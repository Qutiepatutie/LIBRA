import json
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import RoleChoices
from library.models import BookCopy, BookRecommendation, Books
from library.test_recommender_build import RecommenderFixtures


@patch("library.views.rebuild_recommendations")
class RefreshTests(RecommenderFixtures, TestCase):
    NEW = {"call_number": "001.N1", "isbn": "9780000000001", "title": "New Title", "author": "Ana Cruz",
           "publisher": "P", "year_published": "2020", "pages": "10", "item_type": "book"}

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.make_user("A-1", RoleChoices.ADMIN))
        self.book = self.make_book("001.A1", "Compilers", "Alfred V. Aho", ["Compilers"], "parsing")

    def test_add_rebuilds(self, rebuild):
        response = self.client.post("/addBook/", self.NEW, format="multipart")
        self.assertEqual(response.status_code, 201)
        rebuild.assert_called_once()

    def test_unarchive_through_add_rebuilds(self, rebuild):
        self.make_book("001.N1", "New Title", "Ana Cruz", isbn="9780000000001")
        Books.objects.filter(call_number="001.N1").update(is_archived=True)
        response = self.client.post("/addBook/", self.NEW, format="multipart")
        self.assertEqual(response.status_code, 200)
        rebuild.assert_called_once()

    def test_invalid_add_does_not_rebuild(self, rebuild):
        response = self.client.post("/addBook/", {}, format="multipart")
        self.assertEqual(response.status_code, 400)
        rebuild.assert_not_called()

    def test_remove_rebuilds(self, rebuild):
        response = self.client.post("/removeBook/", {"book_id": self.book.id}, format="json")
        self.assertEqual(response.status_code, 200)
        rebuild.assert_called_once()

    def test_text_edit_rebuilds(self, rebuild):
        changes = {"title": "Compilers II", "author": "Someone Else",
                   "tags": ["Compilers", "Parsing"], "description": "lexing", "call_number": "005.1 A1"}
        for field, value in changes.items():
            with self.subTest(field=field):
                rebuild.reset_mock()
                response = self.client.put("/editBook/", {"book_id": self.book.id, field: value}, format="json")
                self.assertEqual(response.status_code, 200)
                rebuild.assert_called_once()

    def test_non_text_edit_does_not_rebuild(self, rebuild):
        response = self.client.put("/editBook/", {"book_id": self.book.id, "pages": "999", "publisher": "X"}, format="json")
        self.assertEqual(response.status_code, 200)
        rebuild.assert_not_called()

    def test_resubmitting_same_text_does_not_rebuild(self, rebuild):
        payload = {"book_id": self.book.id, "title": self.book.title, "author": self.book.author,
                   "tags": self.book.tags, "description": self.book.description}
        response = self.client.put("/editBook/", payload, format="json")
        self.assertEqual(response.status_code, 200)
        rebuild.assert_not_called()

    def test_copy_changes_do_not_rebuild(self, rebuild):
        response = self.client.post("/addCopy/", {"book_id": self.book.id}, format="json")
        self.assertEqual(response.status_code, 201)
        copy = BookCopy.objects.filter(book=self.book).first()
        response = self.client.put("/editCopy/", {"copy_id": copy.id, "condition": "lost"}, format="json")
        self.assertEqual(response.status_code, 200)
        rebuild.assert_not_called()

    def test_failed_rebuild_does_not_fail_the_save(self, rebuild):
        rebuild.side_effect = RuntimeError("boom")
        with self.assertLogs("library.recommender", level="ERROR"):
            response = self.client.put("/editBook/", {"book_id": self.book.id, "title": "Compilers II"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "Compilers II")


class RefreshIntegrationTests(RecommenderFixtures, TestCase):
    def test_new_similar_title_appears_after_add(self):
        client = APIClient()
        client.force_authenticate(self.make_user("A-1", RoleChoices.ADMIN))
        self.make_book("001.A1", "Database Systems Concepts", "A", ["Databases"], "relational database design")
        self.make_book("001.A2", "Database Systems Design", "B", ["Databases"], "relational database systems")
        response = client.post("/addBook/", {
            "call_number": "001.N1", "isbn": "9780000000001", "title": "Database Systems Practice",
            "author": "Ana Cruz", "publisher": "P", "year_published": "2020", "pages": "10",
            "item_type": "book", "tags": json.dumps(["Databases"]),
        }, format="multipart")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(BookRecommendation.objects.filter(recommended__call_number="001.N1").exists())
