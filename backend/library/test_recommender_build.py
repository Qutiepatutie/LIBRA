from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import RoleChoices, UserLogin, UserProfile
from library.models import BookCopy, BookRecommendation, Books, ConditionChoices


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
