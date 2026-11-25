import logging

from django.conf import settings

from ..copies import HIDDEN, catalog_books, title_availability
from ..models import BookRecommendation, Books, ItemType
from ..serializers import BooksSerializer

logger = logging.getLogger("library.recommender")

DEFAULT_MIN_SCORE = 0.10
MAX_CARDS = 4


def min_score(item_type):
    """The serving threshold for a viewed title; a bad setting falls back to the default with a warning."""
    raw = settings.RECOMMENDER_MIN_SCORE
    if item_type == ItemType.THESIS and str(settings.RECOMMENDER_MIN_SCORE_THESIS).strip():
        raw = settings.RECOMMENDER_MIN_SCORE_THESIS
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = None
    if value is None or not 0 <= value <= 1:
        logger.warning("Invalid recommender threshold %r; using %s", raw, DEFAULT_MIN_SCORE)
        return DEFAULT_MIN_SCORE
    return value


def recommendations_for(book, include_score):
    """Up to MAX_CARDS saved recommendations for a title, in rank order, with availability and reasons."""
    rows = list(
        BookRecommendation.objects
        .filter(book=book, score__gte=min_score(book.item_type), recommended__is_archived=False)
        .order_by("rank")
    )
    availability = title_availability([row.recommended_id for row in rows])
    rows = [row for row in rows if availability.get(row.recommended_id, HIDDEN) != HIDDEN][:MAX_CARDS]

    books = catalog_books(Books.objects.filter(pk__in=[row.recommended_id for row in rows]))
    data = {item["id"]: item for item in BooksSerializer(books, many=True).data}

    items = []
    for row in rows:
        item = {
            "book": data[row.recommended_id],
            "availability": availability[row.recommended_id],
            "reason": [term["label"] for term in row.matched_terms],
        }
        if include_score:
            item["score"] = round(row.score, 4)
        items.append(item)
    return items
