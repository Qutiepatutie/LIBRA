# Admin dashboard analytics — Borrowers tab

`GET /getBorrowersDashboard/` feeds the Borrowers tab of the admin dashboard
(Figma node `2975:4723`, in section `2654:1893`). Auth is the same as
[`/getCirculationDashboard/`](ADMIN_ANALYTICS.md): `Authorization: Bearer <jwt>` for an
account whose `role` is `admin`, `401` without a token, `403` for any other role,
`405` for methods other than `GET`. The frontend page
(`frontend/src/pages/admin/dashboard/Borrowers.jsx`) exists but is not wired to it yet.
The v1 route `getAdminBorrowerAnalytics/` is removed; the frontend never called it.

Unlike Circulation, which counts every borrower, this tab counts **students only**:
active accounts with role `student`. Faculty and admin loans are left out.

## Query parameters

Same filter bar and same validation as Circulation (`CirculationQuerySerializer`);
see [ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md#query-parameters). What each one does here:

| Param | Values | Default | Effect on Borrowers |
| --- | --- | --- | --- |
| `range` | `day`, `week`, `semester`, `year` | `week` | Window for every card and chart. |
| `item_type` | `all`, `book`, `thesis` | `all` | Filters **loans** by `Books.item_type`. The student population, and so `registered_students`, is unchanged. |
| `program` | `UserProfile.program` string, repeatable | all | Filters the **students** (and therefore their loans). `All` is ignored. |
| `academic_year` | e.g. `2026-2027` | current | Selects the term (with `semester`). `All` is ignored. |
| `semester` | `AcademicTerm.semester`, e.g. `1`, `2` | current | Selects the term. `All` is ignored. |
| `education_level` | `college`, `senior_high` | `college` | Which academic calendar to read. Does **not** filter students: SHS students stay in the counts with `college`. |

Invalid choices return `400` with DRF field errors.

## Windows

Windows, term resolution and `academic_term.status` (`selected` / `not_found` /
`active` / `no_active_term` / `not_configured`) are exactly Circulation's; see
[ADMIN_ANALYTICS.md](ADMIN_ANALYTICS.md#windows). In short: `day` is today vs.
yesterday, `week` is Monday–Sunday vs. last week, `semester` is the resolved term
vs. the previous term, and `year` is the term's academic year (or the last 12
calendar months with no term) vs. the same-length span before.

"vs. previous" uses the same **same-elapsed-span** rule as Circulation's
`change_pct`. Checkouts in the previous window are counted only up to the same
elapsed time (`borrow_date` in `[previous start, previous start + elapsed)`).
Returns use calendar days because `return_date` is a date: the current span is
window start through `min(today, window end)`, `n` days long. The previous span is
the first `n` days of the previous window.

With no previous window (`range=semester` and no earlier term),
`period.previous_start_date` and every `previous`, `change` and `change_pct` are
`null`. With `range=semester` and no resolvable term, `period` is `null`. All cards
except `registered_students` are then `null`, and both chart blocks are `null`, not `[]`.

## Response

```json
{
  "as_of": "2026-10-07T12:00:00+08:00",
  "timezone": "Asia/Manila",
  "filters": {"range": "week", "item_type": "all", "program": [], "academic_year": "", "semester": "", "education_level": "college"},
  "period": {"start_date": "2026-10-05", "end_date": "2026-10-11", "previous_start_date": "2026-09-28"},
  "academic_term": {"status": "active", "term": {"id": 1, "academic_year": "2026-2027", "semester": "1",
                    "education_level": "college", "start_date": "2026-09-01", "end_date": "2027-01-31"}},
  "statistics": {
    "registered_students": 1000,
    "active_borrowers": {"value": 612, "percentage": 61.2},
    "inactive_borrowers": {"value": 388, "percentage": 38.8},
    "total_checkouts": {"value": 1652, "previous": 1500, "change_pct": 10.1},
    "avg_loan_duration_days": {"value": 6.4, "previous": 6.7, "change": -0.3},
    "avg_checkouts_per_borrower": {"value": 2.7, "previous": 2.5, "change": 0.2}
  },
  "borrowing_frequency_by_program": {
    "college": [{"program": "BS in Computer Science", "code": "BSCS", "count": 96}],
    "senior_high": [{"program": "STEM", "code": "STEM", "count": 12}],
    "unassigned": []
  },
  "checkouts_by_day_of_week": [{"day": "Mon", "count": 14}, {"day": "Tue", "count": 0}, "... through Sat (6 rows)"]
}
```

- **Checkout**: Active/Due/Overdue/Returned with a `borrow_date` no later than now,
  borrowed by a counted student, matching `item_type`. Pending and Cancelled never count.
- **Registered students**: current count of counted students. Profiles have no
  registration date, so it is not historical and has no `previous`.
- **Active borrowers**: distinct students with at least one checkout in the window.
  **Inactive** = registered − active. `percentage` = share of registered students,
  one decimal; `null` when there are no registered students.
- **Total checkouts**: `change_pct` follows Circulation's rule: percent change,
  one decimal, `null` when `previous` is 0.
- **Averages** report an absolute `change` (`value − previous`, two decimals,
  `null` if either side is `null`), not a percentage, to match the card text
  ("−0.3 days vs. previous"). `avg_loan_duration_days` = mean of
  (`return_date` − local checkout date) over loans returned in the span, `null` with
  no returns. `avg_checkouts_per_borrower` = window checkouts ÷ active borrowers,
  `null` with no borrowers.
- **Borrowing frequency by programs**: window checkouts per program, grouped into
  `college` / `senior_high` / `unassigned` by the profile's `education_level`. A blank
  level is inferred from the program as at registration (`BS …` means college, SHS
  strands mean senior high). Programs with registered students appear with `0`.
  Sorted by count descending, then name. `code` is the chart label from
  `PROGRAM_CODES` (`BSCS`, `BSN`, …), else the program name; a blank program gives
  `"program": null, "code": "Unspecified"`. Both levels ship, so the College / SHS
  toggle is client-side.
- **Checkouts by day of week**: window checkouts by library-local weekday, always 6
  rows `Mon`…`Sat` with zeros included. The library is closed Sundays, so Sunday
  checkouts are dropped. Labels are Circulation's `WEEKDAYS`.

## Design mapping

The design labels the academic-year dropdown **Term**; Circulation labels it
**Academic Year**. Both send `academic_year`.

| Figma element | JSON |
| --- | --- |
| Filter bar: Item type / Term / Program / Semester term | `item_type` / `academic_year` / `program` / `semester` |
| Day / Week / Semester / Year toggle | `range` |
| Total registered students ("Across all programs") | `statistics.registered_students` |
| Avg. loan duration ("−0.3 days vs. previous") | `statistics.avg_loan_duration_days` |
| Active borrowers ("61% of registered") | `statistics.active_borrowers` |
| Inactive borrowers ("No checkout this semester") | `statistics.inactive_borrowers` |
| Avg. checkouts per borrower ("+0.2 vs. previous") | `statistics.avg_checkouts_per_borrower` |
| Active & Inactive borrowers donut | `statistics.active_borrowers.percentage`, `statistics.inactive_borrowers.percentage` |
| Borrowing frequency by programs, College / SHS toggle | `borrowing_frequency_by_program.college` / `.senior_high` |
| Total checkouts — By day of week | `checkouts_by_day_of_week` |

`statistics.total_checkouts` has no card of its own in the design. It counts
every window checkout, Sundays included, so it can exceed the sum of the
day-of-week rows. The Inactive borrowers caption says "this semester", but the
value follows `range` like every other card.

## Verification

From `backend`:

```powershell
.\venv\Scripts\python.exe -B manage.py test library --settings=backend.test_settings --noinput
```

The tests for this endpoint are in `library/test_borrower_analytics.py`.
