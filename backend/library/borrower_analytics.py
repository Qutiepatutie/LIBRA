"""Borrowers tab of the admin dashboard (Figma `2975:4723`). Contract: backend/ADMIN_BORROWER_ANALYTICS.md

Shares the Circulation tab's filter bar, period windows, term resolution and "vs. previous" rule,
but is scoped to registered students rather than every borrower.
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.db.models.functions import ExtractIsoWeekDay
from django.utils import timezone

from accounts.models import EducationLevel, RoleChoices, UserProfile, education_level_for_program
from .admin_analytics import WEEKDAYS, calendar_terms, circulation_loans, compare, period_window, resolve_term, term_data
from .user_analytics import day_start, library_timezone, library_today


PROGRAM_CODES = {
    'BS in Psychology': 'BSP',
    'BS in Accounting Information System': 'BSAIS',
    'BS in Accountancy': 'BSA',
    'BS in Computer Science': 'BSCS',
    'BS in Information Technology': 'BSIT',
    'BS in International Tourism Management': 'BSITM',
    'BS in Criminology': 'BSCrim',
    'BS in International Hospitality Management': 'BSIHM',
    'BS in Medical Laboratory Science': 'BSMLS',
    'BS in Physical Therapy': 'BSPT',
    'BS in Pharmacy': 'BSPharm',
    'BS in Nursing': 'BSN',
}


def education_level_of(education_level, program):
    # Profiles saved before the field existed are grouped the way registration would classify them.
    return education_level or education_level_for_program(program) or 'unassigned'


def registered_students(programs):
    students = UserProfile.objects.filter(user__role=RoleChoices.STUDENT, user__is_active=True)
    return students.filter(program__in=programs) if programs else students


def ratio(numerator, denominator, places=2):
    return round(numerator / denominator, places) if denominator else None


def share(part, whole):
    return {'value': part, 'percentage': ratio(part * 100, whole, 1)}


def difference(current, previous):
    change = None if current is None or previous is None else round(current - previous, 2)
    return {'value': current, 'previous': previous, 'change': change}


def span_statistics(loans, returns):
    totals = loans.aggregate(checkouts=Count('pk'), borrowers=Count('user', distinct=True))
    durations = [(returned_on - library_today(borrowed_at)).days
                 for borrowed_at, returned_on in returns.values_list('borrow_date', 'return_date')]
    return {**totals, 'avg_duration': ratio(sum(durations), len(durations)),
            'per_borrower': ratio(totals['checkouts'], totals['borrowers'])}


def window_statistics(loans, start, end, previous_start, now):
    today = library_today(now)
    in_window = loans.filter(borrow_date__gte=day_start(start), borrow_date__lt=day_start(end))
    # return_date is a date, so the elapsed span is counted in whole days up to today.
    last_return = min(today, end - timedelta(days=1))
    current = span_statistics(in_window, loans.filter(return_date__gte=start, return_date__lte=last_return))
    if previous_start is None:
        return current, None
    elapsed = max(min(now, day_start(end)) - day_start(start), timedelta(0))
    days = max((last_return - start).days + 1, 0)
    previous = span_statistics(
        loans.filter(borrow_date__gte=day_start(previous_start), borrow_date__lt=day_start(previous_start) + elapsed),
        loans.filter(return_date__gte=previous_start, return_date__lt=previous_start + timedelta(days=days)),
    )
    return current, previous


def frequency_by_program(students, loans):
    rows = {}
    # Programs with registered students appear even with no checkouts in the period.
    for profile in students.values('education_level', 'program').distinct().order_by():
        rows.setdefault((profile['education_level'], profile['program'] or None), 0)
    for row in loans.values('user__education_level', 'user__program').annotate(count=Count('pk')).order_by():
        key = (row['user__education_level'], row['user__program'] or None)
        rows[key] = rows.get(key, 0) + row['count']
    grouped = {EducationLevel.COLLEGE.value: {}, EducationLevel.SENIOR_HIGH.value: {}, 'unassigned': {}}
    for (education_level, program), count in rows.items():
        programs = grouped[education_level_of(education_level, program)]
        programs[program] = programs.get(program, 0) + count
    return {level: [
        {'program': program, 'code': PROGRAM_CODES.get(program, program) if program else 'Unspecified',
         'count': count}
        for program, count in sorted(programs.items(), key=lambda item: (-item[1], item[0] or ''))
    ] for level, programs in grouped.items()}


def checkouts_by_weekday(loans):
    rows = loans.annotate(weekday=ExtractIsoWeekDay('borrow_date', tzinfo=library_timezone())) \
        .values('weekday').annotate(count=Count('pk')).order_by()
    counts = {row['weekday']: row['count'] for row in rows}
    # ISO weekday 7 (Sunday) has no row: the library is closed.
    return [{'day': day, 'count': counts.get(index, 0)} for index, day in enumerate(WEEKDAYS, start=1)]


def borrowers_dashboard(params, now):
    today = library_today(now)
    students = registered_students(params['program'])
    # circulation_loans applies item_type (and program again, harmlessly); restrict it to the students counted.
    loans = circulation_loans(params, now).filter(user__in=students)
    terms = calendar_terms(params['education_level'])
    term_status, term = resolve_term(terms, params, today)
    window = period_window(params['range'], today, term, terms)
    registered = students.count()
    statistics = dict.fromkeys(('active_borrowers', 'inactive_borrowers', 'total_checkouts',
                                'avg_loan_duration_days', 'avg_checkouts_per_borrower'))
    period = frequency = weekdays = None
    if window:
        start, end, previous_start = window
        current, previous = window_statistics(loans, start, end, previous_start, now)
        earlier = previous or {}
        active = current['borrowers']
        statistics = {
            'active_borrowers': share(active, registered),
            'inactive_borrowers': share(registered - active, registered),
            'total_checkouts': compare(current['checkouts'], earlier.get('checkouts')),
            'avg_loan_duration_days': difference(current['avg_duration'], earlier.get('avg_duration')),
            'avg_checkouts_per_borrower': difference(current['per_borrower'], earlier.get('per_borrower')),
        }
        period = {'start_date': start.isoformat(), 'end_date': (end - timedelta(days=1)).isoformat(),
                  'previous_start_date': previous_start.isoformat() if previous_start else None}
        in_window = loans.filter(borrow_date__gte=day_start(start), borrow_date__lt=day_start(end))
        frequency = frequency_by_program(students, in_window)
        weekdays = checkouts_by_weekday(in_window)
    return {
        'as_of': timezone.localtime(now, library_timezone()).isoformat(),
        'timezone': settings.LIBRARY_TIME_ZONE,
        'filters': params,
        'period': period,
        'academic_term': {'status': term_status, 'term': term_data(term)},
        'statistics': {'registered_students': registered, **statistics},
        'borrowing_frequency_by_program': frequency,
        'checkouts_by_day_of_week': weekdays,
    }
