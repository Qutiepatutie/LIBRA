from django.conf import settings
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField, Q
from django.db.models.functions import ExtractHour, TruncDate, TruncMonth
from datetime import date, timedelta
from django.utils import timezone

from .models import AcademicTerm, AcademicYear, BorrowRecords, Books, ItemType, StatusChoices, effective_academic_terms
from .user_analytics import CHECKOUT_STATUSES, OPEN_STATUSES, day_start, library_timezone, library_today

def circulation_trends():
    cutoff = timezone.now() - timedelta(days=365) #Gets Data from today to 365 days ago (1 year)

    monthly_borrows = (BorrowRecords.objects
        .filter(borrow_date__gte=cutoff,
        borrow_date__isnull=False)
        .annotate(month=TruncMonth('borrow_date'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month'))

    monthly_returns = (BorrowRecords.objects
        .filter(return_date__gte=cutoff.date(),
        status=StatusChoices.RETURNED)
        .annotate(month=TruncMonth('return_date'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month'))

    monthly_overdue = (BorrowRecords.objects
        .filter(borrow_date__gte=cutoff.date(),
        status=StatusChoices.OVERDUE)
        .annotate(month=TruncMonth('due_date'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month'))
    
    bucket = {}
    for r in monthly_borrows:
        key = r['month'].strftime('%Y-%m')
        bucket.setdefault(key, {'month': key, 'borrows': 0, 'returns': 0, 'overdue': 0})
        bucket[key]['borrows'] = r['count']
    for r in monthly_returns:
        key = r['month'].strftime('%Y-%m')
        bucket.setdefault(key, {'month': key, 'borrows':0, 'returns': 0, 'overdue': 0})
        bucket[key]['returns'] = r['count']
    for r in monthly_overdue:
        key = r['month'].strftime('%Y-%m')
        bucket.setdefault(key,{'month' : key, 'borrows': 0, 'returns': 0, 'overdue':0})
        bucket[key]['overdue'] = r['count']  

    totals = {
        'borrows': BorrowRecords.objects.filter(borrow_date__gte=cutoff).count(),
        'returns': BorrowRecords.objects.filter(status=StatusChoices.RETURNED).count(),
        'overdue': BorrowRecords.objects.filter(status=StatusChoices.OVERDUE).count(),
        'active' : BorrowRecords.objects.filter(status=StatusChoices.ACTIVE).count(),
    }
    return {'monthly': sorted(bucket.values(),key=lambda x: x['month']), 'totals' : totals}

  # Borrow counts grouped by month (last 12 months)
  # Active vs Returned vs Overdue breakdown per month
  # Total borrows, returns, overdue count
def borrowing_frequency():
    top_books = list(BorrowRecords.objects
        .values('book__title', 'book__author', 'book__isbn')
        .annotate(count=Count('id'))
        .order_by('-count')[:10])

    top_borrowers = list(BorrowRecords.objects
        .values('user__id_number', 'user__first_name', 'user__last_name')
        .annotate(count=Count('id'))
        .order_by('-count')[:10])

    returned = BorrowRecords.objects.filter(
        status=StatusChoices.RETURNED,
        borrow_date__isnull=False,
        return_date__isnull=False,
    )

    durations = [(r.return_date - r.borrow_date.date()).days for r in returned]
    avg_days = round(sum(durations) / len(durations), 2) if durations else 0

    by_role = dict(BorrowRecords.objects
        .values('user__user__role') #BorrowRecords.user -> UserProfile.user -> UserLogin.role
        .annotate(count=Count('id'))
        .values_list('user__user__role', 'count'))

    return {
        'top_books': [
           {'title': b['book__title'],
           'author': b['book__author'],
           'isbn': b['book__isbn'],
           'count': b['count']}
           for b in top_books 
        ],
        'top_borrowers': [
            {'id_number': u['user__id_number'],
            'name': f"{u['user__first_name']} {u['user__last_name']}",
            'count': u['count']}

            for u in top_borrowers
        ],
        'by_role': by_role,
        'avg_duration_days': avg_days,
    }
 # Top 10 most borrowed books (title, count)
 # Top borrowers (name, count)
 # Average borrow duration
 # Borrows by user role (student vs faculty)
def inventory_status():
    total = Books.objects.count()
    active_statuses = [StatusChoices.ACTIVE,
    StatusChoices.DUE, StatusChoices.OVERDUE]

    borrowed_books_ids = set(BorrowRecords.objects
        .filter(status__in=active_statuses,
        return_date__isnull=True)
        .values_list('book_id', flat=True))

    overdue_items = list(BorrowRecords.objects
    .filter(status=StatusChoices.OVERDUE,
    return_date__isnull=True)
    .select_related('book', 'user')
    .values(
        'book__title', 'book__call_number',
        'user__first_name', 'user__last_name',
        'user__id_number', 'due_date',
    )[:50])

    borrowed_ever = set(BorrowRecords.objects
    .values_list('book_id', flat=True).distinct())
    never_borrowed = Books.objects.exclude(id__in=borrowed_ever).count()

    return {
        'total_books': total,
        'borrowed_out': len(borrowed_books_ids),
        'available': total - len
        (borrowed_books_ids),
        'overdue_items': [{
            'title':        o['book__title'],
            'call_number':  o['book__call_number'],
            'borrower':  f"{o['user__first_name']} {o['user__last_name']}",
            'borrower_id':  o['user__id_number'],
            'due_date':     o['due_date'].isoformat() if o['due_date']
            else None,
        } for o in overdue_items],
        'never_borrowed_count': never_borrowed
    }
 #Total books in collection
 # Currently borrowed out (active/due/overdue count)
 # Available books count
 # Overdue books list (book title, borrower, due date)
 # Books never borrowed

# READ DASHBOARD_PLAN.md for more information (NOTE FOR ME)
# -Shawnlee


# Circulation tab of the admin dashboard. Contract: backend/ADMIN_ANALYTICS.md

LIBRARY_HOURS = range(7, 20)  # hourly buckets 07:00 through 19:00 (closes 20:00)
WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat')  # closed Sundays
TOP_LIMIT = 10


def circulation_loans(params, now):
    # Actual checkouts only; pending and cancelled requests never left the shelf.
    loans = BorrowRecords.objects.filter(status__in=CHECKOUT_STATUSES, borrow_date__lte=now)
    if params['item_type'] != 'all':
        loans = loans.filter(book__item_type=params['item_type'])
    if params['program']:
        loans = loans.filter(user__program__in=params['program'])
    return loans


def calendar_terms(education_level):
    # Library-wide views use the default calendar, not year-level cohort overrides.
    terms = effective_academic_terms(list(AcademicTerm.objects.filter(education_level=education_level)), None)
    return sorted(terms, key=lambda term: term.start_date)


def resolve_term(terms, params, today):
    year, semester = params['academic_year'], params['semester']
    if year or semester:
        matches = [term for term in terms if (not year or term.academic_year == year)
                   and (not semester or term.semester == semester)]
        if not matches:
            return 'not_found', None
        # A partial selection prefers the running term, then the latest one already started.
        running = [term for term in matches if term.start_date <= today <= term.end_date]
        started = [term for term in matches if term.start_date <= today]
        return 'selected', (running or started or matches)[-1]
    if not terms:
        return 'not_configured', None
    running = [term for term in terms if term.start_date <= today <= term.end_date]
    return ('active', running[-1]) if running else ('no_active_term', None)


def term_data(term):
    return None if term is None else {
        'id': term.pk, 'academic_year': term.academic_year, 'semester': term.semester,
        'education_level': term.education_level,
        'start_date': term.start_date.isoformat(), 'end_date': term.end_date.isoformat(),
    }


def academic_year_span(term, terms):
    timeline = term.academic_year_timeline or AcademicYear.objects.filter(
        academic_year=term.academic_year, education_level=term.education_level,
    ).filter(Q(year_level__isnull=True) | Q(year_level='')).first()
    if timeline:
        return timeline.start_date, timeline.end_date
    same_year = [other for other in terms if other.academic_year == term.academic_year]
    return same_year[0].start_date, max(other.end_date for other in same_year)


def month_start(day, offset=0):
    index = day.year * 12 + day.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def period_window(range_, today, term, terms):
    """(start, end) as library-local dates with `end` exclusive, plus the previous period's start."""
    if range_ == 'day':
        return today, today + timedelta(days=1), today - timedelta(days=1)
    if range_ == 'week':
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=7), start - timedelta(days=7)
    if range_ == 'semester':
        if term is None:
            return None
        earlier = [other for other in terms if other.start_date < term.start_date]
        return term.start_date, term.end_date + timedelta(days=1), earlier[-1].start_date if earlier else None
    if term is not None:
        start, last = academic_year_span(term, terms)
        end = last + timedelta(days=1)
    else:
        # No academic calendar to anchor on: twelve calendar months including this one.
        start, end = month_start(today, -11), month_start(today, 1)
    return start, end, start - (end - start)


def compare(current, previous):
    change = round((current - previous) * 100 / previous, 1) if previous else None
    return {'value': current, 'previous': previous, 'change_pct': change}


def window_statistics(loans, start, end, previous_start, now):
    current = loans.filter(borrow_date__gte=day_start(start), borrow_date__lt=day_start(end))
    # Compare like with like: a running period against the same elapsed span of the previous one.
    elapsed = max(min(now, day_start(end)) - day_start(start), timedelta(0))
    previous = None if previous_start is None else loans.filter(
        borrow_date__gte=day_start(previous_start), borrow_date__lt=day_start(previous_start) + elapsed,
    )
    return {
        'borrows': compare(current.count(), previous.count() if previous is not None else None),
        'active_borrowers': compare(
            current.values('user').distinct().count(),
            previous.values('user').distinct().count() if previous is not None else None,
        ),
    }


def overdue_on(loans, day):
    # Date-derived, like the user dashboard: stored statuses are not flipped to Overdue.
    return loans.filter(borrow_date__lt=day_start(day + timedelta(days=1)), due_date__lt=day).filter(
        Q(return_date__isnull=True, status__in=OPEN_STATUSES) | Q(return_date__gt=day),
    ).count()


def daily_counts(loans):
    rows = loans.annotate(day=TruncDate('borrow_date', tzinfo=library_timezone())).values('day').annotate(count=Count('pk'))
    return {row['day']: row['count'] for row in rows}


def checkout_series(window, range_, start, end):
    if range_ == 'day':
        rows = window.annotate(hour=ExtractHour('borrow_date', tzinfo=library_timezone())).values('hour').annotate(count=Count('pk'))
        counts = {row['hour']: row['count'] for row in rows}
        return [{'label': f'{hour:02d}:00', 'start': (day_start(start) + timedelta(hours=hour)).isoformat(),
                 'count': counts.get(hour, 0)} for hour in LIBRARY_HOURS]
    if range_ == 'year':
        rows = window.annotate(month=TruncMonth('borrow_date', tzinfo=library_timezone())).values('month').annotate(count=Count('pk'))
        counts = {row['month'].strftime('%Y-%m'): row['count'] for row in rows}
        months, month = [], month_start(start)
        while month < end:
            months.append(month)
            month = month_start(month, 1)
        return [{'label': month.strftime('%Y-%m'), 'start': month.isoformat(),
                 'count': counts.get(month.strftime('%Y-%m'), 0)} for month in months]
    counts = daily_counts(window)
    if range_ == 'week':
        days = [start + timedelta(days=offset) for offset in range(len(WEEKDAYS))]
        return [{'label': WEEKDAYS[day.weekday()], 'start': day.isoformat(), 'count': counts.get(day, 0)} for day in days]
    first_monday = start - timedelta(days=start.weekday())
    weeks = [0] * ((end - timedelta(days=1) - first_monday).days // 7 + 1)
    for day, count in counts.items():
        weeks[(day - first_monday).days // 7] += count
    return [{'label': f'W{index + 1}', 'start': max(first_monday + timedelta(weeks=index), start).isoformat(),
             'count': count} for index, count in enumerate(weeks)]


def top_borrowed(window):
    # Group by work rather than copy, so several copies of one title rank together.
    def ranked(item_type):
        rows = (window.filter(book__item_type=item_type)
                .values('book__title', 'book__author').annotate(count=Count('pk'))
                .order_by('-count', 'book__title')[:TOP_LIMIT])
        return [{'title': row['book__title'], 'author': row['book__author'], 'count': row['count']} for row in rows]
    return {item_type: ranked(item_type) for item_type in ItemType.values}


def term_heatmap(loans, term):
    first_monday = term.start_date - timedelta(days=term.start_date.weekday())
    weeks = (term.end_date - first_monday).days // 7 + 1
    cells = [[0] * weeks for _ in WEEKDAYS]  # cells[d][w], d = date.weekday()
    term_loans = loans.filter(borrow_date__gte=day_start(term.start_date),
                              borrow_date__lt=day_start(term.end_date + timedelta(days=1)))
    for day, count in daily_counts(term_loans).items():
        if day.weekday() < len(WEEKDAYS):
            cells[day.weekday()][(day - first_monday).days // 7] += count
    flat = [count for row in cells for count in row]
    # Totals come from the grid so stray Sunday records cannot make them disagree.
    return {**term_data(term), 'weeks': weeks, 'cells': cells,
            'scale': {'max': max(flat), 'total': sum(flat)}}


def peak_periods(loans, terms, term):
    academic_year = term.academic_year if term else (terms[-1].academic_year if terms else None)
    return {'academic_year': academic_year,
            'terms': [term_heatmap(loans, other) for other in terms if other.academic_year == academic_year]}


def circulation_dashboard(params, now):
    today = library_today(now)
    loans = circulation_loans(params, now)
    terms = calendar_terms(params['education_level'])
    term_status, term = resolve_term(terms, params, today)
    window = period_window(params['range'], today, term, terms)
    overdue_now, overdue_week_ago = overdue_on(loans, today), overdue_on(loans, today - timedelta(days=7))
    statistics = {'borrows': None, 'active_borrowers': None}
    period, series, top = None, [], {item_type: [] for item_type in ItemType.values}
    if window:
        start, end, previous_start = window
        in_window = loans.filter(borrow_date__gte=day_start(start), borrow_date__lt=day_start(end))
        statistics = window_statistics(loans, start, end, previous_start, now)
        period = {'start_date': start.isoformat(), 'end_date': (end - timedelta(days=1)).isoformat(),
                  'previous_start_date': previous_start.isoformat() if previous_start else None}
        series = checkout_series(in_window, params['range'], start, end)
        top = top_borrowed(in_window)
    statistics['currently_overdue'] = {'value': overdue_now, 'week_ago': overdue_week_ago,
                                       'change': overdue_now - overdue_week_ago}
    return {
        'as_of': timezone.localtime(now, library_timezone()).isoformat(),
        'timezone': settings.LIBRARY_TIME_ZONE,
        'filters': params,
        'period': period,
        'academic_term': {'status': term_status, 'term': term_data(term)},
        'statistics': statistics,
        'total_checkouts': series,
        'top_borrowed': top,
        'peak_periods': peak_periods(loans, terms, term),
    }