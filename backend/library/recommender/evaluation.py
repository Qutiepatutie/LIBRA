import collections
import csv
import math
import random
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from library.models import BookRecommendation, Books
from library.recommender.preprocess import clean_text

SHEET_COLUMNS = ["pair", "viewed_title", "viewed_author", "viewed_type", "viewed_description",
                 "candidate_title", "candidate_author", "candidate_type", "candidate_description",
                 "good"]
KEY_COLUMNS = ["pair", "viewed_id", "candidate_id", "viewed_type", "score", "rank", "group"]
DESCRIPTION_LIMIT = 300


@dataclass(frozen=True)
class KeyRow:
    pair: int
    viewed_id: int
    candidate_id: int
    viewed_type: str
    score: float
    rank: int
    group: str


def ensure_outside_repo(path):
    resolved = Path(path).resolve()
    repo_root = Path(settings.BASE_DIR).parent.resolve()
    if resolved == repo_root or repo_root in resolved.parents:
        raise ValueError(f"{resolved} is inside the repository; judging files hold names.")
    return resolved


def _quotas(counts, items):
    total = sum(counts.values())
    target = min(items, total)
    quotas = {t: min(counts[t], round(items * counts[t] / total)) for t in counts}
    remainder = target - sum(quotas.values())
    for item_type in sorted(counts, key=lambda t: (-counts[t], t)):
        if remainder == 0:
            break
        change = max(-quotas[item_type], min(counts[item_type] - quotas[item_type], remainder))
        quotas[item_type] += change
        remainder -= change
    return quotas


def sample_pairs(items, per_item, seed):
    rng = random.Random(seed)
    eligible = (Books.objects.filter(is_archived=False, recommendations__isnull=False)
                .distinct().order_by("id").values_list("id", "item_type"))
    strata = {}
    for book_id, item_type in eligible:
        strata.setdefault(item_type, []).append(book_id)
    if not strata:
        return []
    quotas = _quotas({t: len(ids) for t, ids in strata.items()}, items)
    sampled = []
    for item_type in sorted(strata):
        sampled += [(book_id, item_type) for book_id in rng.sample(strata[item_type], quotas[item_type])]
    rng.shuffle(sampled)
    split = math.ceil(len(sampled) / 2)
    group_of = {book_id: ("A" if i < split else "B") for i, (book_id, _) in enumerate(sampled)}
    type_of = dict(sampled)
    saved = (BookRecommendation.objects
             .filter(book_id__in=group_of, rank__lte=per_item, recommended__is_archived=False)
             .order_by("book_id", "rank"))
    rows = [(r.book_id, r.recommended_id, r.score, r.rank) for r in saved]
    rng.shuffle(rows)
    return [KeyRow(i, viewed, candidate, type_of[viewed], score, rank, group_of[viewed])
            for i, (viewed, candidate, score, rank) in enumerate(rows, start=1)]


def _safe(value):
    value = str(value)
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


def _description(value):
    return clean_text(value)[:DESCRIPTION_LIMIT]


