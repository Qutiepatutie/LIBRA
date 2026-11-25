# Recommended books: designer handoff

## Where the slot is
`frontend/src/components/library/showbook/ShowBook.jsx`, inside `<div className={styles.recommendationContainer}>` > `<div className={styles.recommendations}>`. It renders only when `role !== "admin"`.

## What it shows now
Up to 4 `BookPanel` cards, or the empty message `No similar items yet.` (your `comingSoonContainer` markup with `libby`). Clicking a card opens that item in the same modal and loads its own recommendations. While loading, or on error, the slot is empty.

## Fields the API returns that are not shown yet
Each item is `{ book, availability, reason, score? }`.
- Book or Thesis: from `book.item_type`.
- `availability`: `available` or `all_out`. Suggested labels: `Available` / `All copies out`.
- `reason`: list of labels, suggested display `Shares: …`.
- `score`: admins only.

`BookPanel` has no place for these yet.

## Notes
- Theses usually have no cover, and `BookPanel` shows an empty image for them.
- The `/*TEMP*/` styles on `.recommendationContainer` and `.recommendations` are still in place.
- Whether admins should see the row (with scores) is your decision. It is hidden for admins today.
- `useRecommendations.js` holds the fetching logic and needs no change.
