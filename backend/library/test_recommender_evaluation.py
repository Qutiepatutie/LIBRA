import collections
import csv
import io
import os
import pathlib
import tempfile

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from library.models import BookRecommendation, Books, ItemType
from library.recommender.build import rebuild_recommendations
from library.recommender.evaluation import (
    SHEET_COLUMNS, Band, KeyRow, _quotas, band_table, coverage, ensure_outside_repo, explain_pair,
    majority_votes, precision_at_4, read_key, sample_pairs, suggest_tau, write_judging_files,
)
from library.test_recommender_build import RecommenderFixtures


class JudgingSheetTests(RecommenderFixtures, TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = tmp.name
        titles = [self.make_book(f"100.B{i}", f"Book {i}", author=f"Author {i}",
                                 description=f"Description {i}") for i in range(8)]
        titles += [self.make_book(f"200.T{i}", f"Thesis {i}", author=f"Student {i}",
                                  item_type="thesis") for i in range(2)]
        for i, title in enumerate(titles):
            for offset, score in enumerate((0.30, 0.20, 0.10), start=1):
                BookRecommendation.objects.create(
                    book=title, recommended=titles[(i + offset) % 10], rank=offset, score=score)
        self.no_rows = self.make_book("300.N1", "No rows")
        formula = self.make_book("300.F1", "=HYPERLINK(1)")
        BookRecommendation.objects.create(book=titles[0], recommended=formula, rank=4, score=0.05)

    def test_same_seed_same_sample(self):
        self.assertEqual(sample_pairs(6, 2, seed=42), sample_pairs(6, 2, seed=42))
        self.assertNotEqual(sample_pairs(6, 2, seed=42), sample_pairs(6, 2, seed=7))

    def test_sample_size_groups_and_strata(self):
        rows = sample_pairs(5, 2, seed=1)
        viewed = {r.viewed_id for r in rows}
        self.assertEqual(len(viewed), 5)
        self.assertEqual(collections.Counter(t for _, t in {(r.viewed_id, r.viewed_type) for r in rows}),
                         {"book": 4, "thesis": 1})
        groups = {r.viewed_id: r.group for r in rows}
        self.assertEqual(collections.Counter(groups.values()), {"A": 3, "B": 2})
        self.assertTrue(all(r.rank <= 2 for r in rows))
        self.assertEqual(sorted(r.pair for r in rows), list(range(1, len(rows) + 1)))

    def test_titles_without_saved_rows_are_never_sampled(self):
        self.assertNotIn(self.no_rows.id, {r.viewed_id for r in sample_pairs(50, 8, seed=3)})

    def test_asking_for_more_than_exist_returns_all_eligible(self):
        self.assertEqual(len({r.viewed_id for r in sample_pairs(50, 8, seed=3)}), 10)

    def test_sheet_is_blind_and_key_holds_scores(self):
        sheet, key = write_judging_files(sample_pairs(6, 2, seed=42), self.out)
        with open(sheet, encoding="utf-8-sig", newline="") as f:
            sheet_rows = list(csv.DictReader(f))
        self.assertEqual(list(sheet_rows[0]), SHEET_COLUMNS)
        self.assertTrue(all(row["good"] == "" for row in sheet_rows))
        self.assertFalse({"score", "rank", "group"} & set(sheet_rows[0]))
        self.assertEqual(read_key(key), sample_pairs(6, 2, seed=42))

    def test_formula_like_cells_are_neutralised(self):
        sheet, _ = write_judging_files(sample_pairs(50, 8, seed=3), self.out)
        with open(sheet, encoding="utf-8-sig") as f:
            text = f.read()
        self.assertIn("'=HYPERLINK(1)", text)
        self.assertNotIn(",=HYPERLINK(1)", text)

    def test_out_inside_repository_is_refused(self):
        with self.assertRaises(ValueError):
            ensure_outside_repo(settings.BASE_DIR / "judging")
        with self.assertRaises(CommandError):
            call_command("export_judging_sheet", out=str(settings.BASE_DIR.parent / "docs"))

    def test_command_writes_both_files(self):
        call_command("export_judging_sheet", items=6, per_item=2, seed=42, out=self.out,
                     stdout=io.StringIO())
        self.assertEqual(sorted(os.listdir(self.out)), ["judging_key.csv", "judging_sheet.csv"])

    def test_relative_and_dotdot_paths_inside_repository_are_refused(self):
        with self.assertRaises(ValueError):
            ensure_outside_repo(os.path.relpath(settings.BASE_DIR / "x"))
        with self.assertRaises(ValueError):
            ensure_outside_repo(settings.BASE_DIR / "a" / ".." / "judging")

    def test_temp_directory_is_accepted(self):
        self.assertEqual(ensure_outside_repo(self.out), pathlib.Path(self.out).resolve())

    def test_quotas_always_total_the_target(self):
        many_small = {f"t{i}": 1 for i in range(10)}
        self.assertEqual(sum(_quotas(many_small, 7).values()), 7)
        self.assertEqual(_quotas({"book": 10}, 4), {"book": 4})
        self.assertEqual(_quotas({"book": 8, "thesis": 2}, 50), {"book": 8, "thesis": 2})
        for items in range(0, 15):
            quotas = _quotas({"a": 5, "b": 3, "c": 1, "d": 1}, items)
            self.assertEqual(sum(quotas.values()), min(items, 10))
            self.assertTrue(all(0 <= quotas[t] <= c for t, c in {"a": 5, "b": 3, "c": 1, "d": 1}.items()))

    def test_description_is_cut_and_placeholder_is_blank(self):
        first = sample_pairs(1, 1, seed=1)[0]
        from library.models import Books
        Books.objects.filter(id=first.viewed_id).update(description="x" * 400)
        Books.objects.filter(id=first.candidate_id).update(description="None")
        sheet, _ = write_judging_files([first], self.out)
        with open(sheet, encoding="utf-8-sig", newline="") as f:
            row = next(csv.DictReader(f))
        self.assertEqual(len(row["viewed_description"]), 300)
        self.assertEqual(row["candidate_description"], "")


def key(pair, viewed, score, rank, group, viewed_type="book"):
    return KeyRow(pair, viewed, 1000 + pair, viewed_type, score, rank, group)


class GradingTests(SimpleTestCase):
    def write_sheet(self, votes, bom=True, extra_column=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "sheet.csv")
        with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["pair", "note", "good"] if extra_column else ["pair", "good"])
            for pair, vote in votes.items():
                writer.writerow([pair, "x", vote] if extra_column else [pair, vote])
        return path

    def test_majority_and_ties(self):
        a = self.write_sheet({1: "Y", 2: "Y", 3: "N", 4: ""})
        b = self.write_sheet({1: "Y", 2: "N", 3: "N", 4: ""})
        c = self.write_sheet({1: "N", 2: "", 3: "Y", 4: ""})
        self.assertEqual(majority_votes([a, b, c]), {1: True, 2: False, 3: False})

    def test_excel_style_sheet_is_accepted(self):
        path = self.write_sheet({2: " yes ", 1: "NO", 99: "y"}, bom=True, extra_column=True)
        self.assertEqual(majority_votes([path]), {2: True, 1: False, 99: True})
        self.assertEqual(band_table([key(1, 1, 0.12, 1, "A"), key(2, 1, 0.13, 2, "A")], majority_votes([path])),
                         [Band(0.10, 2, 1)])

    def test_band_table_and_suggestion(self):
        rows = ([key(p, 1, 0.02, 1, "A") for p in (1, 2)]
                + [key(p, 2, 0.07, 1, "A") for p in range(3, 8)]
                + [key(p, 3, 0.12, 1, "A") for p in range(8, 13)]
                + [key(13, 4, 0.12, 1, "B")])
        good = {1, 2, 3, 4, 8, 9, 10, 11, 13}
        votes = {p: p in good for p in range(1, 14)}
        bands = band_table(rows, votes)
        self.assertEqual(bands, [Band(0.0, 2, 2), Band(0.05, 5, 2), Band(0.10, 5, 4)])
        self.assertAlmostEqual(suggest_tau(bands), 0.10)
        self.assertIsNone(suggest_tau(bands[:2]))

    def test_band_edges(self):
        rows = [key(1, 1, 0.05, 1, "A"), key(2, 1, 0.15, 2, "A"), key(3, 1, 1.0, 3, "A")]
        self.assertEqual([b.low for b in band_table(rows, {1: True, 2: True, 3: True})], [0.05, 0.15, 0.95])

    def test_precision_at_4(self):
        rows = ([key(1, 1, 0.40, 1, "B"), key(2, 1, 0.30, 2, "B"), key(3, 1, 0.20, 3, "B"), key(4, 1, 0.05, 4, "B")]
                + [key(5, 2, 0.50, 1, "B"), key(6, 2, 0.12, 2, "B"), key(7, 2, 0.11, 3, "B"),
                   key(8, 2, 0.105, 4, "B"), key(9, 2, 0.101, 5, "B")]
                + [key(10, 3, 0.05, 1, "B"), key(11, 3, 0.02, 2, "B")]
                + [key(12, 4, 0.90, 1, "A")])
        votes = {1: True, 2: True, 3: False, 4: True, 5: False, 6: True, 7: True, 8: True, 9: True,
                 10: True, 11: True, 12: True}
        mean, counted = precision_at_4(rows, votes, tau=0.10)
        self.assertAlmostEqual(mean, (2 / 3 + 3 / 4) / 2)
        self.assertEqual(counted, 2)
        self.assertEqual(precision_at_4(rows, votes, tau=0.95), (None, 0))

    def test_thesis_threshold_in_precision(self):
        rows = [key(1, 1, 0.20, 1, "B", "thesis"), key(2, 1, 0.50, 2, "B", "thesis")]
        self.assertEqual(precision_at_4(rows, {1: False, 2: True}, tau=0.10, tau_thesis=0.40), (1.0, 1))


