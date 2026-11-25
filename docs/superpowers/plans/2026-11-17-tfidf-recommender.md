# TF-IDF "Books to Recommend" Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show up to 4 similar catalog items in the view-book modal, computed with TF-IDF and cosine similarity, with tools to choose τ and measure precision@4 and coverage.

**Architecture:** A build step turns every non-archived title into one text document, fits scikit-learn's `TfidfVectorizer` on one representative per work, and saves each title's top 12 matches into a `book_recommendations` table. The build runs when an admin adds, archives or edits the text of a title. The modal's endpoint only reads saved rows, applies τ and copy availability, and returns at most 4.

**Tech Stack:** Django 5 + Django REST Framework, PostgreSQL, scikit-learn 1.9.1, React (Vite).

**Spec:** `docs/superpowers/specs/2026-11-14-tfidf-recommender-design.md`. Sections 15 and 16 (amendments) override earlier sections; where they disagree, section 16 wins. Read it before starting.

## Global Constraints

- **Base:** `origin/main` at `003f53a` (2026-11-25). It includes PR #15, the BookCopy split (`f9c901e`), the cover upload (`e7aa863`, `addBook/` is multipart only) and the endpoint permissions tightening (`9a7778d`, catalog edits are admin only). Task 0 sets this up.
- **Execution method (chosen by the user):** subagents do the coding; the main conversation only coordinates and reports.
- **Never touch the live database or live storage.** The main checkout's `backend/.env` points at live Supabase. The worktree has no `backend/.env`; never copy it there. Run every `manage.py` command with `--settings=recommender_pg` (Task 0), which sets dummy Supabase values. Never run `migrate` or `test` with default settings.
- **Test command prefix**, written `TEST` in this plan, run from `backend/` in the worktree:
  `PYTHONPATH="C:/github25/recommender-test-settings" RECOMMENDER_AGENT=<tag> C:/github25/bookly-lms/backend/venv/Scripts/python.exe manage.py test --settings=recommender_pg --noinput`
  Each parallel worker uses its own `<tag>` (it names the test database).
- `scikit-learn==1.9.1`. Vectorizer is exactly `TfidfVectorizer(stop_words=STOP_WORDS, min_df=2)`; every other parameter stays at its default.
- Constants: top 12 saved per title, at most 4 served, at most 3 reason terms, at most 15 tags per item, default τ `0.10`, Dewey granularity = division (tens).
- No Django signals. Rebuilds are explicit calls.
- UI: use the designer's existing recommendation slot in `ShowBook.jsx` and the existing `BookPanel` card; create no CSS file and edit no existing CSS file. The UI commit merges only after the designer signs off.
- Judging sheets and the school's thesis file contain student names: never write them inside the repository, never commit them.
- The GitHub repository is public: keep security details out of commit messages and PR text.
- Do not modify `frontend/src/components/ui/dashboard/graphs/Heatmap.jsx`, `.gitignore`, `docs/reports/`, `docs/Data import libra/` or `seed_data.py` (git-ignored). The school's data files in `docs/Data import libra/` contain student names: read them only if a task says so, never copy them into the repository.
- Commit messages: plain imperative sentences, no attribution lines.

## Review Focus

Inputs the spec implies but does not spell out. Each has a test in the task named.

1. **`tags` that is not a list** (the live table has at least one scalar value; `description` and `author` can be null): the build must skip or coerce it, not crash. Task 1.
2. **A recommended title whose copies are all archived or it has no copies:** hidden, same as all lost or damaged. Task 4.
3. **τ edge values:** a score exactly equal to τ is shown; `RECOMMENDER_MIN_SCORE` set to `abc`, `0,10` or `5` falls back to 0.10 with a warning. Task 4.
4. **Titles starting with `=`, `+`, `-` or `@` in the judging sheet:** written so a spreadsheet does not run them as formulas. Task 6.
5. **A judging sheet saved by Excel:** UTF-8 BOM, reordered rows, extra columns, answers like ` yes `, unknown pair numbers. The grader accepts it and ignores unknown pairs. Task 7.

## File Map

| Path | Responsibility |
|---|---|
| `backend/library/recommender/__init__.py` | package marker |
| `backend/library/recommender/stopwords.py` | the five custom word lists and `STOP_WORDS` |
| `backend/library/recommender/dewey.py` | Dewey division names and the call-number → subject token rule |
| `backend/library/recommender/preprocess.py` | pure text rules; no database, no scikit-learn |
| `backend/library/recommender/build.py` | vectorizer config, catalog loading, `rebuild_recommendations()` |
| `backend/library/recommender/serve.py` | τ lookup and `recommendations_for()` |
| `backend/library/recommender/evaluation.py` | sampling, judging files, grading, pair explanation |
| `backend/library/management/commands/*.py` | `rebuild_recommendations`, `export_judging_sheet`, `evaluate_recommender`, `explain_recommendation` |
| `backend/library/copies.py` | add `with_availability`, `catalog_books`, `title_availability` |
| `backend/library/models.py` + migration | `BookRecommendation` |
| `backend/library/views.py`, `urls.py` | `get_recommendations`, rebuild hooks |
| `backend/library/test_recommender_*.py` | tests, one file per task |
| `backend/RECOMMENDER.md` | operations notes (same style as `ADMIN_ANALYTICS.md`) |
| `frontend/src/api/books.js` | `getRecommendations` |
| `backend/books/views.py` | autofill: description from the work record, tag cap |
| `frontend/src/components/library/showbook/useRecommendations.js`, `RecommendedBooks.jsx` | data hook and the cards inside the designer's slot |
| `docs/recommender-designer-handoff.md` | what the designer needs to finish the slot |

---

### Task 0: Workspace and test environment

**Files:**
- Create (outside the repo): `C:/github25/recommender-test-settings/recommender_pg.py`

**Interfaces:**
- Produces: worktree `C:/github25/bookly-lms-recommender` on `feat/tfidf-recommender` rebased onto `origin/main`; the `TEST` command.

- [ ] **Step 1: Create the worktree.** (Done by the controller on 2026-11-25.) The main checkout stays on `main` with its uncommitted `.gitignore` and `Heatmap.jsx` changes and the untracked `docs/reports/`; none of them may be touched.

```bash
cd C:/github25/bookly-lms
git worktree add ../bookly-lms-recommender feat/tfidf-recommender
cd ../bookly-lms-recommender
git fetch origin
git rebase origin/main
```

Expected: rebase succeeds with no conflicts (the branch only adds files under `docs/superpowers/`). `git log --oneline -8` shows the docs commits on top of `003f53a`.

- [ ] **Step 2: Create the settings module** with exactly this content:

```python
"""Throwaway local Postgres for the recommender work. Never points at the live DB."""
import os

# library/supabase_client.py builds a client at import time. Dummy values keep tests away from live storage.
os.environ.setdefault("SUPABASE_URL", "http://127.0.0.1:9")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-only-dummy-key")

from backend.test_settings import *  # noqa: E402,F403

DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'NAME': 'postgres', 'USER': 'postgres', 'PASSWORD': '',
    'HOST': '127.0.0.1', 'PORT': '55432',
    'TEST': {'NAME': 'test_recommender_' + os.environ.get('RECOMMENDER_AGENT', 'main')},
}}
```

- [ ] **Step 3: Check Postgres is up.** Run `"C:/Program Files/PostgreSQL/18/bin/pg_isready" -h 127.0.0.1 -p 55432`. Expected: `accepting connections`. If not, start a throwaway cluster: `initdb -U postgres -A trust -D <scratch dir>` then `pg_ctl -D <scratch dir> -o "-p 55432" start` (do not pipe `pg_ctl` output; it hangs the shell).

