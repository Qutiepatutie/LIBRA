# LIBRA "Books to recommend": TF-IDF + Cosine Similarity Recommender — Design

- **Date:** 2026-11-14
- **Status:** Approved 2026-11-16; next step is the implementation plan
- **Branch:** `feat/tfidf-recommender`
- **Source:** brainstorm record `LIBRA-TFIDF-Recommender-Brainstorm.pdf` (2026-11-10) plus the follow-up design session (2026-11-11 to 2026-11-14)

## 1. Goal and context

Add a **"Books to recommend"** row to the view-book modal. When a user views a catalog item (book or thesis), the row shows up to 4 similar items, computed with **TF-IDF and cosine similarity** as stated in the capstone methodology (Chapter 3, section 3.3.3). Every recommendation must be explainable (score and shared terms), and the system must support a reportable evaluation for Chapter 4.

### Success criteria

1. Viewing any item shows 0–4 recommended items, ordered by cosine similarity, each scoring at least τ.
2. An item never recommends itself or another edition of the same work.
3. Each card shows the Book/Thesis label, an availability badge and a reason line; admins also see the score.
4. Scores computed by the system match hand calculations using the revised Chapter 3 formulas.
5. New, edited and archived items are reflected immediately after the admin saves.
6. The team can export a blind judging sheet and compute τ, precision@4 and coverage from the filled sheets.

### Out of scope

