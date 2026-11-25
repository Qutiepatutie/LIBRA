import logging
import time
from dataclasses import dataclass

import scipy.sparse
from django.db import connection, transaction
from sklearn.feature_extraction.text import TfidfVectorizer

from library.models import BookRecommendation, Books

from .preprocess import Document, prepare
from .stopwords import STOP_WORDS

TOP_K = 12
MAX_TERMS = 3
CHUNK_ROWS = 500
LOCK_KEY = 74010011

logger = logging.getLogger("library.recommender")


def make_vectorizer():
    return TfidfVectorizer(stop_words=STOP_WORDS, min_df=2)


@dataclass
class Catalog:
    books: list[Books]
    documents: list[Document]
    works: int
    vectorizer: TfidfVectorizer | None
    matrix: scipy.sparse.csr_matrix | None


@dataclass(frozen=True)
class BuildStats:
    items: int
    works: int
    vocabulary: int
    pairs: int
    seconds: float


def _year(book):
    try:
        return int(book.year_published)
    except (TypeError, ValueError):
        return 0


def load_catalog():
    books = list(Books.objects.filter(is_archived=False).order_by("id"))
    documents = [prepare(b.title, b.author, b.tags, b.description, b.call_number) for b in books]
    representatives = {}
    for index, (book, doc) in enumerate(zip(books, documents)):
        best = representatives.get(doc.work_key)
        if best is None:
            representatives[doc.work_key] = index
            continue
        # Longest description, then newest year; books are ordered by id, so the first wins remaining ties.
        if (doc.description_length, _year(book)) > (documents[best].description_length, _year(books[best])):
            representatives[doc.work_key] = index
    vectorizer = make_vectorizer()
    matrix = None
    try:
        vectorizer.fit([documents[i].text for i in representatives.values()])
        matrix = vectorizer.transform([d.text for d in documents]).tocsr()
    except ValueError:
        vectorizer = None
    return Catalog(books=books, documents=documents, works=len(representatives),
                   vectorizer=vectorizer, matrix=matrix)


def pair_contributions(catalog, i, j):
    row_i = catalog.matrix[i]
    row_j = catalog.matrix[j]
    weights_i = dict(zip(row_i.indices, row_i.data))
    terms = catalog.vectorizer.get_feature_names_out()
    result = [(str(terms[k]), float(weights_i[k] * w)) for k, w in zip(row_j.indices, row_j.data) if k in weights_i]
    result.sort(key=lambda item: (-item[1], item[0]))
    return result


def _matched_terms(catalog, i, j):
    labels = {**catalog.documents[j].labels, **catalog.documents[i].labels}
    return [{"term": term, "label": labels.get(term, term), "weight": weight}
            for term, weight in pair_contributions(catalog, i, j)[:MAX_TERMS]]


def _build_rows(catalog):
    rows = []
    if catalog.matrix is None:
        return rows
    matrix = catalog.matrix
    transposed = matrix.T.tocsc()
    ids = [b.id for b in catalog.books]
    for start in range(0, len(ids), CHUNK_ROWS):
        scores = (matrix[start:start + CHUNK_ROWS] @ transposed).toarray()
        for offset, row in enumerate(scores):
            i = start + offset
            key = catalog.documents[i].work_key
            candidates = [
                int(j) for j in row.nonzero()[0]
                if j != i and row[j] > 0 and catalog.documents[j].work_key != key
            ]
            candidates.sort(key=lambda j: (-row[j], ids[j]))
            for rank, j in enumerate(candidates[:TOP_K], start=1):
                rows.append(BookRecommendation(
                    book_id=ids[i], recommended_id=ids[j], rank=rank, score=float(row[j]),
                    matched_terms=_matched_terms(catalog, i, j),
                ))
    return rows


def rebuild_recommendations():
    started = time.perf_counter()
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_KEY])
        catalog = load_catalog()
        new_rows = _build_rows(catalog)
        BookRecommendation.objects.all().delete()
        BookRecommendation.objects.bulk_create(new_rows, batch_size=1000)
    stats = BuildStats(
        items=len(catalog.books), works=catalog.works,
        vocabulary=len(catalog.vectorizer.vocabulary_) if catalog.vectorizer else 0,
        pairs=len(new_rows), seconds=time.perf_counter() - started,
    )
    logger.info("recommendations rebuilt: items=%d works=%d vocabulary=%d pairs=%d seconds=%.2f",
                stats.items, stats.works, stats.vocabulary, stats.pairs, stats.seconds)
    return stats