- [ ] **Step 4: Install scikit-learn and supabase into the shared venv.** `C:/github25/bookly-lms/backend/venv/Scripts/python.exe -m pip install scikit-learn==1.9.1 supabase`. Expected: `Successfully installed` including scipy (numpy 2.4.2 is already there). `supabase` is in `dev-requirements.txt` but missing from the venv; `library/supabase_client.py` imports it.

- [ ] **Step 5: Baseline.** Run `TEST library books`. Expected: all tests pass (the 9 `addBook/` tests that failed with 415 before were fixed on main for multipart). Record the count; if any fail, stop and report before changing code.

---

### Task 1: Stop words and preprocessing

**Files:**
- Create: `backend/library/recommender/__init__.py` (empty), `stopwords.py`, `dewey.py`, `preprocess.py`
- Modify: `backend/requirements.txt` (UTF-16 LE with BOM and CRLF: keep that encoding), `backend/dev-requirements.txt` (ASCII): add `scikit-learn==1.9.1` to both
- Test: `backend/library/test_recommender_preprocess.py` (`django.test.SimpleTestCase`)

**Interfaces:**
- Produces, in `stopwords.py`:
  - `LIBRARY_WORDS = frozenset({"study","research","researchers","respondents","thesis","chapter","book","edition"})`
  - `FILIPINO_WORDS = frozenset({"ang","ng","sa","mga","na","at","ay","ito","para","kung","si","ni","kay","nang","pa"})`
  - `THESIS_TITLE_WORDS = frozenset({"selected","level","basis","evaluation","assessment","determination","implementation","development","impact","based","iii"})`
  - `PLACE_WORDS = frozenset({"city","pampanga","bulacan","angeles","san","marilao","region","province","district","caloocan"})`
  - `BOOK_TITLE_WORDS = frozenset({"guide","introduction","principles","basic","applications","approach","fundamentals","concepts","practice","essentials","applied","volume","part"})`
  - `STOP_WORDS: list[str]` = sorted union of the five sets and `sklearn.feature_extraction.text.ENGLISH_STOP_WORDS`
  - A comment above `THESIS_TITLE_WORDS`, `PLACE_WORDS` and `BOOK_TITLE_WORDS` records the title counts from spec sections 4.7 and 16.2.
- Produces, in `dewey.py`:
  - `DEWEY_DIVISIONS: dict[str, str]`: all 100 divisions `"000"` … `"990"` with their names from OCLC's DDC 23 second summary (e.g. `"000": "Computer science, knowledge & systems"`, `"150": "Psychology"`, `"340": "Law"`, `"370": "Education"`, `"610": "Medicine & health"`, `"650": "Management & public relations"`). A comment says the team verifies the table against OCLC's published summaries.
  - `SPECIAL_COLLECTIONS = {"FIC": ("ddc_fic", "Fiction"), "RIZ": ("ddc_riz", "Rizaliana"), "BIO": ("ddc_bio", "Biography"), "B": ("ddc_bio", "Biography"), "FB": ("ddc_bio", "Biography")}`
  - `subject_token(call_number) -> tuple[str, str] | None`: the first match of `\b(\d{3})(?:\.\d+)?\b` gives `("ddc_" + division, DEWEY_DIVISIONS[division])` where `division = digits[:2] + "0"`; with no match, the first whitespace-separated word (uppercased) looked up in `SPECIAL_COLLECTIONS`; otherwise `None`. Non-strings give `None`.
- Produces, in `preprocess.py`:
  - `clean_text(value) -> str`
  - `clean_tags(tags) -> list[str]`
  - `author_tokens(author) -> dict[str, str]` (token → display label, in author order)
  - `work_key(title, author) -> tuple[str, tuple[str, ...]]`
  - `program_subjects(raw) -> list[str]`
  - `@dataclass(frozen=True) class Document: text: str; work_key: tuple; labels: dict[str, str]; description_length: int`
  - `MAX_TAGS = 15`
  - `prepare(title, author, tags, description, call_number="") -> Document`

Rules the tests do not fully determine (use these exact patterns):

```python
PLACEHOLDERS = frozenset({"", "none", "none.", "unknown", "n/a"})          # compared after strip().lower()
LC_CALL_NUMBER = re.compile(r"^[a-z]{1,3}\s?\d{1,4}(\.\d+)?\s*\.[a-z]\d+", re.I)   # Qa76.76.c65 a37 2007
DEWEY_NUMBER = re.compile(r"^\d{3}(\.\d+)?(/\.?\d+)*$")                    # 005.4/53, 005.1
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
```

- `clean_text`: `""` for `None`, a non-string, or a placeholder; otherwise the stripped string.
- `clean_tags`: a string counts as one tag; any other non-list gives `[]`; non-string members are skipped. Per tag: cut at the first control character (Unicode category `Cc`) and strip; drop placeholders, call-number matches, tags containing `_`, and tags with any letter whose Unicode name does not contain `LATIN`; de-duplicate ignoring case, keeping the first spelling; keep the first `MAX_TAGS`.
- `author_tokens`: split with `AUTHOR_SPLIT`; remove `ET_AL` matches from each part; with a comma, use `parts[1] + " " + parts[0]` and ignore later parts; strip accents (NFKD, drop combining marks); replace non-alphanumerics with spaces; drop one-character words; a part left with fewer than two words gives no token; token = lowercase words joined by `_`, label = the words title-cased and joined by spaces.
- `work_key`: title lowercased, accents stripped, `EDITION_SUFFIX` removed, non-alphanumerics to spaces, spaces collapsed; second element is the sorted author tokens.
- `program_subjects`: apply `PROGRAM_FIXES` (case-insensitive), remove `NON_THESIS`, split with `MAJOR_SPLIT`, strip `DEGREE_PREFIX` from the first part, strip `" ,"`, drop empties.
- `prepare`: `text` = the title with `EDITION_SUFFIX` removed, the author tokens, the cleaned tags, the subject token from `subject_token(call_number)` and the description, joined by single spaces (empty parts omitted); `labels` = the author token map plus `{subject token: subject label}`; `description_length` = `len(clean_text(description))`.

- [ ] **Step 1: Write the failing tests** in `test_recommender_preprocess.py`:

```python
class CleanTextTests(SimpleTestCase):
    def test_placeholders_and_non_strings_are_empty(self):
        for value in (None, "", "  ", "None", "none.", "Unknown", " N/A ", 5, ["x"]):
            self.assertEqual(clean_text(value), "")
    def test_real_text_is_stripped(self):
        self.assertEqual(clean_text("  2nd edition "), "2nd edition")

class CleanTagsTests(SimpleTestCase):
    def test_drops_call_numbers_scripts_underscores_placeholders(self):
        tags = ["Compilers", "Qa76.76.c65 a37 2007", "Bm545 .d3312 2002", "005.4/53", "005.1",
                "Компьютеры", "open_syllabus_project", "None", "Programmation parallèle", "compilers"]
        self.assertEqual(clean_tags(tags), ["Compilers", "Programmation parallèle"])
    def test_control_character_cuts_the_tag(self):
        self.assertEqual(clean_tags(["Philosophy, Jewish.\u001e 0"]), ["Philosophy, Jewish."])
    def test_at_most_fifteen_tags(self):
        self.assertEqual(clean_tags([f"Subject {n}" for n in range(176)]), [f"Subject {n}" for n in range(15)])
    def test_non_list_values(self):                       # Review Focus 1
        self.assertEqual(clean_tags(None), [])
        self.assertEqual(clean_tags(5), [])
        self.assertEqual(clean_tags({"a": 1}), [])
        self.assertEqual(clean_tags("Programming"), ["Programming"])
        self.assertEqual(clean_tags(["Logic", None, 7, ["x"]]), ["Logic"])

class AuthorTokenTests(SimpleTestCase):
    def test_both_name_orders_give_one_token(self):
        self.assertEqual(author_tokens("Alfred V. Aho"), {"alfred_aho": "Alfred Aho"})
        self.assertEqual(author_tokens("Aho, Alfred V."), {"alfred_aho": "Alfred Aho"})
    def test_several_authors(self):
        self.assertEqual(list(author_tokens("Andy Hunt; Dave Thomas & Ana Cruz and Li Wei")),
                         ["andy_hunt", "dave_thomas", "ana_cruz", "li_wei"])
    def test_et_al_gives_no_token(self):
        self.assertEqual(author_tokens("Quilantang, et al."), {})
    def test_full_name_before_et_al_is_kept(self):
        self.assertEqual(author_tokens("Masaaki Mitani et al."), {"masaaki_mitani": "Masaaki Mitani"})
    def test_real_multi_author_formats(self):
        self.assertEqual(list(author_tokens("Clark, Alexander & Sousa, Bailey")), ["alexander_clark", "bailey_sousa"])
        self.assertEqual(list(author_tokens("Gopee, Niel and Galloway, Jo")), ["niel_gopee", "jo_galloway"])
        self.assertEqual(list(author_tokens("Brinkmann, Svend,")), ["svend_brinkmann"])
    def test_credentials_after_second_comma_ignored(self):
        self.assertEqual(list(author_tokens("Daluyong, Mirasol T. Abrenica, MD, FPCP")), ["mirasol_abrenica_daluyong"])
    def test_accents_and_missing_author(self):
        self.assertEqual(list(author_tokens("Peña, José")), ["jose_pena"])
        for value in (None, "", "Unknown"):
            self.assertEqual(author_tokens(value), {})

class WorkKeyTests(SimpleTestCase):
    def test_editions_share_a_key(self):
        self.assertEqual(work_key("Calculus, 11th ed.", "James Stewart"),
                         work_key("Calculus (10th edition)", "Stewart, James"))
        self.assertEqual(work_key("Compilers", "Alfred V. Aho")[0], "compilers")
    def test_different_authors_are_different_works(self):
        self.assertNotEqual(work_key("Psychology", "Robert A. Baron"), work_key("Psychology", "David Myers"))

class ProgramSubjectTests(SimpleTestCase):
    def test_real_sample_spellings(self):
        cases = {
            "Master of Arts in Education, Major in Educational Management": ["Education", "Educational Management"],
            "Master in Public Administration Non-Thesis Track": ["Public Administration"],
            "Master in Infromation of Technology": ["Information Technology"],
            "Masrer of Science in Hospitality Management": ["Hospitality Management"],
            "Master in Business in Administration": ["Business Administration"],
            "Doctor of philosophy in Nursing, Major in Nursing Administration": ["Nursing", "Nursing Administration"],
            "Master of Science in Criminal Justice with Specialization in Criminology": ["Criminal Justice", "Criminology"],
            "Major in Educational Management": ["Educational Management"],
            "Antas Pagkadalubhasa sa Sining ng Pagtuturo, Medyor sa Filipino":
                ["Antas Pagkadalubhasa sa Sining ng Pagtuturo", "Filipino"],
            "Bachelor of Science in Pharmacy": ["Pharmacy"],
            "": [],
        }
        for raw, expected in cases.items():
            self.assertEqual(program_subjects(raw), expected, raw)

class SubjectTokenTests(SimpleTestCase):
    def test_real_call_numbers(self):
        cases = {
            "001.4 K96 2019": ("ddc_000", "Computer science, knowledge & systems"),
            "F 346.59902 D71 2023": ("ddc_340", "Law"),
            "MT 362.11 V82 2020": ("ddc_360", DEWEY_DIVISIONS["360"]),
            "D 658 A2 2021": ("ddc_650", "Management & public relations"),
            "TH 615 P43t 2023": ("ddc_610", "Medicine & health"),
            "FR 150 A1 2020": ("ddc_150", "Psychology"),
            "FIC D64 2001 bk.1": ("ddc_fic", "Fiction"),
            "RIZ B41 2016": ("ddc_riz", "Rizaliana"),
            "FB A2 2016": ("ddc_bio", "Biography"),
            "B G85 2007": ("ddc_bio", "Biography"),
        }
        for call, expected in cases.items():
            self.assertEqual(subject_token(call), expected, call)
    def test_no_subject(self):
        for call in ("", None, 5, "X 12 A1", "00"):
            self.assertIsNone(subject_token(call))
    def test_all_hundred_divisions_are_named(self):
        self.assertEqual(sorted(DEWEY_DIVISIONS), [f"{n:03d}" for n in range(0, 1000, 10)])
        self.assertTrue(all(name.strip() for name in DEWEY_DIVISIONS.values()))

class PrepareTests(SimpleTestCase):
    def test_document_text_and_labels(self):
        doc = prepare("Compilers, 2nd ed.", "Aho, Alfred V.", ["Compilers", "005.4/53"], "Parsing and code generation",
                      "005.453 A28 2007")
        self.assertEqual(doc.text, "Compilers alfred_aho Compilers ddc_000 Parsing and code generation")
        self.assertEqual(doc.labels, {"alfred_aho": "Alfred Aho", "ddc_000": "Computer science, knowledge & systems"})
        self.assertEqual(doc.description_length, len("Parsing and code generation"))
    def test_empty_fields_add_nothing(self):                # Review Focus 1
        doc = prepare("Body Language", None, None, "None")
        self.assertEqual(doc.text, "Body Language")
        self.assertEqual(doc.description_length, 0)

class StopWordTests(SimpleTestCase):
    def test_lists_are_combined(self):
        for word in ("the", "study", "ng", "evaluation", "pampanga", "introduction", "applied"):
            self.assertIn(word, STOP_WORDS)
        self.assertNotIn("feasibility", STOP_WORDS)
        self.assertEqual(STOP_WORDS, sorted(set(STOP_WORDS)))
```

