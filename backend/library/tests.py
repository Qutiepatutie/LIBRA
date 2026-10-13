from datetime import date, datetime, timedelta, timezone as datetime_timezone
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import EducationLevel, UserLogin, UserProfile
from .models import AcademicTerm, Books, BorrowRecords, LoanFine, StatusChoices


MANILA = ZoneInfo('Asia/Manila')
NOW = datetime(2026, 10, 7, 12, tzinfo=MANILA)


@override_settings(LIBRARY_TIME_ZONE='Asia/Manila')
class DashboardTestCase(TestCase):
    def setUp(self):
        clock = patch('django.utils.timezone.now', return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)
        self.user = UserLogin.objects.create_user('reader@example.com', 'test-password')
        self.profile = UserProfile.objects.create(
            user=self.user, id_number='reader', education_level=EducationLevel.COLLEGE, year_level='1',
        )
        self.other_user = UserLogin.objects.create_user('other@example.com', 'test-password')
        self.other = UserProfile.objects.create(
            user=self.other_user, id_number='other', education_level=EducationLevel.SENIOR_HIGH, year_level='11',
        )
        self.book = self.make_book('600.T932 1991')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def make_book(self, call_number):
        return Books.objects.create(
            call_number=call_number, title=f'Book {call_number}', author='Author',
            publisher='Publisher', year_published='2026', pages='100',
        )

    def loan(self, **changes):
        values = dict(user=self.profile, book=self.book, borrow_date=NOW - timedelta(days=2),
                      due_date=date(2026, 10, 10), status=StatusChoices.ACTIVE)
        values.update(changes)
        return BorrowRecords.objects.create(**values)

    def term(self, **changes):
        values = dict(academic_year='2026-2027', semester='1', education_level=EducationLevel.COLLEGE,
                      start_date=date(2026, 9, 1), end_date=date(2027, 1, 31))
        values.update(changes)
        return AcademicTerm.objects.create(**values)

    def analytics(self):
        response = self.client.get(reverse('get_user_analytics'))
        self.assertEqual(response.status_code, 200, response.data)
        return response.data