def write_judging_files(rows, out_dir):
    out_dir = Path(out_dir)
    sheet_path = out_dir / "judging_sheet.csv"
    key_path = out_dir / "judging_key.csv"
    for path in (sheet_path, key_path):
        if path.exists():
            raise ValueError(f"{path} already exists; choose a new --out directory.")
    out_dir.mkdir(parents=True, exist_ok=True)
    ids = {r.viewed_id for r in rows} | {r.candidate_id for r in rows}
    books = Books.objects.in_bulk(ids)
    with open(sheet_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(SHEET_COLUMNS)
        for r in rows:
            viewed, candidate = books[r.viewed_id], books[r.candidate_id]
            writer.writerow([
                r.pair,
                _safe(clean_text(viewed.title)), _safe(clean_text(viewed.author)),
                _safe(viewed.item_type), _safe(_description(viewed.description)),
                _safe(clean_text(candidate.title)), _safe(clean_text(candidate.author)),
                _safe(candidate.item_type), _safe(_description(candidate.description)),
                "",
            ])
    with open(key_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(KEY_COLUMNS)
        for r in rows:
            writer.writerow([r.pair, r.viewed_id, r.candidate_id, _safe(r.viewed_type),
                             repr(float(r.score)), r.rank, _safe(r.group)])
    return sheet_path, key_path


def _require_columns(path, reader, columns):
    missing = [c for c in columns if c not in (reader.fieldnames or [])]
    if missing:
        raise ValueError(f"{path}: missing column(s) {', '.join(missing)}")


def read_key(path):
    rows = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        _require_columns(path, reader, KEY_COLUMNS)
        for line, row in enumerate(reader, start=2):
            try:
                rows.append(KeyRow(int(row["pair"]), int(row["viewed_id"]), int(row["candidate_id"]),
                                   row["viewed_type"], float(row["score"]), int(row["rank"]), row["group"]))
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path}: line {line}: {error}") from error
    return rows


BAND_WIDTH = 0.05
GOOD_SHARE = 0.70
MIN_BAND_PAIRS = 5
THESIS = "thesis"


def read_sheet_votes(path):
    """(pair, good) for every answered row of one filled sheet; blank answers are skipped."""
    votes = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        _require_columns(path, reader, ["pair", "good"])
        for line, row in enumerate(reader, start=2):
            answer = (row.get("good") or "").strip().lower()
            if answer in ("y", "yes"):
                good = True
            elif answer in ("n", "no"):
                good = False
            else:
                continue
            try:
                pair = int(row["pair"])
            except (TypeError, ValueError) as error:
                raise ValueError(f"{path}: line {line}: bad pair number {row['pair']!r}") from error
            votes.append((pair, good))
    return votes


def majority_of(sheets):
    tally = {}
    for votes in sheets:
        for pair, good in votes:
            counts = tally.setdefault(pair, [0, 0])
            counts[0 if good else 1] += 1
    return {pair: yes > no for pair, (yes, no) in tally.items()}


def majority_votes(sheet_paths):
    return majority_of(read_sheet_votes(path) for path in sheet_paths)


@dataclass(frozen=True)
class Band:
    low: float
    pairs: int
    good: int

    @property
    def share(self):
        return self.good / self.pairs


def band_table(rows, votes, viewed_type=None):
    counts = {}
    for r in rows:
        if r.group != "A" or r.pair not in votes:
            continue
        if viewed_type is not None and r.viewed_type != viewed_type:
            continue
        index = min(int(r.score / BAND_WIDTH + 1e-9), 19)
        pairs, good = counts.get(index, (0, 0))
        counts[index] = (pairs + 1, good + (1 if votes[r.pair] else 0))
    return [Band(round(i * BAND_WIDTH, 2), pairs, good) for i, (pairs, good) in sorted(counts.items())]


def suggest_tau(bands):
    for band in bands:
        if band.pairs >= MIN_BAND_PAIRS and band.share >= GOOD_SHARE:
            return band.low
    return None


def _tau_for(viewed_type, tau, tau_thesis):
    return tau_thesis if viewed_type == THESIS and tau_thesis is not None else tau


def precision_at_4(rows, votes, tau, tau_thesis=None):
    per_title = {}
    for r in rows:
        if r.group == "B" and r.score >= _tau_for(r.viewed_type, tau, tau_thesis):
            per_title.setdefault(r.viewed_id, []).append(r)
    precisions = []
    for title_rows in per_title.values():
        shown = [r for r in sorted(title_rows, key=lambda r: r.rank)[:4] if r.pair in votes]
        if shown:
            precisions.append(sum(votes[r.pair] for r in shown) / len(shown))
    if not precisions:
        return None, 0
    return sum(precisions) / len(precisions), len(precisions)


def coverage(tau, tau_thesis=None):
    types = dict(Books.objects.filter(is_archived=False).values_list("id", "item_type"))
    if not types:
        return 0.0
    covered = set()
    saved = BookRecommendation.objects.filter(book_id__in=types).values_list("book_id", "score")
    for book_id, score in saved:
        if score >= _tau_for(types[book_id], tau, tau_thesis):
            covered.add(book_id)
    return len(covered) / len(types)


def top4_scores():
    saved = (BookRecommendation.objects.filter(rank__lte=4, book__is_archived=False)
             .order_by("book_id", "rank").values_list("book_id", "book__item_type", "rank", "score"))
    return list(saved)


def explain_pair(book_id, candidate_id):
    from library.recommender.build import load_catalog, pair_contributions

    catalog = load_catalog()
    index = {book.id: n for n, book in enumerate(catalog.books)}
    if catalog.vectorizer is None or book_id not in index or candidate_id not in index:
        raise ValueError("Both titles must be active and the catalog must have a vocabulary.")
    i, j = index[book_id], index[candidate_id]
    analyzer = catalog.vectorizer.build_analyzer()
    tokens_a = analyzer(catalog.documents[i].text)
    tokens_b = analyzer(catalog.documents[j].text)
    vocabulary = catalog.vectorizer.vocabulary_
    idf = catalog.vectorizer.idf_

    def norm(tokens):
        counts = collections.Counter(t for t in tokens if t in vocabulary)
        return math.sqrt(sum((count * idf[vocabulary[t]]) ** 2 for t, count in counts.items()))

    terms = []
    for term, contribution in pair_contributions(catalog, i, j):
        k = vocabulary[term]
        tf_a, tf_b = tokens_a.count(term), tokens_b.count(term)
        terms.append({
            "term": term, "tf_a": tf_a, "tf_b": tf_b, "idf": float(idf[k]),
            "tfidf_a": float(tf_a * idf[k]), "tfidf_b": float(tf_b * idf[k]),
            "weight_a": float(catalog.matrix[i, k]), "weight_b": float(catalog.matrix[j, k]),
            "contribution": contribution,
        })
    return {"score": sum(t["contribution"] for t in terms), "norm_a": norm(tokens_a),
            "norm_b": norm(tokens_b), "terms": terms}
