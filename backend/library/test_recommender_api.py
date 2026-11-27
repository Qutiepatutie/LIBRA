from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import RoleChoices
from library.models import (
    BookCopy, BookRecommendation, Books, BorrowRecords, ConditionChoices, ItemType, StatusChoices,
)
from library.recommender.serve import min_score
from library.test_recommender_build import RecommenderFixtures


class RecommendationApiTests(RecommenderFixtures, TestCase):
    URL = "/getRecommendations/"

    def setUp(self):
        self.viewed = self.make_book("001.V", "Compilers")
        self.others = [self.make_book(f"001.{n}", f"Other {n}") for n in range(6)]
        for rank, (other, score) in enumerate(zip(self.others, [0.50, 0.40, 0.30, 0.20, 0.10, 0.05]), start=1):
            BookRecommendation.objects.create(
                book=self.viewed, recommended=other, rank=rank, score=score,
                matched_terms=[{"term": "alfred_aho", "label": "Alfred Aho", "weight": 0.2},
                               {"term": "logic", "label": "logic", "weight": 0.1}])
        self.student, self.admin = APIClient(), APIClient()
        self.student_user = self.make_user("stu")
        self.student.force_authenticate(self.student_user)
        self.admin.force_authenticate(self.make_user("adm", role=RoleChoices.ADMIN))

    def get(self, client=None, book_id=None):
        return (client or self.student).get(self.URL, {"book_id": self.viewed.id if book_id is None else book_id})

    def ids(self, response):
        return [item["book"]["id"] for item in response.data["data"]]

    def test_requires_login(self):
        self.assertEqual(APIClient().get(self.URL, {"book_id": self.viewed.id}).status_code, 401)

    def test_bad_and_unknown_ids(self):
        self.assertEqual(self.student.get(self.URL).status_code, 400)
        self.assertEqual(self.get(book_id="abc").status_code, 400)
        self.assertEqual(self.get(book_id=999999).status_code, 404)
        Books.objects.filter(pk=self.viewed.pk).update(is_archived=True)
        self.assertEqual(self.get().status_code, 404)

    def test_top_four_in_rank_order(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.ids(response), [b.id for b in self.others[:4]])

    def test_item_shape(self):
        item = self.get().data["data"][0]
        self.assertEqual(set(item), {"book", "availability", "reason"})
        self.assertEqual(item["reason"], ["Alfred Aho", "logic"])
        self.assertEqual(item["availability"], "available")
        for key in ("title", "cover_url", "item_type", "total_copies", "available_copies", "copies"):
            self.assertIn(key, item["book"])

    def test_score_only_for_admins(self):
        self.assertNotIn("score", self.get().data["data"][0])
        self.assertEqual(self.get(self.admin).data["data"][0]["score"], 0.5)

    @override_settings(RECOMMENDER_MIN_SCORE="0.30")
    def test_threshold_is_inclusive(self):
        self.assertEqual(self.ids(self.get()), [b.id for b in self.others[:3]])

    def test_invalid_threshold_falls_back_to_default(self):
        for bad in ("abc", "0,10", "5", "-1", ""):
            with self.subTest(bad=bad), override_settings(RECOMMENDER_MIN_SCORE=bad), \
                    self.assertLogs("library.recommender", level="WARNING"):
                self.assertEqual(min_score(ItemType.BOOK), 0.10)

    @override_settings(RECOMMENDER_MIN_SCORE="0.10", RECOMMENDER_MIN_SCORE_THESIS="0.45")
    def test_thesis_threshold_applies_to_a_viewed_thesis(self):
        self.assertEqual(len(self.ids(self.get())), 4)
        Books.objects.filter(pk=self.viewed.pk).update(item_type=ItemType.THESIS)
        self.assertEqual(self.ids(self.get()), [self.others[0].id])

    def test_all_copies_held_shows_all_out(self):
        copy = self.others[0].copies.get()
        BorrowRecords.objects.create(user=self.student_user.profile, copy=copy, status=StatusChoices.PENDING)
        self.assertEqual(self.get().data["data"][0]["availability"], "all_out")

    def test_lost_damaged_archived_or_no_copies_are_hidden(self):
        self.others[0].copies.update(condition=ConditionChoices.LOST)
        self.others[1].copies.update(condition=ConditionChoices.DAMAGED)
        self.others[2].copies.update(is_archived=True)
        self.others[3].copies.all().delete()
        self.assertEqual(self.ids(self.get()), [self.others[4].id])

    def test_one_good_free_copy_among_bad_ones_is_available(self):
        BookCopy.objects.create(book=self.others[0], copy_number=2, condition=ConditionChoices.LOST)
        self.assertEqual(self.get().data["data"][0]["availability"], "available")

    def test_archived_candidate_is_dropped_and_next_fills_in(self):
        Books.objects.filter(pk=self.others[0].pk).update(is_archived=True)
        self.assertEqual(self.ids(self.get()), [b.id for b in self.others[1:5]])

    def test_no_rows_gives_empty_list(self):
        self.assertEqual(self.get(book_id=self.others[0].id).data["data"], [])


class GetBooksUnchangedTests(RecommenderFixtures, TestCase):
    def test_get_books_still_lists_copy_counts(self):
        self.make_book("1", "Alpha", copies=2)
        client = APIClient()
        client.force_authenticate(self.make_user("u"))
        book = client.get("/getBooks/").data["data"][0]
        self.assertEqual((book["total_copies"], book["available_copies"], len(book["copies"])), (2, 2, 2))
