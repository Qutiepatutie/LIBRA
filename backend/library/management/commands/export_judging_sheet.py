from django.core.management.base import BaseCommand, CommandError

from library.recommender.evaluation import ensure_outside_repo, sample_pairs, write_judging_files


class Command(BaseCommand):
    help = "Write a blind judging sheet and its key for sampled recommendation pairs."

    def add_arguments(self, parser):
        parser.add_argument("--items", type=int, default=30)
        parser.add_argument("--per-item", type=int, default=8)
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--out", required=True)

    def handle(self, *args, **options):
        try:
            out_dir = ensure_outside_repo(options["out"])
        except ValueError as error:
            raise CommandError(str(error))
        rows = sample_pairs(options["items"], options["per_item"], options["seed"])
        sheet, key = write_judging_files(rows, out_dir)
        per_group = {"A": set(), "B": set()}
        for r in rows:
            per_group[r.group].add(r.viewed_id)
        self.stdout.write(f"sheet={sheet}")
        self.stdout.write(f"key={key}")
        self.stdout.write(
            f"pairs={len(rows)} items_A={len(per_group['A'])} items_B={len(per_group['B'])}")
