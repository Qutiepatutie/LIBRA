from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField
from django.db.models.functions import TruncMonth
from datetime import timedelta
from django.utils import timezone

from .models import BorrowRecords, Books, StatusChoices

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