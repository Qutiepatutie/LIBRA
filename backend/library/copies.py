"""Copy availability, derived on every read; there is no stored "available" flag."""
from django.db.models import Count, Exists, IntegerField, Max, OuterRef, Prefetch, Subquery
from django.db.models.functions import Coalesce

from .models import BookCopy, Books, BorrowRecords, ConditionChoices, StatusChoices
from .user_analytics import OPEN_STATUSES


# A pending request already reserves its copy, so it holds the copy like a checkout.
HOLD_STATUSES = (StatusChoices.PENDING, *OPEN_STATUSES)


def available_copies(book=None):
    """Circulating copies with no hold-status loan, optionally for one title, by copy number."""
    held = BorrowRecords.objects.filter(copy=OuterRef('pk'), status__in=HOLD_STATUSES)
    copies = BookCopy.objects.filter(is_archived=False, condition=ConditionChoices.GOOD).filter(~Exists(held))
    if book is not None:
        copies = copies.filter(book=book)
    return copies.order_by('copy_number')


def _count_per_title(copies):
    # A subquery per count, not a join, so other annotations on the caller's queryset stay exact.
    counts = copies.filter(book=OuterRef('pk')).order_by().values('book').annotate(n=Count('pk')).values('n')
    return Coalesce(Subquery(counts, output_field=IntegerField()), 0)


def with_copy_counts(books_qs):
    """Annotate titles with total_copies (non-archived) and available_copies."""
    return books_qs.annotate(
        total_copies=_count_per_title(BookCopy.objects.filter(is_archived=False)),
        available_copies=_count_per_title(available_copies()),
    )


def with_availability(copies_qs):
    """Annotate is_available from the single rule above, so listing copies costs no query per copy."""
    return copies_qs.annotate(is_available=Exists(available_copies().filter(pk=OuterRef("pk"))))


def catalog_books(books_qs):
    """Titles with copy counts and the non-archived copies (listed_copies) the catalog serializer reads."""
    listed = with_availability(BookCopy.objects.filter(is_archived=False)).order_by("copy_number")
    return with_copy_counts(books_qs).prefetch_related(
        Prefetch("copies", queryset=listed, to_attr="listed_copies"),
    )


AVAILABLE = "available"
ALL_OUT = "all_out"
HIDDEN = "hidden"


def title_availability(book_ids):
    """Map title id to AVAILABLE, ALL_OUT or HIDDEN in one query; ids not found are absent."""
    good = BookCopy.objects.filter(book=OuterRef("pk"), is_archived=False, condition=ConditionChoices.GOOD)
    rows = Books.objects.filter(pk__in=list(book_ids)).annotate(
        has_good=Exists(good),
        has_free=Exists(available_copies().filter(book=OuterRef("pk"))),
    ).values_list("pk", "has_good", "has_free")
    return {pk: AVAILABLE if free else ALL_OUT if good_copy else HIDDEN for pk, good_copy, free in rows}


def assign_copy(book):
    """Return the lowest-numbered available copy of a title, or None. Call inside transaction.atomic().

    The title row is locked, not the copy rows: a concurrent request only adds a loan row and
    leaves the copy row untouched, so a copy lock would not make the second request re-check.
    """
    book_id = getattr(book, 'pk', book)
    if Books.objects.select_for_update().filter(pk=book_id).first() is None:
        return None
    return available_copies(book_id).first()


def next_copy_number(book):
    """Highest copy number so far, archived copies included, plus one."""
    highest = BookCopy.objects.filter(book=book).aggregate(highest=Max('copy_number'))['highest']
    return (highest or 0) + 1
