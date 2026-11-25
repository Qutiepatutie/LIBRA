import collections
import io
import math

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models import F, Q
from django.test import SimpleTestCase, TestCase

from accounts.models import RoleChoices, UserLogin, UserProfile
from library.models import BookCopy, BookRecommendation, Books, ConditionChoices, ItemType
from library.recommender.build import load_catalog, make_vectorizer, pair_contributions, rebuild_recommendations


class RecommenderFixtures:
    def make_book(self, call_number, title, author="", tags=None, description="",
                  copies=1, **fields):
        fields.setdefault("publisher", "Publisher")
        fields.setdefault("year_published", "2000")
        fields.setdefault("pages", "100")
        fields.setdefault("isbn", "")
        book = Books.objects.create(
            call_number=call_number, title=title, author=author,
            tags=tags if tags is not None else [], description=description, **fields,
        )
        for number in range(1, copies + 1):
            BookCopy.objects.create(
                book=book, copy_number=number, condition=ConditionChoices.GOOD,
            )
        return book

    def make_user(self, id_number, role=RoleChoices.STUDENT):
        user = UserLogin.objects.create_user(
            f"{id_number}@example.com", "test-password", role=role,
        )
        UserProfile.objects.create(user=user, id_number=id_number)
        return user


class BookRecommendationModelTests(RecommenderFixtures, TestCase):
    def setUp(self):
        self.a = self.make_book("001.A1", "Compilers")
        self.b = self.make_book("001.B1", "Parallel Logic Programming")
        self.c = self.make_book("001.C1", "Clean Code")
        BookRecommendation.objects.create(book=self.a, recommended=self.b, rank=1, score=0.5)

    def test_duplicate_rank_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            BookRecommendation.objects.create(book=self.a, recommended=self.c, rank=1, score=0.4)

    def test_duplicate_pair_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            BookRecommendation.objects.create(book=self.a, recommended=self.b, rank=2, score=0.4)

    def test_self_recommendation_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            BookRecommendation.objects.create(book=self.c, recommended=self.c, rank=1, score=1.0)

    def test_rows_go_when_either_title_is_deleted(self):
        self.b.delete()
        self.assertEqual(BookRecommendation.objects.count(), 0)

    def test_matched_terms_defaults_to_empty_list(self):
        self.assertEqual(BookRecommendation.objects.get().matched_terms, [])


HAND_DOCS = ["nursing care patients nursing", "nursing patients hospital",
             "inventory hospital care management", "nursing hospital management records"]


class HandCalculationTests(SimpleTestCase):
    """Chapter 3 formulas, computed here without scikit-learn, must match the system."""
    def expected_vectors(self):
        n = len(HAND_DOCS)
        counts = [collections.Counter(doc.split()) for doc in HAND_DOCS]
        df = collections.Counter(term for c in counts for term in c)
        kept = {t for t, d in df.items() if d >= 2}            # min_df = 2 drops "inventory", "records"
        vectors = []
        for c in counts:
            raw = {t: tf * (math.log((1 + n) / (1 + df[t])) + 1) for t, tf in c.items() if t in kept}
            norm = math.sqrt(sum(w * w for w in raw.values()))
            vectors.append({t: w / norm for t, w in raw.items()})
        return vectors

    def test_scores_match_hand_calculation(self):
        expected = self.expected_vectors()
        vectorizer = make_vectorizer()
        matrix = vectorizer.fit_transform(HAND_DOCS)
        self.assertEqual(sorted(vectorizer.vocabulary_), ["care", "hospital", "management", "nursing", "patients"])
        scores = (matrix @ matrix.T).toarray()
        for i in range(4):
            for j in range(4):
                by_hand = sum(w * expected[j].get(t, 0.0) for t, w in expected[i].items())
                self.assertAlmostEqual(scores[i][j], by_hand, delta=1e-9)


