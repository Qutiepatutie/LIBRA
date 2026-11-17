# BookCopy split: titles and physical copies — Design

Date: 2026-11-16 · Branch: `feat/book-copy` (cut from `origin/main` 1bb7294) · Worktree: `C:/github25/bookly-lms-bookcopy`

## 1. Intent

The library holds several physical copies of one title. Today one `Books` row is both the title and the single copy, and `books_isbn_unique_nonblank` rejects a second copy. Split the table so that:

- `Books` is the **title** (catalog record), one row per work.
- `BookCopy` is the **physical item**, many per title.
- A loan (`BorrowRecords`) points at the exact copy.

This is 3NF: title attributes depend on the title, copy attributes on the copy.

### Goals
- Store any number of copies per title, each with its own condition, acquisition date and optional barcode.
- A student requests a **title**; the system assigns a free copy at request time (decision A, chosen by the user).
- Existing data migrates one to one and the migration is reversible.
- API changes are additive where possible so the frontend change stays small.

### Non-goals
- Importing the school's thesis file.
- The TF-IDF recommender (own spec, on `feat/tfidf-recommender`). It only needs `Books` to be one row per title, which this delivers.
- Admin-only permissions for the existing catalog endpoints (`addBook/`, `editBook/`, `removeBook/`), tracked separately.
- Redesigning any screen. The user does not own the UI design: reuse existing components and CSS modules, add the fewest elements that work.
- Changing the type of `date_acquired` (stays a `CharField`).

### Anti-goals
- Never run anything against the live Supabase database. All tests use the throwaway local Postgres (section 8).
- No stored "available" flag. Availability is always derived.

## 2. Live data (checked 2026-11-16, read only)

105 books, all `item_type=book`, all `condition=good`, none archived, all with ISBN and `date_acquired`, no repeated title+author. 62 loans (14 Active, 32 Returned, 16 Cancelled), no fines. No book has more than one open loan. So every row becomes one title + copy 1, and the new one-open-loan-per-copy constraint holds on current data.

## 3. Approaches considered

| Approach | Verdict |
|---|---|
| Keep one table, drop the unique constraints | Rejected: title data repeats per copy and drifts; no item identity. |
| `quantity` column on `Books` | Rejected: no per-copy condition; a loan cannot name the item. |
| **`Books` + `BookCopy`, loan → copy** | **Chosen.** |

Copy assignment: **A, automatic at request** (chosen) over B, the desk scans a barcode at accept (needs new UI and barcodes the library has not supplied for books).

## 4. Models (`backend/library/models.py`)

### `Books` (table `books`) — the title
Keeps: `item_type`, `call_number` (unique), `isbn` (+ `books_isbn_unique_nonblank`), `title`, `author`, `edition`, `description`, `tags`, `publisher`, `year_published`, `pages`, `cover_url`, `is_archived`.
Removes: `condition`, `date_acquired` (move to the copy).

### `BookCopy` (table `book_copies`) — the physical item
| Field | Definition |
|---|---|
| `book` | `ForeignKey(Books, on_delete=CASCADE, related_name='copies')` |
| `copy_number` | `PositiveIntegerField` (1, 2, 3…; shown as "c.2") |
| `accession_number` | `CharField(max_length=50, blank=True)` — the barcode; unique when non-blank |
| `condition` | `CharField(max_length=20, choices=ConditionChoices, default=GOOD)` |
| `date_acquired` | `CharField(max_length=100, blank=True)` |
| `is_archived` | `BooleanField(default=False)` — a withdrawn copy; keeps its loan history |

Constraints: `UniqueConstraint(fields=['book','copy_number'], name='book_copy_number_unique')`; `UniqueConstraint(fields=['accession_number'], condition=~Q(accession_number=''), name='book_copy_accession_unique_nonblank')`.

Accession numbers are blank for migrated rows: the library has not given barcodes for existing books, and invented values would look like real barcodes.

### `BorrowRecords`
- Replace `book` with `copy = ForeignKey(BookCopy, on_delete=CASCADE, related_name='loans')`.
- Add a read-only property `book` returning `self.copy.book` (for non-ORM code such as the CSV export). ORM lookups must use `copy__book__…`.
- Add `UniqueConstraint(fields=['copy'], condition=Q(status__in=[PENDING, ACTIVE, DUE, OVERDUE]), name='loan_one_open_per_copy')`.

### Availability rule (single source: `backend/library/copies.py`)
A copy is **available** when all hold: `is_archived=False`, `condition='good'`, and it has no loan whose status is in `HOLD_STATUSES = (Pending, Active, Due, Overdue)`.
A title is borrowable when `Books.is_archived=False` and it has at least one available copy.