class UserDashboardAPITests(DashboardTestCase):
    endpoints = ('get_user_analytics', 'get_user_current_loans', 'get_user_borrowing_history')

    def test_endpoints_require_authentication_and_only_allow_get(self):
        for endpoint in self.endpoints:
            with self.subTest(endpoint=endpoint):
                self.client.force_authenticate(None)
                self.assertEqual(self.client.get(reverse(endpoint)).status_code, 401)
                self.client.force_authenticate(self.user)
                self.assertEqual(self.client.post(reverse(endpoint), {}).status_code, 405)

    def test_real_jwt_authentication_scopes_results_to_token_owner(self):
        self.loan()
        self.loan(user=self.other)
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.user)}')
        self.assertEqual(self.analytics()['statistics']['currently_borrowed'], 1)

    def test_missing_profile_returns_404(self):
        self.profile.delete()
        self.user = UserLogin.objects.get(pk=self.user.pk)
        self.client.force_authenticate(self.user)
        for endpoint in self.endpoints:
            self.assertEqual(self.client.get(reverse(endpoint)).status_code, 404)

    def test_user_identifiers_cannot_select_another_borrower(self):
        own = self.loan()
        other = self.loan(user=self.other)
        LoanFine.objects.create(loan=other, amount_assessed='100.00')
        spoof = {'id': self.other.pk, 'user_id': self.other.pk, 'id_number': self.other.id_number}
        stats = self.client.get(reverse('get_user_analytics'), spoof).data
        self.assertEqual(stats['history_summary']['total_borrowed'], 1)
        self.assertEqual(stats['history_summary']['fine']['outstanding'], '0.00')
        self.assertEqual(stats['most_borrowed_subjects']['total_borrowed'], 1)
        self.assertEqual(sum(row['count'] for row in stats['borrowing_frequency']), 1)
        for endpoint in self.endpoints[1:]:
            response = self.client.get(reverse(endpoint), spoof)
            self.assertEqual([row['loan_id'] for row in response.data['results']], [own.pk])
            self.assertNotIn('email', response.data['results'][0])

    def test_empty_dashboard_has_zero_counts_and_six_empty_months(self):
        self.term()
        data = self.analytics()
        self.assertEqual(data['statistics'], {
            'currently_borrowed': 0, 'due_soon': 0, 'overdue': 0, 'books_this_semester': 0,
        })
        self.assertEqual(data['most_borrowed_subjects'], {'total_borrowed': 0, 'subjects': []})
        self.assertEqual([row['month'] for row in data['borrowing_frequency']],
                         ['2026-05', '2026-06', '2026-07', '2026-08', '2026-09', '2026-10'])
        self.assertTrue(all(row['count'] == 0 for row in data['borrowing_frequency']))
        self.assertEqual(data['history_summary']['fine']['outstanding'], '0.00')
        for endpoint in self.endpoints[1:]:
            response = self.client.get(reverse(endpoint))
            self.assertEqual(response.data['results'], [])
            self.assertEqual(response.data['count'], 0)

    def test_counts_use_checkouts_and_due_dates_not_stale_status(self):
        self.term()
        self.loan(due_date=date(2026, 10, 6))  # Stale Active, actually overdue.
        self.loan(due_date=date(2026, 10, 7), status=StatusChoices.OVERDUE)  # Due today.
        self.loan(due_date=date(2026, 10, 10))
        self.loan(due_date=date(2026, 10, 11), status=StatusChoices.DUE)
        self.loan(due_date=None)
        self.loan(status=StatusChoices.RETURNED, return_date=date(2026, 10, 6), due_date=date(2026, 10, 5))
        self.loan(status=StatusChoices.PENDING, borrow_date=None)
        self.loan(status=StatusChoices.CANCELLED, return_date=date(2026, 10, 6))
        self.loan(borrow_date=None)
        self.loan(borrow_date=NOW + timedelta(days=1))
        data = self.analytics()
        self.assertEqual(data['statistics'], {
            'currently_borrowed': 5, 'due_soon': 2, 'overdue': 1, 'books_this_semester': 6,
        })
        self.assertEqual(data['history_summary']['total_borrowed'], 6)
        self.assertEqual(data['history_summary']['late_returned'], 1)
        self.assertEqual(data['due_soon_window'], {'start_date': '2026-10-07', 'end_date': '2026-10-10'})

    def test_due_soon_rolls_over_on_sunday_in_manila(self):
        # Saturday UTC is already Sunday in the library.
        sunday = datetime(2026, 10, 10, 16, 0, tzinfo=datetime_timezone.utc)
        self.loan(due_date=date(2026, 10, 10))
        self.loan(due_date=date(2026, 10, 11))
        self.loan(due_date=date(2026, 10, 17))
        self.loan(due_date=date(2026, 10, 18))
        with patch('django.utils.timezone.now', return_value=sunday):
            data = self.analytics()
        self.assertEqual(data['statistics']['due_soon'], 2)
        self.assertEqual(data['statistics']['overdue'], 1)
        self.assertEqual(data['due_soon_window'], {'start_date': '2026-10-11', 'end_date': '2026-10-17'})

    def test_due_soon_on_saturday_is_today_only(self):
        self.loan(due_date=date(2026, 10, 10))
        self.loan(due_date=date(2026, 10, 11))
        with patch('django.utils.timezone.now', return_value=datetime(2026, 10, 10, 12, tzinfo=MANILA)):
            data = self.analytics()
        self.assertEqual(data['statistics']['due_soon'], 1)
        self.assertEqual(data['due_soon_window']['end_date'], '2026-10-10')

    def test_frequency_uses_local_month_boundaries_and_counts_repeat_checkouts(self):
        before_may = datetime(2026, 4, 30, 15, 59, tzinfo=datetime_timezone.utc)
        start_may = datetime(2026, 4, 30, 16, 0, tzinfo=datetime_timezone.utc)
        start_october = datetime(2026, 9, 30, 16, 0, tzinfo=datetime_timezone.utc)
        self.loan(borrow_date=before_may)
        self.loan(borrow_date=start_may, status=StatusChoices.RETURNED, return_date=date(2026, 5, 3))
        self.loan(borrow_date=start_october)
        self.loan(borrow_date=NOW)
        self.loan(borrow_date=NOW, status=StatusChoices.PENDING)
        self.loan(borrow_date=NOW, status=StatusChoices.CANCELLED)
        data = self.analytics()
        self.assertEqual([row['count'] for row in data['borrowing_frequency']], [1, 0, 0, 0, 0, 2])
        self.assertEqual(data['history_summary']['total_borrowed'], 4)

    def test_frequency_handles_year_transition(self):
        with patch('django.utils.timezone.now', return_value=datetime(2026, 1, 1, tzinfo=MANILA)):
            months = self.analytics()['borrowing_frequency']
        self.assertEqual([row['month'] for row in months],
                         ['2025-08', '2025-09', '2025-10', '2025-11', '2025-12', '2026-01'])

    def test_subjects_group_dewey_classes_and_keep_other_counts(self):
        for number in ('600.A', '600.B', '601.C', '100.A', '199.B', '300.A', '400.A', '500.A', '800.A', 'REF unknown'):
            self.loan(book=self.make_book(number))
        data = self.analytics()['most_borrowed_subjects']
        self.assertEqual(data['total_borrowed'], 10)
        self.assertEqual([row['code'] for row in data['subjects']], ['600', '100', '300', '400', '500', 'other'])
        self.assertEqual(data['subjects'][0]['count'], 3)
        self.assertEqual(data['subjects'][0]['percentage'], 30)
        self.assertEqual(data['subjects'][-1]['count'], 2)
        self.assertEqual(sum(row['count'] for row in data['subjects']), 10)

    def test_general_information_and_unclassified_subjects(self):
        for number in ('000.A', '001.A82 2023', '099.C', '1000.invalid', 'Fiction'):
            self.loan(book=self.make_book(number))
        rows = self.analytics()['most_borrowed_subjects']['subjects']
        self.assertEqual([(row['code'], row['count']) for row in rows], [('001', 3), ('unclassified', 2)])

    def test_current_table_has_pending_and_derived_statuses_with_stable_ids(self):
        pending = self.loan(status=StatusChoices.PENDING, borrow_date=None, due_date=None)
        overdue = self.loan(due_date=date(2026, 10, 6))
        due = self.loan(due_date=date(2026, 10, 7))
        active = self.loan(status=StatusChoices.OVERDUE)
        self.loan(status=StatusChoices.RETURNED, return_date=date(2026, 10, 6))
        self.loan(status=StatusChoices.CANCELLED)
        response = self.client.get(reverse('get_user_current_loans'))
        rows = {row['loan_id']: row for row in response.data['results']}
        self.assertEqual(set(rows), {pending.pk, overdue.pk, due.pk, active.pk})
        self.assertIsNone(rows[pending.pk]['borrow_date'])
        self.assertIsNone(rows[pending.pk]['due_date'])
        self.assertEqual(rows[pending.pk]['status'], 'Pending')
        self.assertEqual(rows[overdue.pk]['status'], 'Overdue')
        self.assertEqual(rows[due.pk]['status'], 'Due')
        self.assertEqual(rows[active.pk]['status'], 'Active')
        self.assertEqual(rows[active.pk]['title'], self.book.title)
        self.assertEqual(rows[active.pk]['book_id'], self.book.pk)

    def test_history_includes_actual_loans_and_paid_amount_not_pending_or_cancelled(self):
        active = self.loan()
        returned = self.loan(status=StatusChoices.RETURNED, return_date=date(2026, 10, 6))
        LoanFine.objects.create(loan=returned, amount_assessed='25.50', amount_paid='10.25')
        self.loan(status=StatusChoices.PENDING, borrow_date=None)
        self.loan(status=StatusChoices.CANCELLED, return_date=date(2026, 10, 6))
        response = self.client.get(reverse('get_user_borrowing_history'))
        rows = {row['loan_id']: row for row in response.data['results']}
        self.assertEqual(set(rows), {active.pk, returned.pk})
        self.assertIsNone(rows[active.pk]['return_date'])
        self.assertEqual(rows[returned.pk]['return_date'], '2026-10-06')
        self.assertEqual(rows[returned.pk]['fine']['amount_paid'], '10.25')
        self.assertEqual(response.data['summary']['fine']['outstanding'], '15.25')

    def test_pagination_has_no_duplicates_and_summary_is_not_page_limited(self):
        expected = [self.loan().pk for _ in range(5)][::-1]
        for endpoint in self.endpoints[1:]:
            seen = []
            for page in (1, 2, 3):
                response = self.client.get(reverse(endpoint), {'page': page, 'page_size': 2})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data['count'], 5)
                seen.extend(row['loan_id'] for row in response.data['results'])
                if endpoint == 'get_user_borrowing_history':
                    self.assertEqual(response.data['summary']['total_borrowed'], 5)
            self.assertEqual(seen, expected)
            self.assertIsNone(response.data['next'])
            self.assertIsNotNone(response.data['previous'])

    def test_invalid_pagination_returns_client_errors(self):
        for endpoint in self.endpoints[1:]:
            for params in ({'page': 0}, {'page': 'bad'}, {'page_size': 0}, {'page_size': 101}, {'page_size': 'bad'}):
                with self.subTest(endpoint=endpoint, params=params):
                    self.assertEqual(self.client.get(reverse(endpoint), params).status_code, 400)
            self.assertEqual(self.client.get(reverse(endpoint), {'page': 99}).status_code, 404)

    def test_table_query_count_does_not_grow_per_loan(self):
        for _ in range(10):
            LoanFine.objects.create(loan=self.loan(), amount_assessed='10.00')
        # The already-cached profile needs no query: COUNT plus one joined page query.
        with self.assertNumQueries(2):
            response = self.client.get(reverse('get_user_current_loans'))
            self.assertEqual(len(response.data['results']), 10)

    def test_checkout_and_return_store_library_local_dates(self):
        loan = self.loan(status=StatusChoices.PENDING, borrow_date=None, due_date=None)
        payload = {'isbn': self.book.isbn, 'call_num': self.book.call_number}
        # UTC Oct 6, but the library has already reached Oct 7.
        checkout = datetime(2026, 10, 6, 16, 30, tzinfo=datetime_timezone.utc)
        with patch('django.utils.timezone.now', return_value=checkout):
            response = self.client.put(reverse('accept_borrowed_book'), payload)
        self.assertEqual(response.status_code, 200)
        loan.refresh_from_db()
        self.assertEqual(loan.due_date, date(2026, 10, 14))
        self.assertEqual(loan.borrow_date, checkout)
        LoanFine.objects.create(loan=loan, amount_assessed='25.00')
        returned = datetime(2026, 10, 14, 16, 30, tzinfo=datetime_timezone.utc)
        with patch('django.utils.timezone.now', return_value=returned):
            response = self.client.put(reverse('return_book'), {**payload, 'action': 'return'})
            data = self.analytics()
        self.assertEqual(response.status_code, 200)
        loan.refresh_from_db()
        self.assertEqual(loan.return_date, date(2026, 10, 15))
        self.assertEqual(data['history_summary']['late_returned'], 1)
        self.assertEqual(data['history_summary']['fine']['outstanding'], '25.00')


