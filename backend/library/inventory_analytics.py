"""Read model for the admin Inventory tab. Contract: backend/ADMIN_INVENTORY_ANALYTICS.md"""
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone

from .models import BorrowRecords, Books, ConditionChoices
from .user_analytics import OPEN_STATUSES, library_timezone, library_today


def share(count, total):
    return round(count * 100 / total, 1) if total else None


def inventory_dashboard(now):
    today = library_today(now)
    # Copies out on an actual checkout; pending requests are still on the shelf.
    open_loans = BorrowRecords.objects.filter(status__in=OPEN_STATUSES, return_date__isnull=True,
                                              borrow_date__lte=now)
    copies = Books.objects.aggregate(
        total=Count('pk'),
        lost_damaged=Count('pk', filter=Q(condition__in=(ConditionChoices.LOST, ConditionChoices.DAMAGED))),
        borrowed=Count('pk', filter=Q(condition=ConditionChoices.GOOD, pk__in=open_loans.values('book_id'))),
    )
    total = copies['total']
    available = total - copies['borrowed'] - copies['lost_damaged']
    # Overdue loans need follow-up whatever the copy's condition, so they are not limited to "borrowed".
    overdue = (open_loans.filter(due_date__lt=today).select_related('book', 'user')
               .order_by('due_date', 'book__title', 'pk'))
    overdue_items = [{
        'loan_id': loan.pk,
        'borrower_id': loan.user.id_number,
        'borrower': f'{loan.user.first_name} {loan.user.last_name}'.strip(),
        'title': loan.book.title,
        'call_number': loan.book.call_number,
        'due_date': loan.due_date.isoformat(),
        'days_overdue': (today - loan.due_date).days,
    } for loan in overdue]
    card = lambda count: {'value': count, 'percentage': share(count, total)}
    return {
        'as_of': timezone.localtime(now, library_timezone()).isoformat(),
        'timezone': settings.LIBRARY_TIME_ZONE,
        'statistics': {
            'total_copies': total,
            'available': card(available),
            'borrowed': card(copies['borrowed']),
            'overdue': card(len(overdue_items)),
            'lost_damaged': card(copies['lost_damaged']),
        },
        'overdue_items': overdue_items,
    }