`copies.py` exports:
- `HOLD_STATUSES`
- `available_copies(book=None)` → `BookCopy` queryset of available copies (optionally for one title), ordered by `copy_number`
- `with_copy_counts(books_qs)` → annotates `total_copies` (non-archived copies) and `available_copies`
- `assign_copy(book)` → must run inside `transaction.atomic()`; locks the title row (`select_for_update` on `Books`) and returns the lowest-numbered available copy or `None`. Locking the title row, not the copy rows, is deliberate: a concurrent request adds a loan row without changing the copy row, so a copy-row lock would not make the second request re-evaluate.
- `next_copy_number(book)` → highest existing `copy_number` (archived included) + 1

## 5. Migrations (`backend/library/migrations/`, after `0013_books_is_archived`)

1. `0014_bookcopy` — create `BookCopy` with its constraints; add `BorrowRecords.copy` as nullable; alter `BorrowRecords.book` to nullable (needed so the reverse path works).
2. `0015_backfill_book_copies` — `RunPython`, forward and reverse.
   - Forward: for every `Books` row create copy 1 (`accession_number=''`, `condition` and `date_acquired` copied from the book, `is_archived=False`); set each loan's `copy` to its book's copy 1.
   - Reverse: write the lowest-numbered copy's `condition` and `date_acquired` back to the book; set each loan's `book` from `copy.book`.
3. `0016_finalize_book_copy` — `copy` non-null; remove `BorrowRecords.book`, `Books.condition`, `Books.date_acquired`; add `loan_one_open_per_copy`.

Requirement: `migrate library 0013` from `0016` must succeed with data present, restoring `condition`, `date_acquired` and every loan's `book`. Covered by a migration test.

## 6. API contract

Field names below are exact. "Copy payload" = `{id, copy_number, accession_number, condition, date_acquired, is_available}`. "Copy ref" = `{id, copy_number, accession_number}`.

### Catalog
| Endpoint | Request | Response / behaviour |
|---|---|---|
| `GET getBooks/` | — | `{"data":[title…]}`. Each title: `id, call_number, isbn, title, author, edition, description, tags, publisher, year_published, pages, cover_url, item_type, is_archived, total_copies, available_copies, copies:[copy payload…]`. `copies` lists non-archived copies by `copy_number`. **Removed** top-level `condition`, `date_acquired`. No N+1 queries. |
| `POST addBook/` | title fields as today, plus optional copy fields `accession_number`, `date_acquired`, `condition` | Creates the title and copy 1 atomically → 201, `{"message":"Book Successfully Added!"}`. Existing rules unchanged: missing `call_number`/`title`/`author` → 400; archived match on (`call_number`,`isbn`) → un-archive, 200; duplicate ISBN → 400 "Book already exists". New: duplicate accession → 400 `"Accession number already exists"`; invalid condition → 400 `"Invalid condition"`. |
| `POST addCopy/` (new, admin) | `{book_id, accession_number?, date_acquired?, condition?}` | 201 `{"message":"Copy added","copy":copy payload}`. `copy_number = next_copy_number(book)`. 400 `"Missing book_id"`; 404 `"Book not found"`; 400 if the title is archived; 400 duplicate accession; 400 invalid condition. |
| `PUT editBook/` | as today | Title fields only. A `condition` key in the body is ignored. |
| `PUT editCopy/` (new, admin) | `{copy_id, condition?, accession_number?, date_acquired?}` | 200 `{"message":"Copy successfully edited","copy":copy payload}`. 400 `"Missing copy_id"`; 404 `"Copy not found"`; 400 invalid condition / duplicate accession. |
| `POST removeCopy/` (new, admin) | `{copy_id}` | Archives the copy → 200 `{"message":"Copy successfully removed"}`. 400 `"Copy is on loan"` if it has a hold-status loan. |
| `POST removeBook/` | as today | Unchanged: archives the title. |

New copy endpoints use `@permission_classes([IsAuthenticated, IsAdminRole])`.

### Loans
| Endpoint | Request | Response / behaviour |
|---|---|---|
| `POST borrowBook/` | `{id_number, book_id}` (unchanged; `book_id` is the title) | In one transaction: existing 404/400 checks; if the user already holds a hold-status loan on any copy of this title → 400 `"You already have a request or loan for this book"`; `assign_copy(book)`; none → 400 `"All copies are currently borrowed"`; else create a Pending loan → 200 `{"message":"Book successfully borrowed","loan_id":…,"copy":copy ref}`. |
| `PUT acceptBorrowedBook/` | `{loan_id}` (**replaces** `book_id`) | Looked up by loan pk; must be Pending. Same success body and 404 message as today. Missing/non-integer → 400 `"Missing loan_id"`. |
| `PUT returnBook/` | `{loan_id}` | By pk; must be in `OPEN_STATUSES` with no return date. Same messages. |
| `PUT cancelBorrowedBook/` | `{loan_id}` | By pk; must be Pending. Same messages. |
| `GET getAllBorrowedBooks/` | — | Each record gains `id` (loan id) and `copy` (copy ref). `book` stays a nested title object (title fields only, no `copies`). |
| `POST getUserBorrowedBooks/` | as today | Each item gains `id` (loan id); `cover_url, due_date, status` unchanged. |
| Dashboard loan lists (`DashboardLoanSerializer`) | — | Unchanged fields plus `copy_number`, `accession_number`. `book_id` stays the title id. |
| `GET exportBorrowedBooksCSV/` | — | Two extra columns at the end: `Copy Number`, `Accession Number`. |