class CoverageAndExplainTests(RecommenderFixtures, TestCase):
    def setUp(self):
        mk = self.make_book
        self.a = mk("001.A1", "Compilers", "Alfred V. Aho", ["Compilers", "Programming"],
                    "parsing and code generation for programming languages")
        self.a2 = mk("001.A2", "Compilers, 3rd ed.", "Aho, Alfred", ["Compilers", "Programming"], "None")
        self.b = mk("001.B1", "Parallel Logic Programming", "Evan Tick", ["Logic programming", "Programming"],
                    "parallel programming languages and logic")
        self.c = mk("001.C1", "Clean Code", "Robert C. Martin", ["Programming"], "writing readable code")
        self.d = mk("100.D1", "Body Language", "Allan Pease", ["Psychology"], "nonverbal communication")
        self.e = mk("100.E1", "Psychology", "Robert A. Baron", ["Psychology", "Behavior"],
                    "introduction to psychology and behavior")
        self.t = mk("TH 615 A1", "Antimicrobial Activity of Moringa Leaf Extracts", "Quilantang, et al.", ["Pharmacy"],
                    item_type=ItemType.THESIS)
        self.t2 = mk("TH 615 A2", "Antimicrobial Properties of Semi-Purified Moringa Extracts", "Velomarde, et al.", ["Pharmacy"],
                     item_type=ItemType.THESIS)
        self.x = mk("001.X1", "Programming Pearls", "Jon Bentley", ["Programming"], is_archived=True)
        self.z = mk("900.Z1", "Zymurgy Quarterly", "Qwerty Uiop", [], "None")
        rebuild_recommendations()

    def test_coverage_counts_every_non_archived_title(self):
        self.assertAlmostEqual(coverage(0.0), 8 / 9)
        self.assertEqual(coverage(1.01), 0.0)

    def test_coverage_of_empty_catalog_is_zero(self):
        Books.objects.all().delete()
        self.assertEqual(coverage(0.0), 0.0)

    def test_explanation_adds_up(self):
        result = explain_pair(self.t.id, self.t2.id)
        row = BookRecommendation.objects.get(book=self.t, recommended=self.t2)
        self.assertAlmostEqual(result["score"], row.score, delta=1e-9)
        self.assertAlmostEqual(sum(t["contribution"] for t in result["terms"]), row.score, delta=1e-9)
        first = result["terms"][0]
        self.assertAlmostEqual(first["weight_a"] * first["weight_b"], first["contribution"], delta=1e-12)
        self.assertGreaterEqual(first["tf_a"], 1)

    def test_explaining_an_archived_title_fails_cleanly(self):
        with self.assertRaises(ValueError):
            explain_pair(self.x.id, self.a.id)
        with self.assertRaises(CommandError):
            call_command("explain_recommendation", self.x.id, self.a.id)

    def test_explain_command_prints_total(self):
        out = io.StringIO()
        call_command("explain_recommendation", self.t.id, self.t2.id, stdout=out)
        self.assertRegex(out.getvalue(), r"TOTAL SCORE = [0-9].\d{4}")

    def test_evaluate_command_end_to_end(self):
        src = tempfile.TemporaryDirectory()
        res = tempfile.TemporaryDirectory()
        self.addCleanup(src.cleanup)
        self.addCleanup(res.cleanup)
        call_command("export_judging_sheet", items=6, per_item=4, seed=42, out=src.name, stdout=io.StringIO())
        sheet = os.path.join(src.name, "judging_sheet.csv")
        with open(sheet, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            row["good"] = "Y"
        with open(sheet, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=SHEET_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        out = io.StringIO()
        call_command("evaluate_recommender", key=os.path.join(src.name, "judging_key.csv"), sheet=[sheet],
                     out=res.name, tau=0.0, stdout=out)
        self.assertIn("precision@4", out.getvalue())
        self.assertIn("coverage", out.getvalue())
        self.assertEqual(sorted(os.listdir(res.name)), ["bands.csv", "top4_scores.csv"])
