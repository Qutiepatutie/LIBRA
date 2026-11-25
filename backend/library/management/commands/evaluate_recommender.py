import csv

from django.core.management.base import BaseCommand, CommandError

from library.recommender.evaluation import (
    THESIS, band_table, coverage, ensure_outside_repo, majority_of, precision_at_4, read_key,
    read_sheet_votes, suggest_tau, top4_scores,
)


def _read(path, reader):
    try:
        return reader(path)
    except UnicodeDecodeError:
        raise CommandError(f"{path}: not UTF-8 — save the sheet as 'CSV UTF-8'")
    except OSError as error:
        raise CommandError(f"{path}: {error.strerror or error}")
    except KeyError as error:
        raise CommandError(f"{path}: missing column {error}")
    except ValueError as error:
        raise CommandError(str(error) if str(path) in str(error) else f"{path}: {error}")


class Command(BaseCommand):
    help = "Grade filled judging sheets: band table, suggested tau, precision@4 and coverage."

    def add_arguments(self, parser):
        parser.add_argument("--key", required=True)
        parser.add_argument("--sheet", action="append", required=True)
        parser.add_argument("--out", required=True)
        parser.add_argument("--tau", type=float)
        parser.add_argument("--tau-thesis", type=float)

    def _print_bands(self, label, bands):
        self.stdout.write(f"{label} bands:")
        for b in bands:
            self.stdout.write(f"  low={b.low:.2f} pairs={b.pairs} good={b.good} share={b.share:.2f}")
        suggestion = suggest_tau(bands)
        self.stdout.write(f"  suggested tau ({label}): {suggestion if suggestion is not None else 'none'}")
        return suggestion

    def handle(self, *args, **options):
        try:
            out_dir = ensure_outside_repo(options["out"])
        except ValueError as error:
            raise CommandError(str(error))
        rows = _read(options["key"], read_key)
        sheets = []
        for path in options["sheet"]:
            sheets.append(_read(path, read_sheet_votes))
            self.stdout.write(f"{path}: {len(sheets[-1])} votes read")
        votes = majority_of(sheets)
        all_bands = band_table(rows, votes)
        suggestion = self._print_bands("all", all_bands)
        self._print_bands("books", band_table(rows, votes, "book"))
        self._print_bands("theses", band_table(rows, votes, THESIS))
        tau = options["tau"] if options["tau"] is not None else suggestion
        tau_thesis = options["tau_thesis"]
        if tau is None:
            self.stdout.write("No band qualified; skipping precision@4.")
        else:
            mean, counted = precision_at_4(rows, votes, tau, tau_thesis)
            shown = "n/a" if mean is None else f"{mean:.3f}"
            self.stdout.write(f"precision@4 at tau={tau}: {shown} ({counted} titles)")
            self.stdout.write(f"coverage at tau={tau}: {coverage(tau, tau_thesis):.3f}")
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "bands.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["low", "pairs", "good", "share"])
            for b in all_bands:
                writer.writerow([b.low, b.pairs, b.good, round(b.share, 4)])
        with open(out_dir / "top4_scores.csv", "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["viewed_id", "viewed_type", "rank", "score"])
            writer.writerows(top4_scores())
