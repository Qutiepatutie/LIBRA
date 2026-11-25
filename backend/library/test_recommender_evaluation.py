import collections
import csv
import io
import os
import pathlib
import tempfile

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from library.models import BookRecommendation
from library.recommender.evaluation import (
    SHEET_COLUMNS, _quotas, ensure_outside_repo, read_key, sample_pairs, write_judging_files,
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