`book_id` can no longer identify a loan: two students can each hold a different copy of one title.

### Analytics (response shapes unchanged unless noted)
- **Inventory**: `total_copies` = non-archived copies of non-archived titles; `lost_damaged` by copy condition; `borrowed` = good copies out on a checkout (Active/Due/Overdue, as today; Pending still counts as on the shelf); `available = total − borrowed − lost_damaged`. `overdue_items[]` gain `copy_number`, `accession_number`.
- **Admin circulation**: `item_type` filter and `top_borrowed` go through `copy__book`. `top_borrowed` groups by title id (output keys `title, author, count` unchanged).
- **User analytics**: call-number class breakdown reads `copy__book__call_number`.
- Update `backend/ADMIN_*_ANALYTICS.md` and `USER_ANALYTICS.md` where they describe these.

## 7. Frontend (`frontend/src`)

Keep it minimal; reuse existing styles.
1. `api/books.js`: `acceptBorrowedBook`, `returnBook`, `cancelBorrowedBook` send `{loan_id}`; add `addCopy`, `editCopy`, `removeCopy`.
2. Admin admission (`AdminBorrowers.jsx`, `BookBorrowerList.jsx`, `useBorrowers.js`): use the loan `id`, not `book.id`; show the copy as "c.N" plus the accession number when present.
3. Every other caller of accept/return/cancel: pass the loan id.
4. `ShowBook` and related: availability from `available_copies` / `total_copies` ("N of M copies available"); borrow disabled at 0. For admins, a plain copies list: condition select per copy (`editCopy`), add copy, remove copy. Stop sending `condition` through `editBook`.
5. `AddBook`: `date_acquired` still goes to `addBook`; add an optional accession number input.
6. Anything reading `book.condition` or `book.date_acquired` reads from `book.copies` instead.

Check: `npm run lint` and `npm run build` pass in `frontend/`.

## 8. Test environment

- Worktree: `C:/github25/bookly-lms-bookcopy`. It has no venv and no `.env` (the main checkout's `.env` points at live Supabase; never use it).
- Python: `C:/github25/bookly-lms/backend/venv/Scripts/python.exe`
- Throwaway Postgres 18 is already running on `127.0.0.1:55432` (user `postgres`, trust auth).
- Settings module `bookcopy_pg` lives outside the repo (a scratch directory put on `PYTHONPATH`). It extends `backend.test_settings` and points `DATABASES` at the throwaway Postgres. From `backend/` in the worktree:

```bash
PYTHONPATH="<scratch settings dir>" BOOKCOPY_AGENT=<your-tag> C:/github25/bookly-lms/backend/venv/Scripts/python.exe manage.py test <labels> --settings=bookcopy_pg --noinput
```

`BOOKCOPY_AGENT` names the test database, so each worker uses its own tag and runs do not collide.

Baseline on `origin/main`: 107 tests, 2 failures that predate this work — `library.tests.ItemIdentityTests.test_books_still_require_a_unique_isbn` and `…test_two_theses_without_isbn_can_be_added` (both assert 200 where `addBook/` returns 201).

## 9. Work split

| Worker | Owns (nobody else edits these) |
|---|---|
| Opus 1 (first, alone on backend) | `library/models.py`, `library/migrations/0014–0016`, `library/copies.py`, `library/admin.py`, `library/test_book_copy.py` |
| Opus 2 (after Opus 1) | `library/views.py`, `library/serializers.py`, `library/urls.py`, `library/tests.py`, `backend/seed_data.py` |
| Sonnet 1 (after Opus 1) | `library/admin_analytics.py`, `inventory_analytics.py`, `user_analytics.py`, `borrower_analytics.py`, `library/test_*_analytics.py`, `backend/test_analytics.py`, `backend/*.md` |
| Sonnet 2 (any time) | `frontend/**` |

Rules for all workers: stay inside the worktree; do not commit, stash, switch branches or push; do not edit another worker's files (report what you need changed instead); follow the existing code style; no new dependencies.
