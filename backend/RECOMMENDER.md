# Books to recommend (TF-IDF recommender)

The book modal shows up to four "similar items" for the title being viewed. Each title
is turned into a bag of words (title, author names, tags, a Dewey subject word,
description), weighted by TF-IDF, and compared with every other title by cosine
similarity. The top 12 neighbours per title are precomputed and saved, and the endpoint
only reads them, filters by a score threshold and adds live availability. Full design:
`docs/superpowers/specs/2026-11-14-tfidf-recommender-design.md` (sections 15 and 16 win
over earlier text).

Code: `library/recommender/` (`preprocess.py`, `dewey.py`, `stopwords.py`, `build.py`,
`serve.py`, `evaluation.py`), table `book_recommendations` (`BookRecommendation`,
migration `0017`), commands in `library/management/commands/`.

## Endpoint

`GET /getRecommendations/?book_id=<id>` needs `Authorization: Bearer <jwt>` (any role).
`400 {"message": "Missing book_id"}` when `book_id` is missing or not an integer,
`404 {"message": "Book not found"}` for an unknown or archived title, `401` without a
token. `data` is empty when nothing passes the threshold (the UI shows its empty state).

Rows are the title's saved neighbours in rank order, kept when
`score >= threshold` and the neighbour is not archived. Neighbours with no non-archived
good copy (`hidden`) are dropped, then the first 4 are returned. `availability` is
`available` (a copy is free) or `all_out` (good copies exist but none is free), read live
from the copies. `reason` holds up to 3 display labels. `book` has the `getBooks` shape.

Student:

```json
{"data": [{
  "book": {"id": 12, "title": "Parallel Logic Programming", "author": "Santos, A.", "total_copies": 2, "available_copies": 1, "...": "..."},
  "availability": "available",
  "reason": ["logic", "programming", "Computer science"]
}]}
```

Admin (`role == admin`, decided from the account on the server) gets the same plus `score`:

```json
{"data": [{"book": {"id": 12, "...": "..."}, "availability": "all_out",
           "reason": ["logic", "programming", "Computer science"], "score": 0.3127}]}
```

The ShowBook slot renders the row for non-admins only; the admin `score` is for the
defense and debugging, read from the API response.

## Settings (environment variables)

| Variable | Default | Meaning |
| --- | --- | --- |
| `RECOMMENDER_MIN_SCORE` | `0.10` | Threshold tau for every title. |
| `RECOMMENDER_MIN_SCORE_THESIS` | empty | Tau for theses only; empty means "use `RECOMMENDER_MIN_SCORE`". |

A value that is not a number in 0..1 logs a warning on `library.recommender` and falls
back to `0.10`. Tau is applied when serving, so changing it needs a restart of the
host, not a rebuild. The 0.10 default is a placeholder until the team's first judging
round.

## When rebuilds happen

`rebuild_recommendations()` is called explicitly (no Django signals) after:

- `addBook/` succeeds, for a new title and for an un-archived title;
- `removeBook/` (archive);
- `editBook/` only when `title`, `author`, `tags`, `description` or `call_number` changed
  (the Dewey subject word is derived from the call number).

Condition, pages, publisher and similar edits do not rebuild. No copy or
loan endpoint rebuilds (availability is read live). A failed rebuild is logged with the
traceback on the `library.recommender` logger and never fails the save; the previous
table stays. Data loaded straight into the database (imports, seed script) needs a manual
`rebuild_recommendations`.

## Commands

Run from `backend/`.

```
python manage.py rebuild_recommendations
# items=300 works=300 vocabulary=58 pairs=3600 seconds=1.05
```

```
python manage.py export_judging_sheet --items 30 --per-item 8 --seed 42 --out D:\judging\round1
# sheet=...judging_sheet.csv  key=...judging_key.csv  pairs=... items_A=15 items_B=15
```
Samples 30 titles that have saved candidates, takes each title's ranks 1..8 (ignoring
tau), splits titles into group A (choose tau) and B (measure). The sheet has no score,
rank or group; the key has them. `--out` must be outside the repository or the command
refuses.

```
python manage.py evaluate_recommender --key D:\judging\round1\judging_key.csv ^
  --sheet D:\judging\round1\judge1.csv --sheet D:\judging\round1\judge2.csv ^
  --out D:\judging\round1\results [--tau 0.15] [--tau-thesis 0.20]
```
Majority vote per pair (tie = not good, blank = no vote). Prints 0.05-wide score bands
for all, books and theses, and the suggested tau (lowest band with at least 70 percent
good and at least 5 judged pairs). Without `--tau` the "all" suggestion is used for
precision@4 (group B) and coverage. Writes `bands.csv` and `top4_scores.csv` to `--out`.