- [ ] **Step 2: Run** `TEST library.test_recommender_preprocess`. Expected: import errors (module not found).
- [ ] **Step 3: Implement** `stopwords.py`, `dewey.py` and `preprocess.py` per the Interfaces block.
- [ ] **Step 4: Add the dependency.** Append `scikit-learn==1.9.1` to `dev-requirements.txt`. For `requirements.txt`, read as `utf-16`, append the line with `\r\n`, write back as `utf-16` (Python's `utf-16` codec keeps the BOM). Verify with `file backend/requirements.txt`: still `UTF-16, little-endian`.
- [ ] **Step 5: Run** `TEST library.test_recommender_preprocess`. Expected: all pass.
- [ ] **Step 6: Commit.** `git add backend/library/recommender backend/library/test_recommender_preprocess.py backend/requirements.txt backend/dev-requirements.txt` then `git commit -m "Add recommender preprocessing rules, stop words and Dewey subjects"`.

---

### Task 2: `BookRecommendation` model and τ settings

**Files:**
- Modify: `backend/library/models.py` (append after `BookCopy`), `backend/backend/settings.py`
- Create: migration via `makemigrations` (expected `0017_bookrecommendation.py`)
- Test: `backend/library/test_recommender_build.py` (model tests now; build tests added in Task 3)

**Interfaces:**
- Produces: `library.models.BookRecommendation` with `book` (FK `Books`, CASCADE, `related_name="recommendations"`), `recommended` (FK `Books`, CASCADE, `related_name="+"`), `rank` (`PositiveSmallIntegerField`), `score` (`FloatField`), `matched_terms` (`JSONField(default=list)`); `Meta.db_table = "book_recommendations"`, `ordering = ["book_id", "rank"]`; constraints named `book_recommendation_rank_unique` (book, rank), `book_recommendation_pair_unique` (book, recommended), `book_recommendation_not_self` (`~Q(book=F("recommended"))`).
- Produces: settings `RECOMMENDER_MIN_SCORE = os.environ.get("RECOMMENDER_MIN_SCORE", "0.10")` and `RECOMMENDER_MIN_SCORE_THESIS = os.environ.get("RECOMMENDER_MIN_SCORE_THESIS", "")` (raw strings; parsed in Task 4).
- Produces, in the test file: `class RecommenderFixtures` with `make_book(call_number, title, author="", tags=None, description="", copies=1, **fields) -> Books` (note: call numbers like `001.A1` carry Dewey class `001`, so fixtures sharing that prefix share a subject token) (creates the title and `copies` good copies numbered from 1; fills `publisher="Publisher"`, `year_published="2000"`, `pages="100"`, `isbn=""` unless given) and `make_user(id_number, role=RoleChoices.STUDENT) -> UserLogin` (also creates the `UserProfile`). Later test files import it.

- [ ] **Step 1: Write the failing tests** (`django.test.TestCase`):

```python
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
```

- [ ] **Step 2: Run** `TEST library.test_recommender_build`. Expected: `ImportError` for `BookRecommendation`.
- [ ] **Step 3: Add the model and the two settings.**
- [ ] **Step 4: Create the migration.** From `backend/`: `PYTHONPATH="C:/github25/recommender-test-settings" C:/github25/bookly-lms/backend/venv/Scripts/python.exe manage.py makemigrations library --name bookrecommendation --settings=recommender_pg`. Expected: one new file creating only `BookRecommendation`. If it contains any other operation, stop and report.
- [ ] **Step 5: Run** `TEST library.test_recommender_build`. Expected: 5 pass.
- [ ] **Step 6: Commit** with message `Add book_recommendations table and threshold settings`.

---

### Task 3: Build

**Files:**
- Create: `backend/library/recommender/build.py`, `backend/library/management/__init__.py`, `backend/library/management/commands/__init__.py`, `backend/library/management/commands/rebuild_recommendations.py`
- Test: `backend/library/test_recommender_build.py` (append)

**Interfaces:**
- Consumes: `prepare`, `Document` (Task 1); `STOP_WORDS`; `BookRecommendation` (Task 2).
- Produces, in `build.py`:
  - `TOP_K = 12`, `MAX_TERMS = 3`, `CHUNK_ROWS = 500`, `LOCK_KEY = 74010011`
  - `make_vectorizer() -> TfidfVectorizer` (the only place the vectorizer is configured)
  - `@dataclass class Catalog: books: list[Books]; documents: list[Document]; works: int; vectorizer: TfidfVectorizer | None; matrix: scipy.sparse.csr_matrix | None` (`vectorizer` and `matrix` are `None` when no vocabulary could be learned)
  - `load_catalog() -> Catalog`: non-archived `Books` ordered by id, each prepared with `prepare(title, author, tags, description, call_number)`; fit on one representative per work (longest `description_length`, then newest `year_published` as int with non-numeric as 0, then lowest id); transform every row; catch `ValueError` from fitting.
  - `pair_contributions(catalog: Catalog, i: int, j: int) -> list[tuple[str, float]]`: every shared term with `a_t × b_t`, sorted by contribution descending then term ascending.
  - `@dataclass(frozen=True) class BuildStats: items: int; works: int; vocabulary: int; pairs: int; seconds: float`
  - `rebuild_recommendations() -> BuildStats`
- `rebuild_recommendations` steps, all inside one `transaction.atomic()`: run `SELECT pg_advisory_xact_lock(%s)` with `LOCK_KEY`, then call `load_catalog()` (after the lock); for row chunks of `CHUNK_ROWS` compute `(matrix[chunk] @ matrix.T).toarray()`; per title drop itself, titles with the same `work_key` and scores `<= 0`; order by score descending then candidate id ascending; keep `TOP_K`; `matched_terms` = first `MAX_TERMS` of `pair_contributions` as `{"term", "label", "weight"}` where `label` comes from either document's `labels` (author names and Dewey subject names), else the term; delete all `BookRecommendation` rows and `bulk_create` the new ones; log the stats at INFO with `logging.getLogger("library.recommender")`.
- The command prints one line: `items=<n> works=<n> vocabulary=<n> pairs=<n> seconds=<x.xx>`.

- [ ] **Step 1: Write the failing tests** (append to `test_recommender_build.py`):

```python
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
```

- [ ] **Step 2: Run** `TEST library.test_recommender_build`. Expected: import errors for `library.recommender.build`.
- [ ] **Step 3: Implement** `build.py` and the command per the Interfaces block.
- [ ] **Step 4: Run** `TEST library.test_recommender_build`. Expected: all pass. If `test_expected_top_matches` fails, print the rows and report; do not change the fixture to fit.
- [ ] **Step 5: Commit** with message `Add recommendation build and rebuild command`.

---

### Task 4: Availability, serving and the endpoint

**Files:**
- Modify: `backend/library/copies.py`, `backend/library/views.py`, `backend/library/urls.py`, `backend/library/serializers.py` (comment only: `views.with_availability` → `copies.with_availability`)
- Create: `backend/library/recommender/serve.py`
- Test: `backend/library/test_recommender_api.py`

**Interfaces:**
- Consumes: `BookRecommendation`, the two settings (Task 2); `RecommenderFixtures`.
- Produces, in `copies.py`:
  - `with_availability(copies_qs)`: moved unchanged from `views.py`; `views.py` imports it from `.copies`.
  - `catalog_books(books_qs)`: `with_copy_counts(books_qs)` plus the `listed_copies` prefetch `get_books` builds today. `get_books` becomes `catalog_books(Books.objects.filter(is_archived=False))`.
  - `AVAILABLE = "available"`, `ALL_OUT = "all_out"`, `HIDDEN = "hidden"`
  - `title_availability(book_ids) -> dict[int, str]`: one query. `AVAILABLE` when the title has at least one copy in `available_copies()`; `ALL_OUT` when it has at least one non-archived copy in good condition but none available; `HIDDEN` otherwise. Ids not found are absent from the result.
- Produces, in `serve.py`:
  - `DEFAULT_MIN_SCORE = 0.10`, `MAX_CARDS = 4`
  - `min_score(item_type: str) -> float`: for `ItemType.THESIS` use `settings.RECOMMENDER_MIN_SCORE_THESIS` when it is non-blank, otherwise `settings.RECOMMENDER_MIN_SCORE`. A value that is not a float in `[0, 1]` logs a warning on `library.recommender` and returns `DEFAULT_MIN_SCORE`.
  - `recommendations_for(book: Books, include_score: bool) -> list[dict]`: saved rows for `book` in rank order with `score >= min_score(book.item_type)` and a non-archived `recommended`; drop `HIDDEN`; first `MAX_CARDS`. Each dict: `{"book": <BooksSerializer data via catalog_books>, "availability": ..., "reason": [label, ...]}` plus `"score": round(score, 4)` only when `include_score`.
- Produces: view `get_recommendations` (`GET`, `[IsAuthenticated]`) at `path('getRecommendations/', views.get_recommendations, name='get_recommendations')`. `book_id` comes from `request.query_params`. Missing or non-integer → 400 `{"message": "Missing book_id"}`; unknown or archived → 404 `{"message": "Book not found"}`; else 200 `{"data": recommendations_for(book, include_score=request.user.role == RoleChoices.ADMIN)}`.

- [ ] **Step 1: Write the failing tests.** Rows are created directly so scores are exact.

```python
class RecommendationApiTests(RecommenderFixtures, TestCase):
    URL = "/getRecommendations/"
    def setUp(self):
        self.viewed = self.make_book("001.V", "Compilers")
        self.others = [self.make_book(f"001.{n}", f"Other {n}") for n in range(6)]
        for rank, (other, score) in enumerate(zip(self.others, [0.50, 0.40, 0.30, 0.20, 0.10, 0.05]), start=1):
            BookRecommendation.objects.create(book=self.viewed, recommended=other, rank=rank, score=score,
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
    def test_threshold_is_inclusive(self):                    # Review Focus 3
        self.assertEqual(self.ids(self.get()), [b.id for b in self.others[:3]])
    def test_invalid_threshold_falls_back_to_default(self):   # Review Focus 3
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
        BorrowRecords.objects.create(user=self.student_user.userprofile, copy=copy, status=StatusChoices.PENDING)
        self.assertEqual(self.get().data["data"][0]["availability"], "all_out")
    def test_lost_damaged_archived_or_no_copies_are_hidden(self):   # Review Focus 2
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
        client = APIClient(); client.force_authenticate(self.make_user("u"))
        book = client.get("/getBooks/").data["data"][0]
        self.assertEqual((book["total_copies"], book["available_copies"], len(book["copies"])), (2, 2, 2))
```

Adjust `self.student_user.userprofile` to the real reverse accessor name from `accounts.models.UserProfile.user` if it differs.

- [ ] **Step 2: Run** `TEST library.test_recommender_api`. Expected: 404s and import errors.
- [ ] **Step 3: Implement** the `copies.py` additions, `serve.py`, the view and the URL.
- [ ] **Step 4: Run** `TEST library.test_recommender_api library.test_book_copy library.tests`. Expected: all pass (the move of `with_availability` must not break existing tests).
- [ ] **Step 5: Commit** with message `Add recommendations endpoint with copy availability`.

---

### Task 5: Rebuild on catalog changes

**Files:**
- Modify: `backend/library/views.py` (`add_books`, `edit_book`, `remove_book`)
- Test: `backend/library/test_recommender_refresh.py`

**Interfaces:**
- Consumes: `rebuild_recommendations` (Task 3), imported into `views.py` as `from .recommender.build import rebuild_recommendations`.
- `addBook/` accepts only multipart form data (cover upload). Post with `format="multipart"` and send `tags` as `json.dumps([...])`, as the frontend does. `editBook/`, `removeBook/`, `addCopy/` and `editCopy/` still take JSON.
- Produces: `views._refresh_recommendations() -> None`: calls `rebuild_recommendations()`; on any `Exception` logs it with `logger.exception` on `library.recommender` and returns normally.
- Call sites: `add_books` after a successful create and after un-archiving; `remove_book` after archiving; `edit_book` after `book.save()` only when any of `title`, `author`, `tags`, `description` differs from its value before the edit. No copy endpoint and no loan endpoint calls it.

- [ ] **Step 1: Write the failing tests.** Patch `library.views.rebuild_recommendations` with `unittest.mock.patch`; use an admin `APIClient` (these endpoints are admin-only on main since `9a7778d`).

```python
class RefreshTests(RecommenderFixtures, TestCase):
    NEW = {"call_number": "001.N1", "isbn": "9780000000001", "title": "New Title", "author": "Ana Cruz",
           "publisher": "P", "year_published": "2020", "pages": "10", "item_type": "book"}
    # setUp: self.client = admin APIClient; self.book = self.make_book("001.A1", "Compilers", "Alfred V. Aho", ["Compilers"], "parsing")
    def test_add_rebuilds(self, rebuild):            # POST /addBook/ self.NEW (format="multipart") -> 201, rebuild called once
    def test_unarchive_through_add_rebuilds(self, rebuild):   # archived title with same call_number+isbn -> 200, called once
    def test_invalid_add_does_not_rebuild(self, rebuild):     # POST /addBook/ {} -> 400, not called
    def test_remove_rebuilds(self, rebuild):         # POST /removeBook/ {"book_id": id} -> 200, called once
    def test_text_edit_rebuilds(self, rebuild):      # one subTest per field: title, author, tags, description
    def test_non_text_edit_does_not_rebuild(self, rebuild):   # PUT /editBook/ {"book_id": id, "pages": "999", "publisher": "X"} -> 200, not called
    def test_resubmitting_same_text_does_not_rebuild(self, rebuild):  # PUT with the current title/author/tags/description -> not called
    def test_copy_changes_do_not_rebuild(self, rebuild):      # POST /addCopy/ {"book_id": id}; PUT /editCopy/ condition=lost -> not called
    def test_failed_rebuild_does_not_fail_the_save(self, rebuild):
        rebuild.side_effect = RuntimeError("boom")
        with self.assertLogs("library.recommender", level="ERROR"):
            response = self.client.put("/editBook/", {"book_id": self.book.id, "title": "Compilers II"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.book.refresh_from_db(); self.assertEqual(self.book.title, "Compilers II")

class RefreshIntegrationTests(RecommenderFixtures, TestCase):
    def test_new_similar_title_appears_after_add(self):       # black-box case RC-08, no mocking
        # two existing titles sharing words; POST /addBook/ a third sharing them;
        # then BookRecommendation.objects.filter(recommended__call_number="001.N1").exists() is True
```

Each stub line above is a full test: the comment gives the request and the two assertions (status code; `rebuild.assert_called_once()` or `rebuild.assert_not_called()`). Read `edit_copy`'s request fields from `views.py` before writing `test_copy_changes_do_not_rebuild`.

- [ ] **Step 2: Run** `TEST library.test_recommender_refresh`. Expected: failures (`rebuild` never called).
- [ ] **Step 3: Implement** `_refresh_recommendations` and the call sites.
- [ ] **Step 4: Run** `TEST library`. Expected: the whole suite passes (existing add/edit/remove tests now run a real rebuild).
- [ ] **Step 5: Commit** with message `Rebuild recommendations when the catalog text changes`.

---

### Task 6: Judging sheet export (Tool 1)

**Files:**
- Create: `backend/library/recommender/evaluation.py`, `backend/library/management/commands/export_judging_sheet.py`
- Test: `backend/library/test_recommender_evaluation.py`

**Interfaces:**
- Consumes: `BookRecommendation`; `clean_text` (Task 1).
- Produces, in `evaluation.py`:
  - `SHEET_COLUMNS = ["pair", "viewed_title", "viewed_author", "viewed_type", "viewed_description", "candidate_title", "candidate_author", "candidate_type", "candidate_description", "good"]`
  - `KEY_COLUMNS = ["pair", "viewed_id", "candidate_id", "viewed_type", "score", "rank", "group"]`
  - `@dataclass(frozen=True) class KeyRow: pair: int; viewed_id: int; candidate_id: int; viewed_type: str; score: float; rank: int; group: str`
  - `ensure_outside_repo(path) -> pathlib.Path`: resolves the path; raises `ValueError` when it is inside `settings.BASE_DIR.parent` (the repository root).
  - `sample_pairs(items: int, per_item: int, seed: int) -> list[KeyRow]`: eligible titles are non-archived with at least one saved row, ordered by id. With `random.Random(seed)`: per `item_type`, quota = `round(items × share)` adjusted on the largest type so the total is `min(items, eligible)`; sample each quota; shuffle the sampled titles; the first `ceil(n / 2)` are group `"A"`, the rest `"B"`; rows = each title's saved rows with `rank <= per_item` and a non-archived candidate; shuffle the rows; number them `pair = 1..n`.
  - `write_judging_files(rows: list[KeyRow], out_dir) -> tuple[Path, Path]`: writes `judging_sheet.csv` and `judging_key.csv` with `encoding="utf-8-sig"`, `newline=""`. Descriptions use `clean_text` cut to 300 characters. A text cell starting with `=`, `+`, `-` or `@` gets a leading `'`. `good` is empty.
  - `read_key(path) -> list[KeyRow]`
- Command: `export_judging_sheet --items 30 --per-item 8 --seed 42 --out <dir>` (`--out` required). A path inside the repository raises `CommandError`. Prints the two file paths and the number of pairs and items per group.

- [ ] **Step 1: Write the failing tests.** Use `tempfile.TemporaryDirectory()` for output.

```python
class JudgingSheetTests(RecommenderFixtures, TestCase):
    def setUp(self):
        # self.out = a temp directory outside the repository.
        # 8 books + 2 theses; each has 3 saved rows (ranks 1-3, scores 0.30, 0.20, 0.10) pointing at the next
        # three of those ten titles, wrapping around. self.no_rows = an extra title with no saved rows.
        # One more title named "=HYPERLINK(1)" with no saved rows of its own, saved as the first book's rank 4
        # candidate (score 0.05).
    def test_same_seed_same_sample(self):
        self.assertEqual(sample_pairs(6, 2, seed=42), sample_pairs(6, 2, seed=42))
        self.assertNotEqual(sample_pairs(6, 2, seed=42), sample_pairs(6, 2, seed=7))
    def test_sample_size_groups_and_strata(self):
        rows = sample_pairs(5, 2, seed=1)
        viewed = {r.viewed_id for r in rows}
        self.assertEqual(len(viewed), 5)
        self.assertEqual(collections.Counter(r.viewed_type for r in {(r.viewed_id, r.viewed_type) for r in rows}),
                         {"book": 4, "thesis": 1})
        groups = {r.viewed_id: r.group for r in rows}
        self.assertEqual(collections.Counter(groups.values()), {"A": 3, "B": 2})
        self.assertTrue(all(r.rank <= 2 for r in rows))
        self.assertEqual(sorted(r.pair for r in rows), list(range(1, len(rows) + 1)))
    def test_titles_without_saved_rows_are_never_sampled(self):
        self.assertNotIn(self.no_rows.id, {r.viewed_id for r in sample_pairs(50, 8, seed=3)})
    def test_asking_for_more_than_exist_returns_all_eligible(self):
        self.assertEqual(len({r.viewed_id for r in sample_pairs(50, 8, seed=3)}), 10)
    def test_sheet_is_blind_and_key_holds_scores(self):
        sheet, key = write_judging_files(sample_pairs(6, 2, seed=42), self.out)
        with open(sheet, encoding="utf-8-sig", newline="") as f: sheet_rows = list(csv.DictReader(f))
        self.assertEqual(list(sheet_rows[0]), SHEET_COLUMNS)
        self.assertTrue(all(row["good"] == "" for row in sheet_rows))
        self.assertFalse({"score", "rank", "group"} & set(sheet_rows[0]))
        self.assertEqual(read_key(key), sample_pairs(6, 2, seed=42))
    def test_formula_like_cells_are_neutralised(self):        # Review Focus 4
        sheet, _ = write_judging_files(sample_pairs(50, 8, seed=3), self.out)
        text = open(sheet, encoding="utf-8-sig").read()
        self.assertIn("'=HYPERLINK(1)", text)
        self.assertNotIn(",=HYPERLINK(1)", text)
    def test_out_inside_repository_is_refused(self):
        with self.assertRaises(ValueError):
            ensure_outside_repo(settings.BASE_DIR / "judging")
        with self.assertRaises(CommandError):
            call_command("export_judging_sheet", out=str(settings.BASE_DIR.parent / "docs"))
    def test_command_writes_both_files(self):
        call_command("export_judging_sheet", items=6, per_item=2, seed=42, out=self.out, stdout=io.StringIO())
        self.assertEqual(sorted(os.listdir(self.out)), ["judging_key.csv", "judging_sheet.csv"])
```

- [ ] **Step 2: Run** `TEST library.test_recommender_evaluation`. Expected: import errors.
- [ ] **Step 3: Implement** the functions and the command.
- [ ] **Step 4: Run** `TEST library.test_recommender_evaluation`. Expected: all pass.
- [ ] **Step 5: Commit** with message `Add blind judging sheet export`.

---

### Task 7: Grading and pair explanation (Tools 2 and 3)

**Files:**
- Modify: `backend/library/recommender/evaluation.py`
- Create: `backend/library/management/commands/evaluate_recommender.py`, `explain_recommendation.py`
- Test: `backend/library/test_recommender_evaluation.py` (append)

**Interfaces:**
- Consumes: `KeyRow`, `read_key`, `ensure_outside_repo` (Task 6); `load_catalog`, `pair_contributions` (Task 3).
- Produces, in `evaluation.py`:
  - `BAND_WIDTH = 0.05`, `GOOD_SHARE = 0.70`, `MIN_BAND_PAIRS = 5`
  - `majority_votes(sheet_paths) -> dict[int, bool]`: read each sheet with `utf-8-sig`; use only the `pair` and `good` columns; `y`/`yes` and `n`/`no` after `strip().lower()` are votes, anything else is no vote; a pair with no votes is absent; value is `yes > no` (a tie is `False`).
  - `@dataclass(frozen=True) class Band: low: float; pairs: int; good: int` with property `share -> float`
  - `band_table(rows, votes, viewed_type=None) -> list[Band]`: group `"A"` rows that have a vote (pairs in `votes` but not in `rows` are ignored); band index `min(int(score / BAND_WIDTH + 1e-9), 19)`; `low = round(index * BAND_WIDTH, 2)`; only non-empty bands, ascending.
  - `suggest_tau(bands) -> float | None`: `low` of the lowest band with `pairs >= MIN_BAND_PAIRS` and `share >= GOOD_SHARE`.
  - `precision_at_4(rows, votes, tau, tau_thesis=None) -> tuple[float | None, int]`: group `"B"`; per viewed title, rows with `score >= τ` (τ by `viewed_type`) ordered by rank, first 4, voted ones only; precision = good ÷ shown; titles with nothing shown are skipped; returns (mean, titles counted), `(None, 0)` when none.
  - `coverage(tau, tau_thesis=None) -> float`: share of non-archived `Books` with at least one saved row whose `score >= τ` for that title's type; `0.0` for an empty catalog.
  - `top4_scores() -> list[tuple[int, str, int, float]]`: `(viewed_id, viewed_type, rank, score)` for ranks 1–4.
  - `explain_pair(book_id: int, candidate_id: int) -> dict`: `{"score": float, "terms": [{"term", "tf_a", "tf_b", "idf", "weight_a", "weight_b", "contribution"}]}`; `tf` from `vectorizer.build_analyzer()` counts, `weight` = the normalized matrix value; raises `ValueError` when either title is archived, missing, or there is no vocabulary.
- Commands:
  - `evaluate_recommender --key <file> --sheet <file> [--sheet ...] --out <dir> [--tau X] [--tau-thesis Y]`: prints the band table for all, books and theses with each suggested τ; precision@4 and coverage at `--tau` (default: the all-pairs suggestion; if there is none, print that no band qualified and skip precision); writes `bands.csv` and `top4_scores.csv` to `--out` (outside the repository).
  - `explain_recommendation <book_id> <candidate_id>`: prints one line per shared term and `TOTAL SCORE = <x.xxxx>`; a `ValueError` becomes `CommandError`.

- [ ] **Step 1: Write the failing tests.** Grading tests build `KeyRow` lists by hand (no database):

```python
def key(pair, viewed, score, rank, group, viewed_type="book"):
    return KeyRow(pair, viewed, 1000 + pair, viewed_type, score, rank, group)

class GradingTests(SimpleTestCase):
    def write_sheet(self, votes, bom=True, extra_column=False):   # returns a temp CSV path; votes = {pair: "Y"/"N"/""}
    def test_majority_and_ties(self):
        a = self.write_sheet({1: "Y", 2: "Y", 3: "N", 4: ""})
        b = self.write_sheet({1: "Y", 2: "N", 3: "N", 4: ""})
        c = self.write_sheet({1: "N", 2: "", 3: "Y", 4: ""})
        self.assertEqual(majority_votes([a, b, c]), {1: True, 2: False, 3: False})   # 2 is a 1-1 tie; 4 has no votes
    def test_excel_style_sheet_is_accepted(self):             # Review Focus 5
        path = self.write_sheet({2: " yes ", 1: "NO", 99: "y"}, bom=True, extra_column=True)
        self.assertEqual(majority_votes([path]), {2: True, 1: False, 99: True})
        self.assertEqual(band_table([key(1, 1, 0.12, 1, "A"), key(2, 1, 0.13, 2, "A")], majority_votes([path])),
                         [Band(0.10, 2, 1)])                   # pair 99 is not in the key and is ignored
    def test_band_table_and_suggestion(self):
        rows = ([key(p, 1, 0.02, 1, "A") for p in (1, 2)]                      # 2 pairs, both good: too few to count
                + [key(p, 2, 0.07, 1, "A") for p in range(3, 8)]               # 5 pairs, 2 good
                + [key(p, 3, 0.12, 1, "A") for p in range(8, 13)]              # 5 pairs, 4 good
                + [key(13, 4, 0.12, 1, "B")])                                  # group B is not used here
        good = {1, 2, 3, 4, 8, 9, 10, 11, 13}
        votes = {p: p in good for p in range(1, 14)}
        bands = band_table(rows, votes)
        self.assertEqual(bands, [Band(0.0, 2, 2), Band(0.05, 5, 2), Band(0.10, 5, 4)])
        self.assertAlmostEqual(suggest_tau(bands), 0.10)
        self.assertIsNone(suggest_tau(bands[:2]))
    def test_band_edges(self):
        rows = [key(1, 1, 0.05, 1, "A"), key(2, 1, 0.15, 2, "A"), key(3, 1, 1.0, 3, "A")]
        self.assertEqual([b.low for b in band_table(rows, {1: True, 2: True, 3: True})], [0.05, 0.15, 0.95])
    def test_precision_at_4(self):
        rows = ([key(1, 1, 0.40, 1, "B"), key(2, 1, 0.30, 2, "B"), key(3, 1, 0.20, 3, "B"), key(4, 1, 0.05, 4, "B")]
                + [key(5, 2, 0.50, 1, "B"), key(6, 2, 0.12, 2, "B"), key(7, 2, 0.11, 3, "B"),
                   key(8, 2, 0.105, 4, "B"), key(9, 2, 0.101, 5, "B")]
                + [key(10, 3, 0.05, 1, "B"), key(11, 3, 0.02, 2, "B")]
                + [key(12, 4, 0.90, 1, "A")])
        votes = {1: True, 2: True, 3: False, 4: True, 5: False, 6: True, 7: True, 8: True, 9: True,
                 10: True, 11: True, 12: True}
        mean, counted = precision_at_4(rows, votes, tau=0.10)
        self.assertAlmostEqual(mean, (2 / 3 + 3 / 4) / 2)      # title 3 shows nothing; title 4 is group A
        self.assertEqual(counted, 2)
        self.assertEqual(precision_at_4(rows, votes, tau=0.95), (None, 0))
    def test_thesis_threshold_in_precision(self):
        rows = [key(1, 1, 0.20, 1, "B", "thesis"), key(2, 1, 0.50, 2, "B", "thesis")]
        self.assertEqual(precision_at_4(rows, {1: False, 2: True}, tau=0.10, tau_thesis=0.40), (1.0, 1))

class CoverageAndExplainTests(RecommenderFixtures, TestCase):
    # setUp: the BuildTests catalog from Task 3 (copy its setUp), then rebuild_recommendations()
    def test_coverage_counts_every_non_archived_title(self):
        # 9 non-archived titles; Z has no rows. At tau=0.0 coverage == 8/9. At tau=1.01 coverage == 0.0.
    def test_explanation_adds_up(self):
        result = explain_pair(self.t.id, self.t2.id)
        row = BookRecommendation.objects.get(book=self.t, recommended=self.t2)
        self.assertAlmostEqual(result["score"], row.score, delta=1e-9)
        self.assertAlmostEqual(sum(t["contribution"] for t in result["terms"]), row.score, delta=1e-9)
        first = result["terms"][0]
        self.assertAlmostEqual(first["weight_a"] * first["weight_b"], first["contribution"], delta=1e-12)
        self.assertGreaterEqual(first["tf_a"], 1)
    def test_explaining_an_archived_title_fails_cleanly(self):
        with self.assertRaises(ValueError): explain_pair(self.x.id, self.a.id)
        with self.assertRaises(CommandError): call_command("explain_recommendation", self.x.id, self.a.id)
    def test_explain_command_prints_total(self):
        out = io.StringIO(); call_command("explain_recommendation", self.t.id, self.t2.id, stdout=out)
        self.assertRegex(out.getvalue(), r"TOTAL SCORE = 0\.\d{4}")
    def test_evaluate_command_end_to_end(self):
        # export with seed 42 into a temp dir, fill every "good" cell with Y, run evaluate_recommender with --tau 0.0;
        # assert the output contains "precision@4" and "coverage", and bands.csv and top4_scores.csv exist.
```

- [ ] **Step 2: Run** `TEST library.test_recommender_evaluation`. Expected: import errors for the new names.
- [ ] **Step 3: Implement** the functions and both commands.
- [ ] **Step 4: Run** `TEST library.test_recommender_evaluation`. Expected: all pass.
- [ ] **Step 5: Commit** with message `Add recommender grading and pair explanation commands`.

---

### Task 8: Open Library autofill: work description and tag cap

**Files:**
- Modify: `backend/books/views.py` (`autofillBookInfo`)
- Test: `backend/books/tests.py`

**Interfaces:**
- Consumes: `MAX_TAGS` from `library.recommender.preprocess` (Task 1).
- Produces: the same response shape as today, except `description` comes from the Open Library **work** record (`/works/<id>.json`, found through the edition record's `works[0]["key"]`) when it has one, else from the edition record, else `""` (never the text `"None"`); `tags` holds at most `MAX_TAGS` subject names in Open Library's order (today it is an unordered `set`, so the order changes between calls).

- [ ] **Step 1: Write the failing tests.** Patch `books.views.requests.get` with a fake that answers by URL: `api/books?bibkeys=ISBN:<isbn>` → `{"ISBN:<isbn>": {"key": "/books/OL1M", "title": "T", "subjects": [{"name": f"S{n}"} for n in range(20)], ...}}`; `/books/OL1M.json` → `{"works": [{"key": "/works/OL9W"}]}` (with or without a `description`); `/works/OL9W.json` → `{"description": {"value": "From the work"}}` or `{}`.

```python
class AutofillTests(TestCase):
    # setUp: authenticated APIClient
    def test_description_comes_from_the_work_record(self):      # work has one -> "From the work"
    def test_falls_back_to_the_edition_description(self):       # work has none, edition "From the edition" -> that
    def test_no_description_is_an_empty_string(self):           # neither has one -> "" (not "None")
    def test_tags_are_capped_and_keep_open_library_order(self): # tags == ["S0", ..., "S14"]
    def test_unknown_isbn_is_404(self):                         # bibkeys answer {} -> 404 "No book found"
```

Each stub line is a full test: call `GET /autofill/?isbn=9780000000001` and assert the status code and the field named in the comment.

- [ ] **Step 2: Run** `TEST books`. Expected: the new tests fail.
- [ ] **Step 3: Implement** the change in `autofillBookInfo`. Keep the existing 5-second timeouts and error responses; a failing work-record request falls back to the edition description instead of returning 502.
- [ ] **Step 4: Run** `TEST books library`. Expected: all pass.
- [ ] **Step 5: Commit** with message `Read autofill descriptions from the Open Library work record`.

---

### Task 9: Recommendations in the designer's slot

**Files:**
- Modify: `frontend/src/api/books.js`, `frontend/src/components/library/showbook/ShowBook.jsx`, `frontend/src/pages/library/Library.jsx`
- Create: `frontend/src/components/library/showbook/useRecommendations.js`, `frontend/src/components/library/showbook/RecommendedBooks.jsx`, `docs/recommender-designer-handoff.md`

**Interfaces:**
- Consumes: `GET /getRecommendations/?book_id=` (Task 4). Through `returnData`, the result is `{ status, data }` where `data` is the item list; each item has `book`, `availability`, `reason` and, for admins, `score`.
- Consumes: the existing `BookPanel` (`frontend/src/components/library/BookPanel.jsx`, props `setActiveBook`, `setShowBook`, `book`, `status`, `hover`) and the designer's slot in `ShowBook.jsx` on main: `<div className={styles.recommendationContainer}>` › `<div className={styles.recommendations}>`, rendered only when `role !== "admin"`, currently holding a commented-out `BookPanel` map and a `comingSoonContainer` placeholder.
- Produces:
  - `getRecommendations(bookId)` in `books.js`, same shape as `getBooks` (uses `authFetch`, returns `{"status": 500, ...}` on a thrown error).
  - `useRecommendations(bookId) -> { items, loading, error }`: fetches when `bookId` changes; `items` is `resp.data` when `resp.status === 200`, otherwise `error` is `true` and the hook calls `console.error` once; a response for an older `bookId` is ignored.
  - `<RecommendedBooks bookId setActiveBook setShowBook />`: renders the contents of the `.recommendations` div.
  - `ShowBook` gains a `setActiveBook` prop; `Library.jsx` passes its `setActiveBook`.

Behavior:
- Results: one `<BookPanel key={item.book.id} book={item.book} setActiveBook={setActiveBook} setShowBook={setShowBook} />` per item (at most 4, in API order). Clicking a card opens that item in the same modal and loads its recommendations.
- Empty (`items` is `[]`): the designer's `comingSoonContainer` markup and `libby` image with the text `No similar items yet.`
- Loading and error: render nothing inside `.recommendations` (the slot keeps its size).
- Keep the `role !== "admin"` condition and the commented header line exactly as they are. Remove only the commented `BookPanel` map and the `{/* TEMP*/}` placeholder that the new component replaces.
- `availability`, `reason` and `score` are not shown in this task: `BookPanel` has no place for them yet. The handoff note lists them for the designer.
- No CSS file is created or edited. The slot's `/*TEMP*/` styles (50% opacity, centered content) stay for the designer to finish.

`docs/recommender-designer-handoff.md` contains: where the slot is; that it now shows up to 4 `BookPanel` cards or the empty message `No similar items yet.`; the fields the API already returns for each card and that are not shown yet (Book/Thesis from `book.item_type`, `availability` = `available` or `all_out` with the labels `Available` / `All copies out`, `reason` as `Shares: …`, and `score` for admins); that theses usually have no cover and `BookPanel` shows an empty image for them; that the `/*TEMP*/` styles on `.recommendationContainer` and `.recommendations` are still in place; whether admins should see the row (with scores) is the designer's decision; and that `useRecommendations.js` holds the logic and needs no change.

- [ ] **Step 1: Install dependencies** if the worktree has no `frontend/node_modules`: `npm ci` in `frontend/`. Run `npm run lint` and note any errors that already exist.
- [ ] **Step 2: Implement** the API helper, the hook, `RecommendedBooks.jsx`, the `ShowBook` and `Library` prop changes and the handoff note.
- [ ] **Step 3: Verify.** In `frontend/`: `npm run lint` (expected: no errors in the new or touched files beyond those noted in Step 1) and `npm run build` (expected: `built in`).
- [ ] **Step 4: Check no stylesheet changed.** `git diff --stat -- '*.css'` prints nothing.
- [ ] **Step 5: Commit** with message `Show recommended books in the view-book modal`. Keep this as its own commit: it is the part the designer signs off.

---

### Task 10: Operations notes and full verification

**Files:**
- Create: `backend/RECOMMENDER.md`

**Interfaces:**
- Consumes: everything above.

`backend/RECOMMENDER.md` (same style as `ADMIN_ANALYTICS.md`) covers: what the feature does in three sentences; the endpoint with a sample response for a student and for an admin; the two environment variables and their fallback; when rebuilds happen; the four commands with one example each; deploy steps (`pip install -r requirements.txt`, `migrate`, `rebuild_recommendations`, set `RECOMMENDER_MIN_SCORE` on the host); that `DEWEY_DIVISIONS` must be checked against OCLC's DDC 23 summaries before the defense; the privacy rule for judging files; the upgrade path when a rebuild takes more than about 5 seconds; and the black-box cases RC-01 to RC-11 from spec section 12.

- [ ] **Step 1: Write** `backend/RECOMMENDER.md`.
- [ ] **Step 2: Run the whole backend suite.** `TEST library accounts books`. Expected: the Task 0 baseline count plus the new tests, 0 failures.
- [ ] **Step 3: Time a build on realistic data.** In a `manage.py shell --settings=recommender_pg` session against the throwaway database (after `migrate --settings=recommender_pg`), create 300 titles with varied text and run `rebuild_recommendations()`. Record `BuildStats.seconds` in `RECOMMENDER.md`. Never run this against the live database.
- [ ] **Step 4: Black-box walk-through.** Start the backend with `runserver --settings=recommender_pg` and the frontend with `npm run dev` pointed at it (`VITE_API_URL`), create one admin and one student, add a handful of related titles through the app, and walk RC-01 to RC-11 as a student (the slot is student-only; RC-07 checks the admin score through the API response instead of the screen). Record pass or fail per case in `RECOMMENDER.md`. If a browser is not available to the worker, say so in the report and leave the table marked "not run"; do not mark cases as passed without running them.
- [ ] **Step 5: Commit** with message `Document recommender operations and test cases`.
- [ ] **Step 6: Report.** Summarize: test counts, the measured build time, which RC cases were run, the two commits a reviewer should look at first (Task 3 and Task 4), and what is still open: designer sign-off for the Task 9 commit, the team's check of `DEWEY_DIVISIONS` and the stop-word lists, the first τ from the team's judging round, and the live database needs `migrate` plus `rebuild_recommendations` at deploy time. Do not push or open a PR unless the user asks.
