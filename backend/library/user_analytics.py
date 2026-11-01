"""Read models for the authenticated borrower's dashboard (not admin analytics)."""
from collections import Counter
from datetime import date, datetime, time, timedelta
from decimal import Decimal
import re
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from .models import AcademicTerm, BorrowRecords, LoanFine, StatusChoices, effective_academic_terms


OPEN_STATUSES = (StatusChoices.ACTIVE, StatusChoices.DUE, StatusChoices.OVERDUE)
CHECKOUT_STATUSES = (*OPEN_STATUSES, StatusChoices.RETURNED)
SUBJECTS = (
    ('001', 'General Information'), ('100', 'Philosophy & Psychology'),
    ('200', 'Religion'), ('300', 'Social Sciences'), ('400', 'Language'),
    ('500', 'Science'), ('600', 'Technology'), ('700', 'Arts & Recreation'),
    ('800', 'Literature'), ('900', 'History & Geography'),
)


def library_timezone():
    return ZoneInfo(settings.LIBRARY_TIME_ZONE)


def library_today(now=None):
    return timezone.localdate(now or timezone.now(), library_timezone())


def day_start(day):
    return datetime.combine(day, time.min, tzinfo=library_timezone())


def actual_loans(profile, now):
    return BorrowRecords.objects.filter(
        user=profile, status__in=CHECKOUT_STATUSES, borrow_date__lte=now,
    )


def current_loans(profile, now):
    # Pending requests belong in the table, but not in any checkout aggregate.
    return BorrowRecords.objects.filter(user=profile, return_date__isnull=True).filter(
        Q(status=StatusChoices.PENDING)
        | Q(status__in=OPEN_STATUSES, borrow_date__lte=now)
    )


def current_term(profile, today):
    # year_level is optional; without it the student follows the default calendar.
    if not profile.education_level:
        return 'profile_incomplete', None
    terms = list(AcademicTerm.objects.filter(education_level=profile.education_level))
    effective = effective_academic_terms(terms, profile.year_level)
    if not effective:
        return 'not_configured', None
    active = [term for term in effective if term.start_date <= today <= term.end_date]
    if len(active) > 1:
        return 'conflict', None
    if not active:
        return 'no_active_term', None
    return 'active', active[0]


def money(amount):
    return format(amount or Decimal('0'), '.2f')


def fine_totals(profile):
    totals = LoanFine.objects.filter(loan__user=profile).aggregate(
        assessed=Sum('amount_assessed'), paid=Sum('amount_paid'),
    )
    assessed, paid = totals['assessed'] or Decimal('0'), totals['paid'] or Decimal('0')
    return {'currency': 'PHP', 'amount_assessed': money(assessed),
            'amount_paid': money(paid), 'outstanding': money(assessed - paid)}


def history_summary(profile, now):
    today = library_today(now)
    loans = actual_loans(profile, now)
    totals = loans.aggregate(
        total_borrowed=Count('pk'),
        overdue=Count('pk', filter=Q(status__in=OPEN_STATUSES, return_date__isnull=True, due_date__lt=today)),
        late_returned=Count('pk', filter=Q(return_date__gt=F('due_date'), return_date__lte=today)),
    )
    return {**totals, 'fine': fine_totals(profile)}


def borrowing_frequency(loans, today):
    # Six calendar months, including the current month; preserve empty buckets.
    month_index = today.year * 12 + today.month - 1
    months = [date(index // 12, index % 12 + 1, 1) for index in range(month_index - 5, month_index + 1)]
    rows = loans.filter(borrow_date__gte=day_start(months[0])).annotate(
        month=TruncMonth('borrow_date', tzinfo=library_timezone()),
    ).values('month').annotate(count=Count('pk')).order_by('month')
    counts = {row['month'].strftime('%Y-%m'): row['count'] for row in rows}
    return [{'month': month.strftime('%Y-%m'), 'count': counts.get(month.strftime('%Y-%m'), 0)} for month in months]


def borrowed_subjects(loans):
    counts = Counter()
    # Aggregate per catalog call number in SQL instead of loading every loan.
    for row in loans.values('book__call_number').annotate(count=Count('pk')).order_by():
        prefix = re.match(r'^\s*([0-9]{3})(?![0-9])', row['book__call_number'])
        subject = SUBJECTS[int(prefix[1]) // 100] if prefix else ('unclassified', 'Unclassified')
        counts[subject] += row['count']
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0][0]))
    total = sum(counts.values())
    visible = ranked[:5]
    if len(ranked) > 5:
        visible.append((('other', 'Other'), sum(count for _, count in ranked[5:])))
    return {'total_borrowed': total, 'subjects': [
        {'code': code, 'label': label, 'count': count, 'percentage': round(count * 100 / total, 2)}
        for (code, label), count in visible
    ]}


def dashboard(profile, now):
    today = library_today(now)
    saturday = today + timedelta(days=(5 - today.weekday()) % 7)
    loans = actual_loans(profile, now)
    open_loans = loans.filter(status__in=OPEN_STATUSES, return_date__isnull=True)
    statistics = open_loans.aggregate(
        currently_borrowed=Count('pk'),
        due_soon=Count('pk', filter=Q(due_date__range=(today, saturday))),
        overdue=Count('pk', filter=Q(due_date__lt=today)),
    )
    term_status, term = current_term(profile, today)
    statistics['books_this_semester'] = loans.filter(
        borrow_date__gte=day_start(term.start_date),
        borrow_date__lt=day_start(term.end_date + timedelta(days=1)),
    ).count() if term else None
    term_data = None if term is None else {
        'id': term.pk, 'academic_year': term.academic_year, 'semester': term.semester,
        'education_level': term.education_level, 'year_level': term.year_level or None,
        'start_date': term.start_date.isoformat(), 'end_date': term.end_date.isoformat(),
    }
    return {
        'as_of': timezone.localtime(now, library_timezone()).isoformat(),
        'timezone': settings.LIBRARY_TIME_ZONE,
        'statistics': statistics,
        'academic_term': {'status': term_status, 'term': term_data},
        'due_soon_window': {'start_date': today.isoformat(), 'end_date': saturday.isoformat()},
        'borrowing_frequency': borrowing_frequency(loans, today),
        'most_borrowed_subjects': borrowed_subjects(loans),
        'history_summary': history_summary(profile, now),
    }