class AcademicTermTests(DashboardTestCase):
    def test_unknown_profile_and_unconfigured_or_inactive_terms_do_not_fake_zero(self):
        self.assertEqual(self.analytics()['academic_term']['status'], 'not_configured')
        self.assertIsNone(self.analytics()['statistics']['books_this_semester'])
        self.term(start_date=date(2026, 11, 1))
        self.assertEqual(self.analytics()['academic_term']['status'], 'no_active_term')
        self.profile.education_level = ''
        self.profile.save()
        self.assertEqual(self.analytics()['academic_term']['status'], 'profile_incomplete')

    def test_blank_year_level_follows_default_term_not_overrides(self):
        default = self.term()
        self.term(year_level='1', start_date=date(2026, 10, 1))
        self.profile.year_level = ''
        self.profile.save()
        self.assertEqual(self.analytics()['academic_term']['term']['id'], default.pk)

    def test_year_override_takes_precedence_before_date_filtering(self):
        self.term()
        override = self.term(year_level='1', start_date=date(2026, 10, 15))
        self.assertEqual(self.analytics()['academic_term']['status'], 'no_active_term')
        override.start_date = date(2026, 10, 1)
        override.save()
        self.loan(borrow_date=datetime(2026, 9, 15, tzinfo=MANILA))
        self.loan()
        data = self.analytics()
        self.assertEqual(data['academic_term']['term']['id'], override.pk)
        self.assertEqual(data['statistics']['books_this_semester'], 1)

    def test_default_applies_to_other_years_and_different_education_has_own_term(self):
        default = self.term(year_level='')
        self.term(year_level='2', start_date=date(2026, 10, 15))
        high_school = self.term(education_level=EducationLevel.SENIOR_HIGH, start_date=date(2026, 8, 1))
        self.assertEqual(self.analytics()['academic_term']['term']['id'], default.pk)
        self.client.force_authenticate(self.other_user)
        self.assertEqual(self.analytics()['academic_term']['term']['id'], high_school.pk)

    def test_old_academic_year_override_does_not_affect_new_year(self):
        self.term(academic_year='2025-2026', year_level='1',
                  start_date=date(2025, 10, 1), end_date=date(2026, 2, 1))
        current = self.term()
        self.assertEqual(self.analytics()['academic_term']['term']['id'], current.pk)

    def test_semester_boundaries_are_inclusive_in_manila(self):
        self.term(start_date=date(2026, 10, 1), end_date=date(2026, 10, 7))
        self.loan(borrow_date=datetime(2026, 9, 30, 15, 59, tzinfo=datetime_timezone.utc))
        self.loan(borrow_date=datetime(2026, 9, 30, 16, 0, tzinfo=datetime_timezone.utc))
        self.loan(borrow_date=datetime(2026, 10, 7, 15, 59, tzinfo=datetime_timezone.utc))
        self.loan(borrow_date=datetime(2026, 10, 7, 16, 0, tzinfo=datetime_timezone.utc))
        with patch('django.utils.timezone.now', return_value=datetime(2026, 10, 7, 23, 59, 59, tzinfo=MANILA)):
            self.assertEqual(self.analytics()['statistics']['books_this_semester'], 2)
        with patch('django.utils.timezone.now', return_value=datetime(2026, 10, 8, tzinfo=MANILA)):
            self.assertEqual(self.analytics()['academic_term']['status'], 'no_active_term')

    def test_overlapping_effective_terms_validate_and_runtime_reports_conflict(self):
        self.term()
        overlap = AcademicTerm(academic_year='2026-2027', semester='2', education_level='college',
                               start_date=date(2026, 10, 1), end_date=date(2027, 2, 1))
        with self.assertRaises(ValidationError):
            overlap.full_clean()
        # Imported legacy data can bypass model validation; never silently pick one.
        overlap.save()
        data = self.analytics()
        self.assertEqual(data['academic_term']['status'], 'conflict')
        self.assertIsNone(data['statistics']['books_this_semester'])

    def test_default_and_override_can_overlap_intentionally(self):
        self.term()
        override = AcademicTerm(academic_year='2026-2027', semester='1', education_level='college', year_level='1',
                                start_date=date(2026, 10, 1), end_date=date(2027, 2, 1))
        override.full_clean()
        override.save()
        self.assertEqual(self.analytics()['academic_term']['term']['id'], override.pk)

    def test_database_rejects_duplicate_null_empty_and_exact_scopes(self):
        self.term()
        for year in (None, ''):
            with self.subTest(year=year), self.assertRaises(IntegrityError), transaction.atomic():
                self.term(year_level=year)
        self.term(year_level='1')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.term(year_level='1')
        self.term(semester='2', year_level='')
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.term(semester='2', year_level=None)

    def test_invalid_date_order_is_rejected_but_single_day_term_is_valid(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.term(start_date=date(2026, 10, 8), end_date=date(2026, 10, 7))
        self.term(start_date=date(2026, 10, 7), end_date=date(2026, 10, 7))
        self.assertEqual(self.analytics()['academic_term']['status'], 'active')

    def test_profile_and_term_year_levels_use_numeric_values(self):
        self.profile.year_level = 'Freshman'
        with self.assertRaises(ValidationError):
            self.profile.full_clean()
        invalid = AcademicTerm(academic_year='2026-2027', semester='1', education_level='college', year_level='01',
                               start_date=date(2026, 9, 1), end_date=date(2027, 1, 1))
        with self.assertRaises(ValidationError):
            invalid.full_clean()


class LoanFineTests(DashboardTestCase):
    def test_partial_and_full_payments_and_returned_unpaid_fines(self):
        returned = self.loan(status=StatusChoices.RETURNED, return_date=date(2026, 10, 6))
        first = LoanFine.objects.create(loan=returned, amount_assessed='50.50', amount_paid='10.25')
        LoanFine.objects.create(loan=self.loan(), amount_assessed='25.00', amount_paid='25.00')
        LoanFine.objects.create(loan=self.loan(user=self.other), amount_assessed='999.00')
        fine = self.analytics()['history_summary']['fine']
        self.assertEqual(fine, {'currency': 'PHP', 'amount_assessed': '75.50', 'amount_paid': '35.25', 'outstanding': '40.25'})
        first.amount_paid = Decimal('50.50')
        first.save()
        self.assertEqual(self.analytics()['history_summary']['fine']['outstanding'], '0.00')

    def test_no_automatic_charge_for_overdue_loan(self):
        self.loan(due_date=date(2026, 1, 1))
        self.assertEqual(self.analytics()['history_summary']['fine']['outstanding'], '0.00')

    def test_invalid_amounts_rejected_by_model_and_database(self):
        loan = self.loan()
        for assessed, paid in (('-1.00', '0.00'), ('10.00', '-1.00'), ('10.00', '10.01')):
            with self.subTest(assessed=assessed, paid=paid):
                with self.assertRaises(ValidationError):
                    LoanFine.objects.create(loan=loan, amount_assessed=assessed, amount_paid=paid)
                with self.assertRaises(IntegrityError), transaction.atomic():
                    LoanFine.objects.bulk_create([LoanFine(loan=loan, amount_assessed=assessed, amount_paid=paid)])

    def test_pending_and_cancelled_requests_cannot_receive_fines(self):
        for status in (StatusChoices.PENDING, StatusChoices.CANCELLED):
            with self.subTest(status=status), self.assertRaises(ValidationError):
                LoanFine.objects.create(loan=self.loan(status=status), amount_assessed='25.00')
        with self.assertRaises(ValidationError):
            LoanFine.objects.create(loan=self.loan(borrow_date=None), amount_assessed='25.00')

    def test_one_fine_per_loan_and_loan_is_protected_from_deletion(self):
        loan = self.loan()
        LoanFine.objects.create(loan=loan, amount_assessed='25.00')
        with self.assertRaises(ValidationError):
            LoanFine.objects.create(loan=loan, amount_assessed='10.00')
        with self.assertRaises(ProtectedError):
            loan.delete()