class BuildTests(RecommenderFixtures, TestCase):
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
        self.stats = rebuild_recommendations()

    def rows(self, book):
        return list(BookRecommendation.objects.filter(book=book).order_by("rank"))

    def test_stats_count_items_and_works(self):
        self.assertEqual((self.stats.items, self.stats.works), (9, 8))     # archived excluded; A and A2 are one work
        self.assertEqual(self.stats.pairs, BookRecommendation.objects.count())

    def test_a_work_counts_once_for_idf(self):
        # "compilers" appears in two rows of one work, so its document frequency is 1 and min_df=2 removes it.
        self.assertNotIn("compilers", load_catalog().vectorizer.vocabulary_)

    def test_no_self_same_work_or_archived_rows(self):
        self.assertFalse(BookRecommendation.objects.filter(book=F("recommended")).exists())
        self.assertNotIn(self.a2.id, [r.recommended_id for r in self.rows(self.a)])
        self.assertNotIn(self.a.id, [r.recommended_id for r in self.rows(self.a2)])
        self.assertFalse(BookRecommendation.objects.filter(Q(book=self.x) | Q(recommended=self.x)).exists())

    def test_non_representative_edition_still_gets_recommendations(self):
        self.assertTrue(self.rows(self.a2))

    def test_item_with_no_shared_terms_has_no_rows(self):
        self.assertFalse(BookRecommendation.objects.filter(Q(book=self.z) | Q(recommended=self.z)).exists())

    def test_expected_top_matches(self):
        self.assertEqual(self.rows(self.t)[0].recommended_id, self.t2.id)
        self.assertEqual(self.rows(self.d)[0].recommended_id, self.e.id)

    def test_ranks_are_contiguous_and_scores_descend(self):
        for book in (self.a, self.b, self.c, self.e):
            rows = self.rows(book)
            self.assertLessEqual(len(rows), 12)
            self.assertEqual([r.rank for r in rows], list(range(1, len(rows) + 1)))
            self.assertEqual([r.score for r in rows], sorted((r.score for r in rows), reverse=True))
            self.assertTrue(all(0 < r.score <= 1 for r in rows))

    def test_reason_terms_come_from_the_score(self):
        catalog = load_catalog()
        index = {book.id: n for n, book in enumerate(catalog.books)}
        row = self.rows(self.b)[0]
        parts = pair_contributions(catalog, index[self.b.id], index[row.recommended_id])
        self.assertAlmostEqual(sum(weight for _, weight in parts), row.score, delta=1e-9)
        self.assertEqual([t["term"] for t in row.matched_terms], [term for term, _ in parts[:3]])
        self.assertEqual(set(row.matched_terms[0]), {"term", "label", "weight"})

    def test_author_tokens_are_labelled_with_names(self):
        self.make_book("001.A9", "Principles of Compiler Design", "Alfred V. Aho", ["Compilers"])
        rebuild_recommendations()
        terms = {t["term"]: t["label"] for r in self.rows(self.a) for t in r.matched_terms}
        self.assertEqual(terms.get("alfred_aho"), "Alfred Aho")

    def test_two_builds_are_identical(self):
        before = list(BookRecommendation.objects.values_list("book_id", "recommended_id", "rank", "score"))
        rebuild_recommendations()
        self.assertEqual(before, list(BookRecommendation.objects.values_list("book_id", "recommended_id", "rank", "score")))


class SmallCatalogTests(RecommenderFixtures, TestCase):
    def test_empty_catalog(self):
        self.assertEqual(rebuild_recommendations().pairs, 0)

    def test_no_vocabulary_clears_old_rows(self):
        a, b = self.make_book("1", "Alpha", "Ann Lee"), self.make_book("2", "Beta", "Bo Chan")
        BookRecommendation.objects.create(book=a, recommended=b, rank=1, score=0.5)
        stats = rebuild_recommendations()
        self.assertEqual((stats.vocabulary, stats.pairs, BookRecommendation.objects.count()), (0, 0, 0))

    def test_equal_scores_order_by_id_and_same_title_other_author_is_another_work(self):
        p = self.make_book("5.P", "Marine Biology Basics", "Ann Lee")
        q1 = self.make_book("5.Q1", "Marine Biology", "Bo Chan")
        q2 = self.make_book("5.Q2", "Marine Biology", "Cy Dee")
        rebuild_recommendations()
        self.assertEqual(list(BookRecommendation.objects.filter(book=p).values_list("recommended_id", flat=True)),
                         [q1.id, q2.id])                      # equal scores: lower id first
        self.assertTrue(BookRecommendation.objects.filter(book=q1, recommended=q2).exists())

    def test_shared_dewey_subject_links_titles_with_no_shared_word(self):
        a = self.make_book("658.1 A1 2020", "Alpha Kinetics", "Ann Lee")
        b = self.make_book("658.4 B2 2021", "Beta Ledger", "Bo Chan")
        rebuild_recommendations()
        row = BookRecommendation.objects.get(book=a, recommended=b)
        self.assertEqual(row.matched_terms[0]["label"], "Management & public relations")

    def test_non_list_tags_do_not_crash(self):               # Review Focus 1
        book = self.make_book("3", "Gamma Delta", tags=["x"])
        Books.objects.filter(pk=book.pk).update(tags="Programming", description=None)
        rebuild_recommendations()

    def test_command_prints_stats(self):
        out = io.StringIO()
        call_command("rebuild_recommendations", stdout=out)
        self.assertRegex(out.getvalue(), r"items=0 works=0 vocabulary=0 pairs=0 seconds=\d+\.\d\d")
