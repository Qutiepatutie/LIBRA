# User dashboard API

Backend contract for Figma `Dashboard #user`, Group 354 (`2661:1751`) and the
Borrowing history tab (`2654:1793`). This implements no UI and makes no changes
to the separate admin analytics API.

All three endpoints require `Authorization: Bearer <access token>`. They use
the token owner's `UserProfile`; query parameters such as `user_id`, `id`, or
`id_number` never select another borrower. Missing authentication returns 401,
a missing profile returns 404, and unsupported HTTP methods return 405.

## Routes

| GET route | Response |
| --- | --- |
| `/getUserAnalytics/` | Statistics cards, academic-term resolution, both charts, history summary |
| `/getUserCurrentLoans/` | Paginated unreturned checkouts and pending requests |
| `/getUserBorrowingHistory/` | Paginated actual checkouts, including unreturned loans, plus a lifetime summary |

The table endpoints accept `page` (default 1) and `page_size` (default 20,
maximum 100). Invalid values return 400; nonexistent pages return 404.
Results are ordered by checkout timestamp descending, then loan ID descending,
with pending requests lacking a timestamp at the end. Pagination is by page
number; a concurrent checkout can move rows between pages.

Table response shape:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [{
    "loan_id": 42,
    "book_id": 7,
    "title": "Example book",
    "call_number": "600.T932 1991",
    "borrow_date": "2026-10-01T09:00:00+08:00",
    "due_date": "2026-10-08",
    "return_date": null,
    "status": "Active",
    "fine": {
      "currency": "PHP",
      "amount_assessed": "0.00",
      "amount_paid": "0.00",
      "outstanding": "0.00"
    }
  }]
}
```

Borrowing history also has a top-level `summary` containing `total_borrowed`,
`overdue`, `late_returned`, and `fine` (the same money shape, summed across the
borrower's recorded fines). This summary covers the entire history, not just
the current page. The **Fee paid** column uses `fine.amount_paid`.

## Dashboard response and counting rules

`GET /getUserAnalytics/` returns:

- `as_of`: ISO timestamp for this request; `timezone`: `Asia/Manila`.
- `statistics`: `currently_borrowed`, `due_soon`, `overdue`, `books_this_semester`.
- `academic_term`: `{ "status": "active", "term": {...} }`. A resolved term
  includes its ID, academic year, semester, education level, year level, start
  date, and end date. See the unresolved states below.
- `due_soon_window`: `start_date` and `end_date`, inclusive.
- `borrowing_frequency`: six chronological `{ "month": "YYYY-MM", "count": n }`
  entries, including zero months and the current partial month.
- `most_borrowed_subjects`: `{ "total_borrowed": n, "subjects": [...] }`.
  Each subject has `code`, `label`, `count`, and `percentage`.
- `history_summary`: the same lifetime summary returned by the history route.

An actual checkout has a non-null `borrow_date` no later than this request and
status Active, Due, Overdue, or Returned. Each checkout counts once; borrowing
the same book again counts again. Pending and Cancelled requests never count.

Currently borrowed means an actual checkout with an open status and no return
date. Due soon means due **today through Saturday**, excluding already overdue
loans. A new Sunday starts a new window. Overdue means an open loan whose due
date is before today, regardless of a stale stored status. Missing due dates
do not count as due soon or overdue. Late returned means the recorded return
date is after the due date and no later than today. Returning on the due date
is on time. The table derives Active, Due (today), Overdue, or Returned from
these dates; pending requests retain Pending and a null borrow date.

All calendar boundaries use `LIBRARY_TIME_ZONE` (Asia/Manila), even though the
project's default `TIME_ZONE` remains UTC. New checkout due dates and return
dates also use library-local dates. Existing historical date-only values are
used as recorded; their original time of day cannot be reconstructed.

The redesign supersedes the older chart descriptions in `analytics_user.md`:
borrowing frequency is monthly, and most borrowed subjects ranks lifetime
checkouts by broad Dewey class. The API returns the top five classes plus
`Other` if necessary, with ties ordered by code. It reads the leading three
digits of a call number (`600.T932` maps to Technology). `000–099` uses display
code `001`, matching the design. Non-numeric or prefixed call numbers go to
`Unclassified`; they are never silently dropped. Percentages use all eligible
checkouts as the denominator and are rounded to two decimals.

## Academic-year and semester timelines

`UserProfile.education_level` accepts `senior_high` or `college`.
`year_level` is a string containing a positive integer, e.g. `"1"` for college
freshman or `"11"` for Grade 11. Existing profiles migrate with these fields
blank; do not infer a student's level from their program name.

`AcademicYear` stores the full year's label (for example `2026-2027`), education
level, optional year-level scope, and inclusive `start_date` / `end_date`.
`AcademicTerm` stores one semester's timeline and can link to that year through
`academic_year_timeline` (`AcademicYear.semesters` is the reverse relationship).

For compatibility, `AcademicTerm` retains its academic-year label, semester, education level, optional
year level, and inclusive start/end dates. Null and empty year levels both
mean the default calendar for that education level. For each academic-year /
semester pair, an exact year-level override replaces the default **before**
checking dates. Thus a freshman term starting later suppresses the default
term even while that default is active. Overrides do not carry into another
academic year automatically.

Each `AcademicTerm` represents one semester, not the entire academic year's
date range. Prelims, Midterms, and Finals are not tracked separately.

A linked semester must match its year's label and education level, and its
dates must fit inside the year's dates. A year with a specific year-level scope
only accepts that cohort; a default year accepts any cohort. `AcademicYear.save()`
validates the model and rejects date or scope edits that invalidate linked
semesters. A year with linked semesters is protected from deletion. Continue to
call `AcademicTerm.full_clean()` before saving semesters. Bulk writes bypass
these relationship checks; date order and unique scopes also have database
constraints. Relationship checks do not serialize concurrent writes.

Migration `0005_delete_semesterterm` removes the unused grading-period table
and any records in it, preserving existing academic terms. The historical
`0004_semesterterm` migration remains so already-migrated databases can upgrade.
Reversing `0005` recreates an empty table; it does not restore deleted records.
The analytics response remains scoped to the academic term.

Migration `0006_academicyear_academicterm_academic_year_timeline` adds the year
table and a nullable link on semesters without changing existing semester data.
Existing semesters remain valid with no link. Configure the approved full-year
dates explicitly, then link the relevant semesters; the migration does not infer
year dates from a possibly incomplete semester calendar. Reversing `0006` removes
year timelines and their links but preserves the original semester fields and
records; export configured year timelines first if they need to be restored.

Call `full_clean()` before saving terms in trusted backend management code.
It checks effective-calendar overlaps while allowing intentional default /
override overlap. Database constraints enforce unique scopes and valid date
order. If imported data bypasses validation and produces multiple active
effective terms, the API returns `conflict` instead of choosing arbitrarily.

When the term cannot be resolved, `term` and `books_this_semester` are null:

| Status | Meaning |
| --- | --- |
| `profile_incomplete` | Education level or year level is missing |
| `not_configured` | No applicable term is configured |
| `no_active_term` | Terms exist, but today is outside their effective windows |
| `conflict` | More than one effective term is active |

With an active term and no checkouts, the semester card is **0**. Its count
uses checkout timestamps inside that term, including books since returned.
This is a current-term view using the student's current profile, not a
historical enrollment/cohort tracking system.

## Recorded fines

`LoanFine` has one record per loan: decimal `amount_assessed`, cumulative
`amount_paid`, an internal note, and `updated_at`. All amounts are PHP and API
money is a two-decimal string. Database constraints reject negative values and
payments above the assessed amount. Model saves also reject fines on pending,
cancelled, or never-checked-out records. A fine protects its loan from deletion.

There is **no automatic daily rate**, grace period, or cap. No fine record
means no recorded charge. Outstanding = assessed minus paid, including fines
on returned books. Returning a book does not mark its fine as paid. Notes are
not exposed by these user endpoints.

These endpoints are read-only. A trusted librarian backend can populate
profiles, terms, and fines through the models. For example, in a Django shell:

```python
from decimal import Decimal
from datetime import date
from accounts.models import UserProfile
from library.models import AcademicYear, AcademicTerm, LoanFine

