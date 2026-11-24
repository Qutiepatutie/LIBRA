# Endpoint access rules for catalog and loans — Design

Date: 2026-11-17 · Branch: `fix/endpoint-access-checks` (cut from `feat/book-copy` 970997d, PR #15) · Worktree: `C:/github25/bookly-lms-access-checks`

## 1. Intent

Several catalog and loan endpoints accept any logged-in account, or identify the borrower from a value in the request body. Make each endpoint check who is calling: the account comes from the JWT (`request.user`), the borrower profile from `request.user.profile`, and the admin role from `IsAdminRole` (`library/permissions.py`).

### Goals
- Desk and catalog actions are admin only.
- A student can act only on their own loans and see only their own loan records.
- `editBook/` and `addBook/` agree on the item-type key.
- The existing frontend keeps working; the only frontend change is how the CSV export is downloaded.

### Non-goals
- Room reservation endpoints (`reserveRoom/`, `acceptReservedRoom/`, `cancelReservedRoom/`, `getAllReservedRooms/`, `getUserReservedRooms/`). Report what you see there; do not change them.
- Any change to response shapes, models or migrations.
- UI redesign.

## 2. Access rules (the contract)

"Admin" = `IsAuthenticated` + `IsAdminRole`. Unauthenticated → 401. Authenticated but not allowed → 403. Bodies and success responses stay as they are on `feat/book-copy` unless stated.

| Endpoint | Rule |
|---|---|
| `POST addBook/`, `PUT editBook/`, `POST removeBook/` | Admin only. |
| `PUT acceptBorrowedBook/`, `PUT returnBook/` | Admin only. |
| `GET exportBorrowedBooksCSV/` | Admin only. Becomes a DRF `api_view(['GET'])`; drop `csrf_exempt`. CSV columns and filename unchanged. On an unexpected error return 500 `{"message": "CSV export failed"}` without the exception text. |
| `POST borrowBook/` | The borrower is the caller's own profile. `id_number` in the body is optional. A non-admin sending an `id_number` that is not their own → 403 `"You can only borrow for yourself"`. An admin may send any `id_number` to borrow on that person's behalf (404 `"User not found"` if it matches nobody). A caller with no profile and no `id_number` → 404 `"User not found"`. Everything after the borrower is resolved is unchanged. |
| `PUT cancelBorrowedBook/` | Admin, or the borrower who owns the loan. Anyone else → 403 `"You can only cancel your own request"`. The existing 404 for a missing or non-pending loan stays, and is checked first for admins; for a non-admin a loan that is not theirs returns 403 whatever its status. |
| `GET getAllBorrowedBooks/` | Admin gets every record, as today. A non-admin gets only their own loans, same record shape. A non-admin with no profile gets an empty list. |
| `POST getUserBorrowedBooks/` | Same rule as `borrowBook/`: `id` in the body is optional; a non-admin may only ask for their own (403 `"You can only view your own loans"` otherwise); an admin may ask for anyone. |

Already correct, leave alone: `addCopy/`, `editCopy/`, `removeCopy/`, the three admin dashboards, and the user dashboard endpoints (they use `request.user.profile`).

### Item-type key
`PUT editBook/` reads `item_type`, the same key `addBook/` uses. It still accepts the old `itemType` so existing callers keep working; when both are sent, `item_type` wins. Validation and messages unchanged.

## 3. Frontend

Only one call site must change. `pages/admin/history/History.jsx` opens the CSV export with `window.open(url)`, which sends no token and will now get 401.

- Add `exportBorrowedBooksCSV()` to `frontend/src/api/books.js`: `authFetch` the endpoint, and on 200 return the response as a blob together with the filename from the `Content-Disposition` header (fall back to `borrowed_books.csv`).
- In `History.jsx`, for the books page only, call it and save the blob through a temporary object URL and an `<a download>` element that is clicked and removed, then revoke the URL. On a non-200 response show the failure the way this page already reports errors (or a toast if it has none). Leave the rooms export exactly as it is.

Nothing else should need to change: student pages already filter loan records by their own `id_number`, and add/edit/remove book controls are only shown to admins. Confirm that by reading the callers; if a student-facing screen relied on seeing other borrowers' records, report it.

## 4. Tests

For every row in the table: unauthenticated → 401, non-admin → 403 (or the scoped result), admin → success. Plus:
- `borrowBook/` with no `id_number` borrows for the caller; a student naming another student is refused and no loan is created; an admin naming a student creates the loan for that student.
- `cancelBorrowedBook/`: owner can cancel; another student cannot and the loan stays Pending; admin can.
- `getAllBorrowedBooks/`: with loans from two students, each student sees only their own and the admin sees both.
- `editBook/`: `item_type` works, `itemType` still works, `item_type` wins when both are sent.
- CSV: admin gets `text/csv` with the header row; the error path does not include exception text.

Existing tests that call these endpoints as a plain user need an admin client where the rule now demands one. Keep each test's original intent.

## 5. Test environment

- Python: `C:/github25/bookly-lms/backend/venv/Scripts/python.exe` (the worktree has no venv and no `.env`; never use the main checkout's `.env`, it points at the live database).
- Throwaway Postgres 18 is running on `127.0.0.1:55432`.
- From `backend/` in this worktree:

```bash
PYTHONPATH="<scratch settings dir>" BOOKCOPY_AGENT=<your-tag> C:/github25/bookly-lms/backend/venv/Scripts/python.exe manage.py test <labels> --settings=bookcopy_pg --noinput
```

Baseline on this branch before any change: 158 tests, all passing.

## 6. Work split

| Worker | Owns |
|---|---|
| Opus | `backend/library/views.py`, `backend/library/tests.py`, and other `backend/library/test_*.py` files only where an existing test must switch to an admin client |
| Sonnet | `frontend/**` |

Rules: stay inside this worktree; do not commit, stash, switch branches or push; do not edit the other worker's files; follow the existing code style; no new dependencies.
