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
    largest = max(sorted(counts), key=lambda t: counts[t])
    quotas[largest] = max(0, min(counts[largest], quotas[largest] + target - sum(quotas.values())))
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
    out_dir.mkdir(parents=True, exist_ok=True)
    ids = {r.viewed_id for r in rows} | {r.candidate_id for r in rows}
    books = Books.objects.in_bulk(ids)
    sheet_path = out_dir / "judging_sheet.csv"
    key_path = out_dir / "judging_key.csv"
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


def read_key(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [
            KeyRow(int(row["pair"]), int(row["viewed_id"]), int(row["candidate_id"]),
                   row["viewed_type"], float(row["score"]), int(row["rank"]), row["group"])
            for row in csv.DictReader(f)
        ]