```
python manage.py explain_recommendation 12 15
```
Prints for every shared term: raw tf in each title, idf, tf-idf weight before L2
normalisation, weight after normalisation, contribution, then both norms and
`TOTAL SCORE`. It refits on the current catalog, so the total equals the saved score
only right after a rebuild.

## Deploy steps

1. `pip install -r requirements.txt` (adds `scikit-learn==1.9.1`; plan for about 100 MB
   more memory on the host).
2. `python manage.py migrate` (creates `book_recommendations`).
3. `python manage.py rebuild_recommendations` (the table starts empty).
4. Set `RECOMMENDER_MIN_SCORE` on the host (and `RECOMMENDER_MIN_SCORE_THESIS` if the
   team decides on a separate thesis threshold), then restart.

## Before the defense

`DEWEY_DIVISIONS` in `library/recommender/dewey.py` is the 100-row division name table
shown in reason lines. It must be checked against OCLC's published DDC 23 summaries.
The stop-word lists (`stopwords.py`, including `BOOK_TITLE_WORDS`) also need the team's
confirmation. Tau comes from the team's judging round, not from the placeholder.

## Privacy rule for judging files

Judging sheets contain thesis authors' names. Write them only outside the repository
(the commands enforce this for `--out`), never commit them, and never put them in
the repository's docs or issues. Judges must save their filled sheet as
**CSV UTF-8**. The grader reads `utf-8-sig`; Excel's plain "CSV (Comma delimited)" is
cp1252 and fails on characters such as the n with tilde.

## Build time and the upgrade path

Measured on a throwaway local Postgres (not the live database), 300 generated titles
with 40-word descriptions: `items=300 works=300 vocabulary=58 pairs=3600 seconds=1.05`
(two runs, 1.05 s each, on a developer laptop). The vocabulary is small because the
generated text reuses about 60 words, so a real catalog will have a larger vocabulary and
a different timing; re-measure on the real catalog after the school import.

Synthetic 5,000-title benchmark (no database; generated text, not the school's catalog):
5,000 documents with 20 to 40 description words each, vocabulary 3,867, 60,000 saved
pairs. Scoring, top-12 selection, reason terms and building the unsaved rows
(`_build_rows`) took about 1.5 s on a developer laptop, down from 23 to 46 s before the
candidate selection and reason-term lookups were vectorised. Loading the catalog,
fitting the vectorizer and writing the rows to Postgres come on top of that.

When rebuilds regularly take more than about 5 seconds, move the rebuild out of the
save request (run it after the response or on a short schedule). The table and the API
stay the same. If the host lacks memory for scikit-learn, build off-server with the same
table.

## Known baseline

`library.tests` has 9 pre-existing `addBook` failures on main (8 failures, 1 error in
`CatalogCopyTests` and `ItemIdentityTests`): the tests post JSON to the multipart-only
endpoint and get `415`. They are not fixed on this branch. Full suite on this branch
(`manage.py test library accounts books`): 268 tests, only those 9 fail.

## Black-box cases (spec section 12)

Walk as a student unless noted. Status: not run. The walk-through needs a browser
session logged in through the app's Google sign-in and an admin plus a student account;
that cannot be done non-interactively, and the frontend must not be pointed at the live
backend. Do not read these as passed. The API behaviour behind each case is covered by
automated tests in `library/test_recommender_*.py`; that is not a substitute for the
screen check.

| ID | Input | Expected output | Status |
| --- | --- | --- | --- |
| RC-01 | View any item with similar items in the catalog | 1-4 cards, each a different item from the viewed one | not run |
| RC-02 | View an item that has another edition in the catalog | the other edition is not recommended | not run |
| RC-03 | View an item whose top match is on an open loan | that card shows "All copies out" (availability `all_out`) | not run |
| RC-04 | View an item whose only matches are lost or damaged | those items are not shown | not run |
| RC-05 | View an item with no similar items | "No similar items yet." | not run |
| RC-06 | Log in as a student; view an item | reason line shown; no score | not run |
| RC-07 | Log in as an admin; view an item (check the API response) | reason line and `score` present | not run |
| RC-08 | Admin adds a new item similar to an existing one; view the existing item | the new item can appear | not run |
| RC-09 | Admin archives a recommended item; view the item that recommended it | the archived item no longer appears | not run |
| RC-10 | Click a recommended card | the modal shows that item and its own recommendations | not run |
| RC-11 | View the same item twice without catalog changes | identical recommendations in identical order | not run |

Note: phase 1 of the UI uses `BookPanel` as is (cover, title, author); the availability
badge and reason line are in the API response but are not drawn until the designer
specifies them, so RC-03 and RC-06 will need that before they can pass on screen.
