# Admin dashboard analytics — Circulation tab

`GET /getCirculationDashboard/` feeds the Circulation tab of the admin dashboard
(Figma node `2654:1893`). It requires `Authorization: Bearer <jwt>` and an account
whose `role` is `admin`: `401` without a token, `403` for any other role. The
legacy `?id_number=` check used by `/adminAnalyticsDashboard/` is not used here.

## Query parameters

| Param | Values | Default | Effect |
| --- | --- | --- | --- |
| `range` | `day`, `week`, `semester`, `year` | `week` | Window for the cards, line chart and top 10. |
| `item_type` | `all`, `book`, `thesis` | `all` | Filters loans by `Books.item_type`. |
| `program` | `UserProfile.program` string, repeatable | all | `?program=BS Nursing&program=BS Pharmacy` groups a college. `All` is ignored. |
| `academic_year` | e.g. `2026-2027` | current | Selects the term (with `semester`). `All` is ignored. |
| `semester` | `AcademicTerm.semester`, e.g. `1`, `2` | current | Selects the term. |
| `education_level` | `college`, `senior_high` | `college` | Which academic calendar to read. Does not filter borrowers. |

Invalid choices return `400` with DRF field errors.

## Windows

All boundaries are library-local (`Asia/Manila`). Only real checkouts count
(Active/Due/Overdue/Returned with a `borrow_date`); Pending and Cancelled never do.

| `range` | Window | Chart buckets | Previous window |
| --- | --- | --- | --- |
| `day` | today | hourly `07:00`…`19:00` (checkouts outside library hours are left off the chart) | yesterday |
| `week` | Monday–Sunday of this week | `Mon`…`Sat` (closed Sundays) | last week |
| `semester` | the resolved term | `W1`…`Wn`, Monday-aligned term weeks | the previous term |
| `year` | the term's academic year (`AcademicYear` timeline, else span of its terms); with no term, the last 12 calendar months | `YYYY-MM` | the same-length span just before |

`change_pct` compares a running window with the **same elapsed span** of the previous
window (Wednesday noon vs. last Wednesday noon), and is `null` when the previous value
is 0 or there is no previous term.

The term is resolved from the `education_level` default calendar (cohort overrides are
ignored): an explicit `academic_year`/`semester` gives `selected` (or `not_found`);
otherwise the term running today gives `active`, else `no_active_term` /
`not_configured`. With `range=semester` and no term, `period`, `borrows`,
`active_borrowers` and the chart are empty.

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
    "borrows": {"value": 12, "previous": 10, "change_pct": 20.0},
    "active_borrowers": {"value": 9, "previous": 8, "change_pct": 12.5},
    "currently_overdue": {"value": 7, "week_ago": 1, "change": 6}
  },
  "total_checkouts": [{"label": "Mon", "start": "2026-10-05", "count": 4}],
  "top_borrowed": {
    "book": [{"title": "Introduction to Algorithms", "author": "Cormen", "count": 48}],
    "thesis": []
  },
  "peak_periods": {
    "academic_year": "2026-2027",
    "terms": [{"id": 1, "academic_year": "2026-2027", "semester": "1", "education_level": "college",
               "start_date": "2026-09-01", "end_date": "2027-01-31", "weeks": 22,
               "cells": [[0, 3, 1], [2, 0, 0]], "scale": {"max": 3, "total": 6}}]
  }
}
```

- **Cards**: `borrows` = checkouts in the window; `active_borrowers` = distinct borrowers
  with a checkout in the window; `currently_overdue` = loans still out past their due
  date today vs. 7 days ago, derived from dates rather than stored status. The
  overdue card ignores `range` but honours `item_type` and `program`. The semester
  timeline card reads `academic_term`.
- **Top 10**: ranked by checkouts in the window, grouped by title + author so copies
  rank together. Both lists ship in one response so the Books/Thesis toggle is
  client-side.
- **Peak borrowing periods**: one grid per term of the resolved academic year (or the
  latest configured one), so the 1st Sem / 2nd Sem / Summer buttons are client-side.
  `cells[d][w]` with `d` = 0 Mon … 5 Sat and `w` = term week; Sunday checkouts are
  dropped and `scale` is computed from the grid. Ignores `range`.

## Item type

`Books.item_type` (`book` default, `thesis` for hard-bound capstone research) was added
in migration `0007_books_item_type`; existing rows become `book`. It is exposed on
`getBooks/` and accepted by `addBook/`.