- Personalized recommendations (from a student's borrowing history). Stated as a limitation and future work.
- Libby's chat recommender (LIBBY_PLAN.md Phase 4: embeddings, reranker, GPT). Separate feature.
- The **BookCopy** split (Books = title, BookCopy = physical copy). Gets its own spec. This design only depends on `Books` being one row per title and isolates availability in one function so it can switch to copies later.
- Importing the school's thesis file. Covered by the BookCopy / import work; this spec only defines how imported fields feed the recommender (section 4.4).
- A baseline comparison (random recommendations) in the evaluation.
- Field weighting (title or tags counted more than once). Plain concatenation, as in the paper.

## 2. Decisions

Numbers 1–10 follow the brainstorm record (question 5, "what counts as a liked book", was dropped with personalization).

| # | Topic | Decision |
|---|---|---|
| 1 | Method | TF-IDF + cosine similarity with scikit-learn. No LLMs or embeddings. |
| 2 | Input text | title + author tokens + cleaned tags + description |
| 3 | Formulas | scikit-learn `TfidfVectorizer` defaults (raw TF, smoothed IDF, L2 normalization); Chapter 3 is revised to match (section 10) |
| 4 | Recommendation input | item-to-item only: the currently viewed item |
| 6 | Stop words | scikit-learn English list ∪ custom library words ∪ ~15 Filipino function words ∪ thesis-title words, in one file |
| 7 | Authors | each author becomes one token (`alfred_aho`) |
| 8 | Books and theses | one mixed list ranked by score, with Book/Thesis labels |
| 9 | N and threshold | N = 4, minimum similarity τ; the row shows 0–4 cards with an empty state |
| 10 | Copies and editions | A: skip candidates of the same work (normalized title + author tokens); each work counts once for IDF |
| 11 | Data | the current 105 rows are the team's stand-in data; τ and evaluation are redone on the school's data |
| 12 | Tag cleaning | rule-based, in the pipeline (section 4.2) |
| 13 | Field weighting | none (plain concatenation) |
| 14 | Availability | rank by similarity only; badge "Available" / "All copies out"; hide titles whose every copy is lost or damaged |
| 15 | Choosing τ | judges rate real pairs blind; τ = lowest score band with ≥ 70% judged good |
| 16 | Judges | research team now (majority vote, stand-in data); librarian later (school data, final τ) |
| 17 | Evaluation | Part III(a) survey + precision@4 and coverage, split-half (one half picks τ, the other measures) |
| 18 | Explainability | students see the reason line; admins also see the score |
| 19 | Compute location | Approach 1: precomputed table rebuilt on catalog change |
| 20 | Theses | title + author + Program (as a tag); description used automatically if abstracts arrive later |
| 21 | Rare terms | `min_df=2`: terms in only one work are ignored |
| 22 | UI | plain version from existing styles only, isolated components; designer signs off before merge |

## 3. Architecture overview

```
Admin saves item ──► rebuild_recommendations()
                        │  1. load non-archived Books
                        │  2. preprocess → document text + work key      (preprocess.py)
                        │  3. fit TF-IDF on one representative per work
                        │  4. transform all rows, cosine in chunks
                        │  5. top 12 per item + reason terms
                        ▼
                 book_recommendations table  (12 rows per item)

Student opens modal ──► GET /library/getRecommendations/?book_id=…
                        │  read saved rows → filter τ, archived → availability
                        ▼
                 ≤ 4 items → RecommendedRow in ShowBook modal
```

Heavy work happens only when the catalog changes. Opening the modal reads saved rows (two queries, no math).

### Code layout

| Path | Responsibility |
|---|---|
| `backend/library/recommender/__init__.py` | package |
| `backend/library/recommender/stopwords.py` | `STOP_WORDS` = English list ∪ library ∪ Filipino ∪ thesis-title lists; each list a named constant so the paper can reproduce it |
| `backend/library/recommender/preprocess.py` | pure functions, no DB, no ML: placeholders, author tokens, tag cleaning, work key, document builder, program-to-tag helper |
| `backend/library/recommender/build.py` | `rebuild_recommendations() -> BuildStats` (vectorize, score, save, lock) |
| `backend/library/recommender/serve.py` | `recommendations_for(book, user)` and `availability_for(book_ids)` |
| `backend/library/recommender/evaluation.py` | sampling, judging sheet + key, grading, pair explanation |
| `backend/library/management/commands/rebuild_recommendations.py` | manual rebuild, prints stats |
| `backend/library/management/commands/export_judging_sheet.py` | Tool 1 |
| `backend/library/management/commands/evaluate_recommender.py` | Tool 2 |
| `backend/library/management/commands/explain_recommendation.py` | Tool 3 |
| `backend/library/models.py` | `BookRecommendation` model |
| `backend/library/migrations/0014_bookrecommendation.py` | new table (renumber if main moves) |
| `backend/library/views.py`, `urls.py` | `get_recommendations` view + rebuild hooks |
| `frontend/src/api/books.js` | `getRecommendations(bookId)` |
| `frontend/src/components/library/showbook/useRecommendations.js` | data hook |
| `frontend/src/components/library/showbook/RecommendedRow.jsx`, `RecommendedCard.jsx` | visible row (designer-owned look) |
| `frontend/src/styles/library/showBook/recommended.module.css` | the row's own styles |

## 4. Preprocessing (Section 1)

All functions in `preprocess.py` are pure and unit-testable with plain strings.

### 4.1 Fields

| Field | Use |
|---|---|
| `title` | in the text, as is |
| `author` | author tokens (4.3) |
| `tags` | cleaned (4.2); the "genre" |
| `description` | in the text unless it is a placeholder |
| `edition`, `publisher`, `year_published`, `pages`, `call_number` | not in the text |
| `item_type` | not in the text; Book/Thesis label only |
| `is_archived` | archived items are excluded from the build entirely |

**Placeholders:** after trimming and ignoring case, `none`, `none.`, `unknown`, `n/a` and the empty string count as empty.

### 4.2 Tag cleaning

A tag is dropped when it:

1. is a placeholder;
2. looks like a call number: Library of Congress style (`Qa76.76.c65 a37 2007`, `Bm545 .d3312 2002`) or Dewey style (`005.4/53`, `005.1`);
3. contains a letter outside the Latin script (Cyrillic, CJK, Arabic, etc.);
4. contains an underscore (`open_syllabus_project`).

Control characters are stripped (one stand-in tag ends in `\u001e 0`; the control character and the trailing fragment after it are removed). Remaining tags are de-duplicated ignoring case, keeping the first spelling. Latin-script foreign tags (`Programmation parallèle`, `Kompilatory`) are kept.

### 4.3 Author tokens

1. Split multiple authors on `;`, `&` and the word ` and `. (The school's thesis file has none of these: one author per master's/doctoral record, and `Surname, et al.` for every undergraduate record. The books' format is still to confirm.)
2. An author written as `Surname, et al.` gives **no token**: a lone surname cannot identify a person, and unrelated groups that share a surname would otherwise look similar.
3. `Last, First` → `First Last`, using only the first two comma-separated parts; anything after the second comma (credentials such as `MD, FPCP`) is ignored.
4. Drop single-letter initials (`V.`).
5. Lowercase, strip accents and punctuation, join words with `_`.

`"Alfred V. Aho"` and `"Aho, Alfred"` both give `alfred_aho`. The build keeps a token → display-name map (`alfred_aho` → `Alfred Aho`) for reason lines. A missing author gives no tokens. Because students usually write one thesis, `min_df=2` removes most thesis author tokens anyway; the rule matters mainly for books.

### 4.4 Theses and the Program column

The school's thesis file has `BARCODE NO.`, `TITLE`, `AUTHOR`, `Program`, `COPYRIGHT`, `CALL NO.`, `Date Accessioned`. No description or tags.

- The import puts the thesis's **program subject** into its `tags` via `program_subject(raw)`. The school writes programs as full names, not codes (51 distinct spellings in the sample), so the helper:
  1. applies a small typo map built from the sample (`PROGRAM_FIXES`: `Infromation` → `Information`, `Masrer` → `Master`, `Infromation of Technology` → `Information Technology`, `Business in Administration` → `Business Administration`);
  2. removes `Non-Thesis Track` and the leading degree words (`Bachelor/Master/Doctor`, `of Arts/Science/Philosophy … in`);
  3. splits on `Major in`, `with Specialization in` and `Medyor sa`, keeping each subject.

  Example: `Master of Arts in Education, Major in Educational Management` → tags `Education`, `Educational Management`.
- `description` stays empty until abstracts are available; they are used automatically when filled.
- Barcode and date accessioned are copy-level (BookCopy). COPYRIGHT → `year_published`, CALL NO. → `call_number`.

**What the school's sample contains** (`[FOR BS CS] LAGUNA THESIS AND DISSERTATION.xlsx`, profiled 2026-11-14):

| Sheet | Records | Notes |
|---|---|---|
| MASTER | 214 | 3 titles appear twice (2 copies, same call number, different barcodes); barcode `LRC-VI-A-MT-168` is used for two different theses (data error to report) |
| DOCTOR | 23 | 2 records carry `MT` call numbers |
| THESIS (undergraduate) | 40 | 38 Pharmacy, 2 Psychology; authors are `Surname, et al.` |

Import notes for the BookCopy/import work: the sheets contain many numbered empty rows; COPYRIGHT and Date Accessioned are Excel date serials in MASTER and DOCTOR (e.g. `43891` = 2020-03-01) but plain years in THESIS, and one value is `Hunyo 2023`. Despite the file name, there are no BS CS theses (one Master of Science in Computer Science, eleven Master in Information Technology).

**Title-only check (throwaway spike, pure-Python re-implementation of the same formulas on the 273 distinct works):** with title + program subject, every thesis has at least one match at τ up to 0.20 and 96% still do at 0.30. Thesis documents are short, so one or two shared words give high scores; thesis scores will run higher than book scores (books have long descriptions). Sample matches were topical for Pharmacy and Psychology; the main false links came from place names and broad program words such as "administration".

### 4.5 Same-work key and representatives

- **Work key:** normalized title (lowercase, accents and punctuation removed, spaces collapsed, trailing edition phrases such as `2nd ed.`, `11th edition`, `(3rd edition)` removed) + the sorted author tokens.
- **Representative per work:** longest non-placeholder description; tie → newest `year_published`; tie → lowest id.

### 4.6 Document text

`title + author tokens + cleaned tags + description`, joined with spaces. Empty fields add nothing.

### 4.7 Stop words

`STOP_WORDS = ENGLISH_STOP_WORDS ∪ LIBRARY_WORDS ∪ FILIPINO_WORDS ∪ THESIS_TITLE_WORDS ∪ PLACE_WORDS`

- `LIBRARY_WORDS` (starting list, team-maintained): study, research, researchers, respondents, thesis, chapter, book, edition.
- `FILIPINO_WORDS`: ang, ng, sa, mga, na, at, ay, ito, para, kung, si, ni, kay, nang, pa.
- `THESIS_TITLE_WORDS`: generic research-title words, from the word count of the 277 sample titles (number of titles containing each): selected 18, level 19, basis 18, evaluation 22, assessment 15, determination 13, implementation 12, development 16, impact 14, based 13, iii 15. ("among" is already in the English list.) The team confirms the final list; topical words such as feasibility, antioxidant and satisfaction stay.
- `PLACE_WORDS`: Philippine place words that describe where a study was done, not what it is about (city 48, pampanga 27, bulacan 16, angeles 13, san 14, marilao 10, region 17, province 11, district 11, plus others found in the titles such as caloocan). The team completes the list from the title word count. Justification for the paper: locale is not topic, and two unrelated studies in the same city should not look similar.

Each list keeps its counts in a comment so the paper's stop-word table can cite them.

The English list removes some real words (e.g. "system"); this is accepted because nearly every IT capstone title contains "system".

## 5. Build (Section 2)

`rebuild_recommendations()` runs inside one database transaction:

1. Take a Postgres transaction-level advisory lock (`pg_advisory_xact_lock` with a fixed key) so builds run one at a time. Read the catalog **after** the lock is held.
2. Load all non-archived `Books`; preprocess each (section 4).
3. Group by work key; choose representatives.
4. Fit `TfidfVectorizer(stop_words=STOP_WORDS, min_df=2)` on the representatives only; all other parameters stay at scikit-learn defaults.
5. Transform every non-archived row with the fitted vocabulary.
6. Compute cosine similarity as sparse dot products in chunks of 500 rows (vectors are already L2-normalized).
7. For each item: exclude itself, items with the same work key and scores of exactly 0; keep the top 12 by score, ties broken by lower candidate id.
8. For each kept pair, the per-term contribution is `a_t × b_t`; contributions sum to the score. Store the top 3 terms by contribution with display labels (author tokens shown as names).
9. Delete all rows of `book_recommendations` and bulk-insert the new ones.
10. Return `BuildStats`: items, works, vocabulary size, pairs saved, seconds. Log them.

**Edge case:** if the vectorizer learns no vocabulary (too few items or no shared terms), save an empty table, log the reason and return normally.

**Dependency:** `scikit-learn==1.9.1` (pulls numpy and scipy), added to `backend/requirements.txt` (UTF-16 LE with CRLF; keep the encoding) and `backend/dev-requirements.txt` (ASCII). The pinned version matches the one the methodology notes were checked against.

**Performance (estimates, to be measured):** < 0.1 s for 105 items; ~1–3 s for 5,000. Upgrade trigger in section 8.

## 6. Storage (Section 3)

Model `BookRecommendation`, table `book_recommendations`:

| Field | Type | Notes |
|---|---|---|
| `book` | FK → `Books`, `on_delete=CASCADE`, `related_name="recommendations"` | the viewed item |
| `recommended` | FK → `Books`, `on_delete=CASCADE`, `related_name="+"` | the suggestion |
| `rank` | `PositiveSmallIntegerField` | 1–12, 1 = best |
| `score` | `FloatField` | exact cosine similarity |
| `matched_terms` | `JSONField(default=list)` | ≤ 3 items: `{"term": "alfred_aho", "label": "Alfred Aho", "weight": 0.14}` |

Constraints:

- `UniqueConstraint(book, rank)` (also serves the rank-ordered lookup)
- `UniqueConstraint(book, recommended)`
- `CheckConstraint(~Q(book=F("recommended")))`

Not stored: τ, availability, and title/cover/type (read from `Books` at request time).

**τ setting:** `RECOMMENDER_MIN_SCORE` in Django settings, read from the environment variable of the same name. Default `0.10` (placeholder until the team's judging). A missing or unparsable value logs a warning and uses the default.

Size: 12 rows per item (60,000 rows for 5,000 items).

Like existing tables, the new table has Row Level Security off and is accessed only through Django. Enabling RLS on all public tables is a separate hardening task.

## 7. API (Section 4)

`GET /library/getRecommendations/?book_id=<id>`, `permission_classes=[IsAuthenticated]`.

Steps:

1. Parse `book_id` from query params; missing or not an integer → 400 `{"message": "Missing book_id"}`.
2. Unknown id or archived item → 404 `{"message": "Book not found"}`.
3. Read the item's saved rows in rank order with `select_related("recommended")`.
4. Keep rows with `score >= RECOMMENDER_MIN_SCORE` and a non-archived `recommended`.
5. `availability_for(ids)` returns, per id, one of:
   - `"hidden"`: today, `condition` is lost or damaged; after BookCopy, every copy is lost or damaged or the title has no copies;
   - `"all_out"`: today, the item has a borrow record with status Pending, Active, Due or Overdue (`StatusChoices.PENDING` + `user_analytics.OPEN_STATUSES`, the same rule `borrow_book` uses); after BookCopy, no good copy is free;
   - `"available"`: otherwise.

   One query for all candidates. This function is the only place that changes when BookCopy lands.
6. Drop `hidden`; return the first 4.

Response (200):

```json
{
  "data": [
    {
      "book": { "...": "same shape as getBooks (BooksSerializer)" },
      "availability": "available",
      "reason": ["logic", "programming", "parallel"],
      "score": 0.31
    }
  ]
}
```

- `score` is included only when `request.user.role == RoleChoices.ADMIN` (decided server-side from the authenticated account, as `IsAdminRole` does).
- `reason` holds display labels only.
- An empty `data` list means the empty state.

## 8. Refresh (Section 6)

| Trigger | Rebuild |
|---|---|
| `add_books` succeeds (new item or un-archived item) | yes |
| `remove_book` (archive) | yes |
| `edit_book` where `title`, `author`, `tags` or `description` changed | yes |
| `edit_book` changing only other fields (condition, pages, publisher, call number, item type, year) | no |
| Borrowing, approving, returning, cancelling | no (availability is read live) |
| Copy-level changes (after BookCopy) | no |

- Call `rebuild_recommendations()` explicitly in those views after the save succeeds. No Django signals (they would fire per row in bulk imports and the seed script).
- If the rebuild raises, log the exception and still return the normal success response; the previous table stays.
- `python manage.py rebuild_recommendations` prints the build stats. Run it after deploys, after the school-data import and after any data loaded directly into Supabase. `seed_data.py` calls it at the end.
- **Upgrade path (not built now):** when rebuilds regularly take more than ~5 seconds, move the rebuild out of the save request (run after the response or on a short schedule). The table and API stay the same.

## 9. UI (Section 5)

The user does not own the visual design; the designer does. Rules:

- No existing CSS file is edited. The row's look lives in its own components and CSS module, reusing only colors, fonts and spacing already used in the modal.
- The UI part merges only after the designer signs off or restyles it.

Changes to existing files (logic only):

| File | Change |
|---|---|
| `frontend/src/api/books.js` | add `getRecommendations(bookId)` |
| `ShowBook.jsx` | render `<RecommendedRow bookId={currBook.id} onSelectBook={onSelectBook} isAdmin={isAdmin} />` under `BookInfos`; hide it while `isEdit` |
| `pages/library/Library.jsx` | pass `onSelectBook={setActiveBook}` to `ShowBook` |

Row behavior:

- Heading "Books to recommend".
- **Loading:** 4 placeholder tiles.
- **Results:** up to 4 cards. Card: cover image, or a title tile when `cover_url` is empty; title (max 2 lines); `Book`/`Thesis` label; badge "Available" or "All copies out"; reason line `Shares: logic, programming, parallel`; `Score 0.31` for admins only (rendered only if `score` is present).
- **Empty:** "No similar items yet."
- **Error:** row hidden; error logged to the console. Viewing and borrowing are unaffected.
- **Click a card:** `onSelectBook(item.book)` opens that item in the same modal; its recommendations load.

Designer handoff note (delivered with the plain version): card fields, the four states, Figma frames 2165:2489 (row placement) and 2442:1490 (view-book variants), and the thesis title-tile requirement.

## 10. Evaluation tooling (Section 7)

### Tool 1: `export_judging_sheet --items 30 --per-item 8 --seed 42 --out <dir>`

1. Sample 30 non-archived items, stratified by `item_type` in proportion to the catalog, using the seed.
2. Take each item's top 8 saved candidates (ranks 1–8, ignoring τ); an item with fewer saved candidates contributes all it has.
3. Randomly assign items to group A (choose τ) or B (measure), 15 each.
4. Write `judging_sheet.csv` (shuffled rows: pair number, viewed item title/author/type/description excerpt, candidate the same, empty `Good (Y/N)`); no score, rank or group.
5. Write `judging_key.csv`: pair number → viewed id, candidate id, score, rank, group.
6. `--out` is required and must be outside the repository; the command refuses a path inside it.

### Tool 2: `evaluate_recommender --key <key.csv> --sheet <a.csv> [--sheet <b.csv> ...] [--tau <value>]`

- Combine sheets by majority vote per pair; a tie counts as not good. A blank answer is treated as no vote.
- **Group A:** score-band table in 0.05-wide bands (pairs, good, % good) and the suggested τ = lowest band with ≥ 70% good, reported for all pairs and separately by the viewed item's type (book, thesis). Thesis scores run higher than book scores (section 4.4), so if the two suggestions differ by more than one band the team may use a separate threshold for theses (`RECOMMENDER_MIN_SCORE_THESIS`, falling back to `RECOMMENDER_MIN_SCORE` when unset). This is decided after the first judging round.
- **Group B, at the given τ (or the suggestion):** per item, cards = candidates with score ≥ τ, top 4; precision = good ÷ shown; items with no cards are excluded from the mean. Report mean precision@4 and the number of items it covers. Availability is ignored.
- **Coverage:** over all non-archived items in `Books` (including items with no saved rows), the share with at least one saved candidate ≥ τ.
- **Histogram data:** CSV of every item's top-4 scores.
- Output: printed tables plus CSV files in the chosen output folder.

### Tool 3: `explain_recommendation <book_id> <candidate_id>`

Fits the same vectorizer as the build and prints, for every shared term: raw TF in each document, IDF, weight before and after L2 normalization, and contribution. The contributions sum to the score.

### Privacy

Judging sheets contain student thesis authors' names. They are written only outside the repository and never committed.

## 11. Edge cases (Section 8)

| Situation | Behavior |
|---|---|
| Table not built yet | empty state until `rebuild_recommendations` runs |
| No vocabulary learned | empty table, logged; no crash |
| Item with no usable terms | no recommendations; never recommended |
| All candidates filtered (τ, archived, hidden) | empty state |
| Recommended item archived after the last build | filtered at serve time |
| `RECOMMENDER_MIN_SCORE` missing or invalid | default 0.10 + warning |
| Equal scores | lower candidate id first |
| Same title, different authors | different works; may recommend each other |
| Missing author | no author tokens |
| Rebuild fails | admin save succeeds; old table kept; error logged |
| Concurrent saves | advisory lock serializes rebuilds |
| Client-side role tampered | score still omitted (server decides) |
| Filipino text | function words removed only; stated limitation |

## 12. Testing

Backend tests need Postgres (the SQLite test settings are broken by `RoomReservation`'s `ArrayField`; the advisory lock also needs Postgres). Use the throwaway local Postgres set up for this project.

1. **Preprocessing unit tests:** each placeholder, tag rule and author rule with real stand-in examples; work keys for `Calculus, 11th ed.` vs `Calculus (10th edition)`; `program_subject` on real sample spellings (typo fixes, `Non-Thesis Track`, `Major in`, `Medyor sa`); `Quilantang, et al.` gives no author token; `Daluyong, Mirasol T. Abrenica, MD, FPCP` ignores the credentials; document assembly with empty fields.
2. **Hand-calculation test:** a 3-document toy corpus; expected TF, IDF, normalized weights and cosine computed in the test from the Chapter 3 formulas; the build's score matches within 1e-9.
3. **Build tests** on a small fixture catalog (two editions of one work, an archived item, a thesis with a Program tag, a `None` description, an item with no shared terms): no self or same-work pairs; archived excluded; ≤ 12 per item; rank order; contributions of all shared terms sum to the score; two builds identical; empty catalog does not raise; IDF counts a work once.
4. **API tests:** 401 without login; 400/404 cases; τ filter; max 4; `all_out` with an open loan; lost/damaged hidden; archived candidate dropped; `score` present for admins and absent for students; empty list.
5. **Refresh tests:** add, archive and text edits rebuild; a condition-only edit does not; a failing rebuild still returns success.
6. **Evaluation tests:** sheet has no scores; same seed gives the same sample; grading hand-filled fake sheets gives hand-computed precision and coverage; tie → not good; `--out` inside the repo is refused.
7. **Frontend:** no test runner exists and adding one is out of scope. Checked by hand in the running app, plus the black-box cases below.

### Black-box test cases for 3.4.2

| ID | Input | Expected output |
|---|---|---|
| RC-01 | View any item with similar items in the catalog | 1–4 cards, each a different item from the viewed one |
| RC-02 | View an item that has another edition in the catalog | the other edition is not recommended |
| RC-03 | View an item whose top match is on an open loan | that card shows "All copies out" |
| RC-04 | View an item whose only matches are lost or damaged | those items are not shown |
| RC-05 | View an item with no similar items | "No similar items yet." |
| RC-06 | Log in as a student; view an item | reason line shown; no score |
| RC-07 | Log in as an admin; view an item | reason line and score shown |
| RC-08 | Admin adds a new item similar to an existing one; view the existing item | the new item can appear |
| RC-09 | Admin archives a recommended item; view the item that recommended it | the archived item no longer appears |
| RC-10 | Click a recommended card | the modal shows that item and its own recommendations |
| RC-11 | View the same item twice without catalog changes | identical recommendations in identical order |

## 13. Methodology revision notes (for the research partner)

1. **3.3.3.1 TF-IDF:** describe tokenizing (lowercase; words of 2+ letters/digits), stop-word removal (table of the custom lists), `min_df = 2`, raw-count TF, `idf = ln((1 + N) / (1 + df)) + 1`, and L2 normalization. Cite Pedregosa et al. (2011) and the scikit-learn User Guide "Tf–idf term weighting".
2. **Document text:** "titles, authors, genres and abstracts", where genre = tags, and for theses genre = the program. Theses in the current sample have no abstracts (limitation).
3. **3.3.3.2 Cosine:** replace "the student's search query (or previously liked books)" with "the currently viewed item". Scores range 0–1 because TF-IDF weights are non-negative. The scale-invariance argument now applies to a record without an abstract compared with one that has a long abstract.
4. **3.3.3.3:** "Top-N, where N = 4, considering only items with cosine similarity ≥ τ; τ was determined empirically from relevance judgments (3.4.3)." Replace "personalized list" with "list of similar items". Items of the same work are excluded.
5. **3.4.3 Evaluation:** add the blind judging, the split-half procedure, precision@4 and coverage, and describe them as descriptive measures.
6. **Limitations:** no personalization; full Filipino support; theses represented by title, author and program only.
7. **Panel answers:** why not deep learning (no usage history, explainability, small catalog; precomputing results follows Linden, Smith & York, 2003, *IEEE Internet Computing*); why scores cannot be negative.

## 14. Open items and dependencies

| Item | Owner | Needed for |
|---|---|---|
| Author separator format in the books data (thesis format resolved: single author or `Surname, et al.`) | data preparer | author-token split rule |
| Abstracts for theses (any subset) | school / LRC | thesis quality (optional) |
| Duplicate barcode `LRC-VI-A-MT-168` (two different theses) | school / LRC | thesis import |
| Confirm `THESIS_TITLE_WORDS` and complete `PLACE_WORDS` from the title word count | team | stop-word lists |
| Single τ or separate thesis τ | team, after first judging | `RECOMMENDER_MIN_SCORE_THESIS` |
| Designer sign-off on the plain row | designer | merging the UI part |
| BookCopy spec and thesis import | team | availability switch; thesis data load (`publisher` and `pages` are required fields today) |
| Render instance memory (scikit-learn adds ~100 MB) | team | deploy; fallback is building off-server with the same table |
| First τ from team judging on stand-in data | team | replaces the 0.10 default |