profile = UserProfile.objects.get(id_number="ACTUAL-STUDENT-ID")
profile.education_level = "college"
profile.year_level = "1"
profile.full_clean()
profile.save(update_fields=["education_level", "year_level"])

# Example dates only: substitute the institution's actual approved calendar.
year = AcademicYear.objects.create(
    academic_year="2026-2027", education_level="college",
    start_date=date(2026, 8, 17), end_date=date(2027, 6, 1),
)
first_semester = AcademicTerm(
    academic_year_timeline=year, academic_year=year.academic_year,
    semester="1", education_level=year.education_level,
    start_date=date(2026, 8, 17), end_date=date(2026, 12, 18),
)
first_semester.full_clean()
first_semester.save()
second_semester = AcademicTerm(
    academic_year_timeline=year, academic_year=year.academic_year,
    semester="2", education_level=year.education_level,
    start_date=date(2027, 1, 11), end_date=date(2027, 6, 1),
)
second_semester.full_clean()
second_semester.save()

# Example charge only: use the actual librarian-assessed amount and loan ID.
fine = LoanFine(loan_id=42, amount_assessed=Decimal("25.00"), amount_paid=Decimal("0.00"))
fine.save()  # Validates the model before saving.
```

Librarian write endpoints and a payment transaction ledger are outside this
user-dashboard implementation. Future payment writers should use a transaction
and row lock when updating the cumulative amount to avoid lost concurrent updates.

## Migrations and verification

Migrations add the two profile fields, AcademicTerm, AcademicYear, LoanFine,
and a user/checkout-date index. No analytics snapshot table is needed: the dashboard
aggregates loan records on demand.

From `backend`, apply to the intended application database when ready:

```powershell
.\venv\Scripts\python.exe manage.py migrate
```

Run the tests without touching the configured application database:

```powershell
.\venv\Scripts\python.exe -B manage.py test library --settings=backend.test_settings --noinput
.\venv\Scripts\python.exe -B manage.py check --settings=backend.test_settings
.\venv\Scripts\python.exe -B manage.py makemigrations --check --dry-run --settings=backend.test_settings
```

All feature tests live in `library/tests.py`. Test settings use an in-memory
SQLite database and apply the real migrations. Run the suite against a
dedicated PostgreSQL test database as well before production rollout; SQLite
does not prove PostgreSQL-specific execution or concurrent-write behavior.

Authentication and isolation described here apply to these new routes. Existing
legacy catalog/circulation endpoints retain their current permission behavior;
this change is not an authorization overhaul of the application.
