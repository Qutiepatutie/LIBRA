from unittest import mock

import requests
from django.test import TestCase
from rest_framework.test import APIClient

from library.test_recommender_build import RecommenderFixtures

ISBN = "9780000000001"


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class AutofillTests(RecommenderFixtures, TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.make_user("A1"))

    def get_autofill(self, edition=None, work=None, isbn_payload="default",
                     work_error=False):
        edition = {"works": [{"key": "/works/OL9W"}]} if edition is None else edition
        work = {} if work is None else work
        if isbn_payload == "default":
            isbn_payload = {f"ISBN:{ISBN}": {
                "key": "/books/OL1M",
                "title": "T",
                "subjects": [{"name": f"S{n}"} for n in range(20)],
            }}

        def fake_get(url, **kwargs):
            if "api/books?bibkeys=" in url:
                return FakeResponse(isbn_payload)
            if "/books/OL1M.json" in url:
                return FakeResponse(edition)
            if "/works/OL9W.json" in url:
                if work_error:
                    raise requests.Timeout()
                return FakeResponse(work)
            raise AssertionError(f"unexpected url {url}")

        with mock.patch("books.views.requests.get", side_effect=fake_get):
            return self.client.get(f"/autofill/?isbn={ISBN}")

    def test_description_comes_from_the_work_record(self):
        response = self.get_autofill(
            edition={"works": [{"key": "/works/OL9W"}], "description": "From the edition"},
            work={"description": {"value": "From the work"}},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["book"]["description"], "From the work")

    def test_falls_back_to_the_edition_description(self):
        response = self.get_autofill(
            edition={"works": [{"key": "/works/OL9W"}], "description": "From the edition"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["book"]["description"], "From the edition")

    def test_failing_work_request_falls_back_to_the_edition_description(self):
        response = self.get_autofill(
            edition={"works": [{"key": "/works/OL9W"}], "description": {"value": "From the edition"}},
            work_error=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["book"]["description"], "From the edition")

    def test_no_description_is_an_empty_string(self):
        response = self.get_autofill()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["book"]["description"], "")

    def test_tags_are_capped_and_keep_open_library_order(self):
        response = self.get_autofill()
        self.assertEqual(response.data["book"]["tags"], [f"S{n}" for n in range(15)])

    def test_unknown_isbn_is_404(self):
        response = self.get_autofill(isbn_payload={})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["message"], "No book found")
