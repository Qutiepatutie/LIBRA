from datetime import date

from django.urls import reverse

from accounts.models import RoleChoices, UserLogin, UserProfile
from .models import Books, ConditionChoices, StatusChoices
from .tests import DashboardTestCase


class InventoryDashboardTests(DashboardTestCase):
    def setUp(self):
        super().setUp()
        self.admin = UserLogin.objects.create_user('admin@example.com', 'test-password', role=RoleChoices.ADMIN)
        UserProfile.objects.create(user=self.admin, id_number='admin')
        self.client.force_authenticate(self.admin)

    def dashboard(self):
        response = self.client.get(reverse('get_inventory_dashboard'))
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_requires_jwt_admin_role(self):
        url = reverse('get_inventory_dashboard')
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(url, {'id_number': 'admin'}).status_code, 403)

    def test_legacy_spoofable_endpoint_is_gone(self):
        self.assertEqual(self.client.get('/adminAnalyticsDashboard/', {'id_number': 'admin'}).status_code, 404)

    def test_empty_collection_has_null_shares(self):
        Books.objects.all().delete()
        data = self.dashboard()
        self.assertEqual(data['statistics']['total_copies'], 0)
        self.assertEqual(data['statistics']['available'], {'value': 0, 'percentage': None})
        self.assertEqual(data['overdue_items'], [])

    def test_cards_partition_the_collection(self):
        out = self.make_book('100.A')
        late = self.make_book('100.B')
        self.make_book('100.C')
        lost_on_loan = self.make_book('100.D')
        damaged = self.make_book('100.E')
        Books.objects.filter(pk=damaged.pk).update(condition=ConditionChoices.DAMAGED)
        Books.objects.filter(pk=lost_on_loan.pk).update(condition=ConditionChoices.LOST)
        self.loan(book=out)
        self.loan(book=late, due_date=date(2026, 10, 1))
        self.loan(book=lost_on_loan, due_date=date(2026, 9, 20))
        self.loan(book=self.book, status=StatusChoices.PENDING, borrow_date=None)  # still on the shelf
        self.loan(book=self.book, status=StatusChoices.RETURNED, return_date=date(2026, 10, 6))
        stats = self.dashboard()['statistics']
        self.assertEqual(stats['total_copies'], 6)
        self.assertEqual(stats['borrowed'], {'value': 2, 'percentage': 33.3})
        self.assertEqual(stats['lost_damaged'], {'value': 2, 'percentage': 33.3})
        self.assertEqual(stats['available'], {'value': 2, 'percentage': 33.3})
        self.assertEqual(stats['overdue']['value'], 2)

    def test_overdue_list_uses_due_dates_and_sorts_most_overdue_first(self):
        self.profile.first_name, self.profile.last_name = 'Ana', 'Cruz'
        self.profile.save()
        newer = self.loan(due_date=date(2026, 10, 5))
        older = self.loan(book=self.make_book('200.A'), due_date=date(2026, 9, 28), status=StatusChoices.ACTIVE)
        self.loan(book=self.make_book('200.B'), due_date=date(2026, 10, 7))  # due today: not overdue
        self.loan(book=self.make_book('200.C'), due_date=date(2026, 9, 1),
                  status=StatusChoices.RETURNED, return_date=date(2026, 9, 3))
        items = self.dashboard()['overdue_items']
        self.assertEqual([item['loan_id'] for item in items], [older.pk, newer.pk])
        self.assertEqual(items[0], {
            'loan_id': older.pk, 'borrower_id': 'reader', 'borrower': 'Ana Cruz', 'title': 'Book 200.A',
            'call_number': '200.A', 'due_date': '2026-09-28', 'days_overdue': 9,
        })


class EditBookClassificationTests(DashboardTestCase):
    def test_edit_book_sets_and_validates_item_type_and_condition(self):
        url = reverse('edit_book')
        response = self.client.put(url, {'book_id': self.book.pk, 'itemType': 'thesis', 'condition': 'lost'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.book.refresh_from_db()
        self.assertEqual((self.book.item_type, self.book.condition), ('thesis', 'lost'))
        for field in ('itemType', 'condition'):
            response = self.client.put(url, {'book_id': self.book.pk, field: 'bogus'}, format='json')
            self.assertEqual(response.status_code, 400)
