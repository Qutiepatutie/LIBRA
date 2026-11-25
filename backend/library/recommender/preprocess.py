import re
import unicodedata
from dataclasses import dataclass

from .dewey import subject_token

MAX_TAGS = 15

PLACEHOLDERS = frozenset({"", "none", "none.", "unknown", "n/a"})
LC_CALL_NUMBER = re.compile(r"^[a-z]{1,3}\s?\d{1,4}(\.\d+)?\s*\.[a-z]\d+", re.I)
DEWEY_NUMBER = re.compile(r"^\d{3}(\.\d+)?(/\.?\d+)*$")
AUTHOR_SPLIT = re.compile(r"\s*(?:;|&|\band\b)\s*", re.I)
ET_AL = re.compile(r"\bet\.?\s*al\b", re.I)
EDITION_SUFFIX = re.compile(
    r"[\s,(]*\b(?:\d+(?:st|nd|rd|th)|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|revised|updated)"
    r"\s+(?:ed\.?|edition)\)?\s*$", re.I)
PROGRAM_FIXES = (("Infromation of Technology", "Information Technology"), ("Infromation", "Information"),
                 ("Masrer", "Master"), ("Business in Administration", "Business Administration"))
NON_THESIS = re.compile(r",?\s*non-thesis track", re.I)
MAJOR_SPLIT = re.compile(r",?\s*(?:major in|with specialization in|medyor sa)\s*", re.I)
DEGREE_PREFIX = re.compile(
    r"^(?:bachelor|master|doctor)(?:\s+(?:of|in))?(?:\s+(?:philosophy|arts|science|education|business)\s+in)?\s*", re.I)

NON_ALNUM = re.compile(r"[\W_]+")


@dataclass(frozen=True)
class Document:
    text: str
    work_key: tuple
    labels: dict
    description_length: int


def clean_text(value):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    return "" if value.lower() in PLACEHOLDERS else value


def _strip_accents(value):
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _is_latin_only(tag):
    return all("LATIN" in unicodedata.name(ch, "") for ch in tag if ch.isalpha())


def clean_tags(tags):
    if isinstance(tags, str):
        tags = [tags]
    elif not isinstance(tags, list):
        return []
    result = []
    seen = set()
    for tag in tags:
        if not isinstance(tag, str):
            continue
        for index, ch in enumerate(tag):
            if unicodedata.category(ch) == "Cc":
                tag = tag[:index]
                break
        tag = tag.strip()
        if (tag.lower() in PLACEHOLDERS or LC_CALL_NUMBER.match(tag) or DEWEY_NUMBER.match(tag)
                or "_" in tag or not _is_latin_only(tag)):
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(tag)
        if len(result) == MAX_TAGS:
            break
    return result


def author_tokens(author):
    author = clean_text(author)
    tokens = {}
    for part in AUTHOR_SPLIT.split(author):
        part = ET_AL.sub("", part)
        if "," in part:
            pieces = [piece.strip() for piece in part.split(",")]
            part = pieces[1] + " " + pieces[0]
        words = [w for w in NON_ALNUM.sub(" ", _strip_accents(part)).split() if len(w) > 1]
        if len(words) < 2:
            continue
        tokens["_".join(w.lower() for w in words)] = " ".join(w.title() for w in words)
    return tokens


def _title_without_edition(title):
    return EDITION_SUFFIX.sub("", clean_text(title)).strip()


def work_key(title, author):
    base = _strip_accents(_title_without_edition(title).lower())
    return " ".join(NON_ALNUM.sub(" ", base).split()), tuple(sorted(author_tokens(author)))


def program_subjects(raw):
    if not isinstance(raw, str):
        return []
    for wrong, right in PROGRAM_FIXES:
        raw = re.sub(re.escape(wrong), right, raw, flags=re.I)
    raw = NON_THESIS.sub("", raw)
    parts = MAJOR_SPLIT.split(raw)
    parts[0] = DEGREE_PREFIX.sub("", parts[0].strip())
    parts = [part.strip(" ,") for part in parts]
    return [part for part in parts if part]


def prepare(title, author, tags, description, call_number=""):
    authors = author_tokens(author)
    subject = subject_token(call_number)
    description = clean_text(description)
    parts = [_title_without_edition(title), *authors, *clean_tags(tags), subject[0] if subject else "", description]
    labels = dict(authors)
    if subject:
        labels[subject[0]] = subject[1]
    return Document(
        text=" ".join(part for part in parts if part),
        work_key=work_key(title, author),
        labels=labels,
        description_length=len(description),
    )
