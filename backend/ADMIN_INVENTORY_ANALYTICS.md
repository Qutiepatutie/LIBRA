# Admin dashboard: Inventory tab API

Backend contract for Figma `Admin Dashboard` → Inventory tab (`2975:5293`). Code
lives in `library/inventory_analytics.py`. It only adds the backend. The frontend
isn't wired to it yet.

`GET /getInventoryDashboard/` takes no parameters. It requires
`Authorization: Bearer <access token>` for an account whose `role` is `admin`. It
returns `401` without a token, `403` for other roles and `405` for other methods.

This branch also removes the legacy `/adminAnalyticsDashboard/` route, its
`admin_role` decorator (`library/decorators.py`) and the three helpers it called
(`circulation_trends`, `borrowing_frequency`, `inventory_status`). That route took
`?id_number=` from the query string, so anyone who knew an admin's ID number could
call it. `getCirculationDashboard/` replaces the circulation helper, the Borrowers
tab endpoint replaces the frequency helper, and this endpoint replaces
`inventory_status`.

## Response

```json
{
  "as_of": "2026-10-07T12:00:00+08:00",
  "timezone": "Asia/Manila",
  "statistics": {
    "total_copies": 4249,
    "available": {"value": 3820, "percentage": 89.9},
    "borrowed": {"value": 412, "percentage": 9.7},
    "overdue": {"value": 58, "percentage": 1.4},
    "lost_damaged": {"value": 17, "percentage": 0.4}
  },
  "overdue_items": [{"loan_id": 7, "borrower_id": "2023-0142", "borrower": "Ana Cruz",
                     "title": "Operating System Concepts", "call_number": "005.43 S5",
                     "due_date": "2026-09-12", "days_overdue": 25}]
}
```

- Each copy (`Books` row) counts in exactly one of `available`, `borrowed` or
  `lost_damaged`, so the three add up to `total_copies`.
  - `borrowed`: good copies on an open checkout (Active/Due/Overdue with no
    `return_date`).
  - Pending requests stay `available`.
  - A lost or damaged copy counts as `lost_damaged` even when it is on loan.
- `overdue` counts every open checkout past its due date, from dates rather than stored
  status, including loans on copies since marked lost. It sits outside the three-way
  split.
- `percentage` is a share of `total_copies`, and is `null` when the collection is
  empty.
- `overdue_items` lists every overdue loan (no cap), most days overdue first. Dates
  use `LIBRARY_TIME_ZONE` (Asia/Manila).

## `Books.condition`

| Value | Meaning |
| --- | --- |
| `good` (default) | In the circulating collection |
| `lost` | Missing; left out of `available` and `borrowed` |
| `damaged` | Out of circulation until repaired |

Migration `0011_books_condition` adds it with a default, so existing rows become
`good`. `getBooks/` returns it and `addBook/` accepts it. `editBook/` accepts
`condition` (and `itemType`), and an unknown value returns `400`.

## Deploy notes

- Based on `main` after the room-reservation merge. `0011_books_condition` follows
  `0010_alter_borrowrecords_status_and_more`, so the `library` graph has one leaf and
  `migrate` adds only the `condition` column (default `good`).
- `IsAdminRole` and `Books.item_type` come from the Circulation tab (PR #10), which
  is already on `main`.
