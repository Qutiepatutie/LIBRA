from datetime import date, datetime, timedelta

from django.urls import reverse
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import EducationLevel, RoleChoices, UserLogin, UserProfile
from .models import AcademicTerm, AcademicYear, Books, ItemType, StatusChoices
from .tests import MANILA, NOW, DashboardTestCase


def at(day, hour=10):
    return datetime(day.year, day.month, day.day, hour, tzinfo=MANILA)


class CirculationDashboardTests(DashboardTestCase):
    # NOW is Wednesday 2026-10-07 12:00 in Manila; this week runs Mon 10-05 to Sun 10-11.

    def setUp(self):
        super().setUp()
        self.profile.program = 'BS Computer Science'
        self.profile.save()
        self.admin = UserLogin.objects.create_user('admin@example.com', 'test-password', role=RoleChoices.ADMIN)
        UserProfile.objects.create(user=self.admin, id_number='admin')
        self.client.force_authenticate(self.admin)

    def dashboard(self, **params):
        response = self.client.get(reverse('get_circulation_dashboard'), params)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def make_book(self, call_number, **changes):
        book = super().make_book(call_number)
        for field, value in changes.items():
            setattr(book, field, value)
        book.save()
        return book

    def test_requires_jwt_admin_role(self):
        self.client.force_authenticate(None)
        url = reverse('get_circulation_dashboard')
        self.assertEqual(self.client.get(url).status_code, 401)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(url).status_code, 403)
        # The legacy id_number query value cannot promote a student.
        self.assertEqual(self.client.get(url, {'id_number': 'admin'}).status_code, 403)
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {}).status_code, 405)

    def test_rejects_unknown_range_and_item_type(self):
        url = reverse('get_circulation_dashboard')
        self.assertEqual(self.client.get(url, {'range': 'month'}).status_code, 400)
        self.assertEqual(self.client.get(url, {'item_type': 'magazine'}).status_code, 400)

    def test_week_counts_checkouts_against_same_elapsed_span_last_week(self):
        self.loan(borrow_date=at(date(2026, 10, 5)))
        self.loan(borrow_date=at(date(2026, 10, 7), 9), user=self.other)
        self.loan(borrow_date=at(date(2026, 9, 28)))
        self.loan(borrow_date=at(date(2026, 10, 1)))  # last Thursday: after the elapsed span
        self.loan(borrow_date=at(date(2026, 10, 6)), status=StatusChoices.PENDING)
        self.loan(borrow_date=at(date(2026, 10, 6)), status=StatusChoices.CANCELLED)
        data = self.dashboard()
        self.assertEqual(data['period'], {'start_date': '2026-10-05', 'end_date': '2026-10-11',
                                          'previous_start_date': '2026-09-28'})
        self.assertEqual(data['statistics']['borrows'], {'value': 2, 'previous': 1, 'change_pct': 100.0})
        self.assertEqual(data['statistics']['active_borrowers'], {'value': 2, 'previous': 1, 'change_pct': 100.0})
        self.assertEqual([row['label'] for row in data['total_checkouts']], ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'])
        self.assertEqual([row['count'] for row in data['total_checkouts']], [1, 0, 1, 0, 0, 0])

    def test_change_is_null_without_previous_checkouts(self):
        self.loan(borrow_date=at(date(2026, 10, 6)))
        self.assertEqual(self.dashboard()['statistics']['borrows'], {'value': 1, 'previous': 0, 'change_pct': None})

    def test_day_buckets_cover_library_hours(self):
        self.loan(borrow_date=at(date(2026, 10, 7), 9).replace(minute=30))
        self.loan(borrow_date=at(date(2026, 10, 7), 11))
        self.loan(borrow_date=at(date(2026, 10, 6), 9))
        data = self.dashboard(range='day')
        series = data['total_checkouts']
        self.assertEqual(len(series), 13)
        self.assertEqual((series[0]['label'], series[-1]['label']), ('07:00', '19:00'))
        self.assertEqual(series[0]['start'], '2026-10-07T07:00:00+08:00')
        self.assertEqual({row['label']: row['count'] for row in series if row['count']}, {'09:00': 1, '11:00': 1})
        # Yesterday up to the same time of day had one checkout.
        self.assertEqual(data['statistics']['borrows']['previous'], 1)

    def test_item_type_and_program_filters(self):
        thesis = self.make_book('T-001', item_type=ItemType.THESIS, title='Capstone')
        self.other.program = 'BS Nursing'
        self.other.save()
        self.loan(borrow_date=at(date(2026, 10, 6)))
        self.loan(borrow_date=at(date(2026, 10, 6)), book=thesis)
        self.loan(borrow_date=at(date(2026, 10, 6)), user=self.other)
        self.assertEqual(self.dashboard(item_type='thesis')['statistics']['borrows']['value'], 1)
        self.assertEqual(self.dashboard(program='BS Nursing')['statistics']['borrows']['value'], 1)
        response = self.client.get(reverse('get_circulation_dashboard'),
                                   {'program': ['BS Nursing', 'BS Computer Science']})
        self.assertEqual(response.data['statistics']['borrows']['value'], 3)
        self.assertEqual(self.dashboard(program='All', item_type='all')['statistics']['borrows']['value'], 3)

    def test_currently_overdue_uses_due_dates_and_compares_with_a_week_ago(self):
        self.loan(borrow_date=at(date(2026, 9, 1)), due_date=date(2026, 9, 8))  # overdue both days
        self.loan(borrow_date=at(date(2026, 9, 25)), due_date=date(2026, 10, 2))  # overdue only now
        self.loan(borrow_date=at(date(2026, 9, 1)), due_date=date(2026, 9, 8),
                  status=StatusChoices.RETURNED, return_date=date(2026, 10, 3))  # overdue a week ago
        self.loan(due_date=date(2026, 10, 10))
        self.assertEqual(self.dashboard()['statistics']['currently_overdue'],
                         {'value': 2, 'week_ago': 2, 'change': 0})

    def test_top_borrowed_groups_copies_and_splits_item_types(self):
        copy = self.make_book('600.T932 1991 c.2', title=self.book.title)
        thesis = self.make_book('T-001', item_type=ItemType.THESIS, title='Capstone')
        for book in (self.book, copy, thesis):
            self.loan(borrow_date=at(date(2026, 10, 6)), book=book)
        for index in range(11):
            self.loan(borrow_date=at(date(2026, 10, 5)), book=self.make_book(f'900.{index:02d}'))
        top = self.dashboard()['top_borrowed']
        self.assertEqual(len(top['book']), 10)
        self.assertEqual(top['book'][0], {'title': self.book.title, 'author': 'Author', 'count': 2})
        self.assertEqual(top['thesis'], [{'title': 'Capstone', 'author': 'Author', 'count': 1}])

    def test_semester_without_calendar_has_no_period(self):
        self.loan()
        data = self.dashboard(range='semester')
        self.assertEqual(data['academic_term'], {'status': 'not_configured', 'term': None})
        self.assertIsNone(data['period'])
        self.assertIsNone(data['statistics']['borrows'])
        self.assertEqual(data['total_checkouts'], [])
        self.assertEqual(data['peak_periods'], {'academic_year': None, 'terms': []})
        self.assertEqual(data['statistics']['currently_overdue']['value'], 0)

    def test_semester_range_buckets_term_weeks_and_compares_previous_term(self):
        self.term(academic_year='2025-2026', semester='2', start_date=date(2026, 2, 2), end_date=date(2026, 6, 30))
        first = self.term()  # Tue 2026-09-01 to Sun 2027-01-31
        self.loan(borrow_date=at(date(2026, 9, 1)))
        self.loan(borrow_date=at(date(2026, 10, 7), 9))
        self.loan(borrow_date=at(date(2026, 2, 3)))
        data = self.dashboard(range='semester')
        self.assertEqual(data['academic_term']['status'], 'active')
        self.assertEqual(data['academic_term']['term']['id'], first.pk)
        self.assertEqual(data['period']['previous_start_date'], '2026-02-02')
        series = data['total_checkouts']
        self.assertEqual(len(series), 22)
        self.assertEqual(series[0], {'label': 'W1', 'start': '2026-09-01', 'count': 1})
        self.assertEqual(series[5]['count'], 1)
        self.assertEqual(data['statistics']['borrows'], {'value': 2, 'previous': 1, 'change_pct': 100.0})

    def test_peak_periods_grid_is_monday_to_saturday_per_term(self):
        first = self.term()
        self.term(semester='2', start_date=date(2027, 2, 1), end_date=date(2027, 6, 30))
        self.term(academic_year='2025-2026', semester='2', start_date=date(2026, 2, 2), end_date=date(2026, 6, 30))
        self.loan(borrow_date=at(date(2026, 9, 5)))  # Saturday of W1
        self.loan(borrow_date=at(date(2026, 10, 5)))  # Monday of W6
        self.loan(borrow_date=at(date(2026, 10, 4)))  # Sunday: closed, left off the grid
        self.loan(user=self.other, borrow_date=at(date(2026, 10, 5)))
        peak = self.dashboard()['peak_periods']
        self.assertEqual(peak['academic_year'], '2026-2027')
        self.assertEqual([term['semester'] for term in peak['terms']], ['1', '2'])
        grid = peak['terms'][0]
        self.assertEqual(grid['id'], first.pk)
        self.assertEqual(len(grid['cells']), 6)
        self.assertTrue(all(len(row) == grid['weeks'] == 22 for row in grid['cells']))
        self.assertEqual(grid['cells'][5][0], 1)
        self.assertEqual(grid['cells'][0][5], 2)
        self.assertEqual(grid['scale'], {'max': 2, 'total': 3})
        self.assertEqual(peak['terms'][1]['scale'], {'max': 0, 'total': 0})

    def test_selecting_a_past_term_reports_its_full_span(self):
        past = self.term(academic_year='2025-2026', semester='2', start_date=date(2026, 2, 2), end_date=date(2026, 6, 30))
        self.term()
        self.loan(borrow_date=at(date(2026, 3, 2)))
        data = self.dashboard(range='semester', academic_year='2025-2026', semester='2')
        self.assertEqual(data['academic_term']['status'], 'selected')
        self.assertEqual(data['academic_term']['term']['id'], past.pk)
        self.assertEqual(data['period']['end_date'], '2026-06-30')
        self.assertEqual(data['statistics']['borrows']['value'], 1)
        self.assertEqual(data['peak_periods']['academic_year'], '2025-2026')
        self.assertEqual(self.dashboard(academic_year='1999-2000')['academic_term'], {'status': 'not_found', 'term': None})

    def test_year_range_uses_academic_year_timeline(self):
        timeline = AcademicYear.objects.create(academic_year='2026-2027', education_level=EducationLevel.COLLEGE,
                                               start_date=date(2026, 8, 15), end_date=date(2027, 7, 31))
        self.term(academic_year_timeline=timeline)
        self.loan(borrow_date=at(date(2026, 8, 20)))
        self.loan(borrow_date=at(date(2026, 10, 6)))
        data = self.dashboard(range='year')
        self.assertEqual((data['period']['start_date'], data['period']['end_date']), ('2026-08-15', '2027-07-31'))
        self.assertEqual(len(data['total_checkouts']), 12)
        self.assertEqual(data['total_checkouts'][0], {'label': '2026-08', 'start': '2026-08-01', 'count': 1})
        self.assertEqual(data['total_checkouts'][2]['count'], 1)

    def test_year_range_falls_back_to_twelve_calendar_months(self):
        self.loan(borrow_date=at(date(2025, 11, 3)))
        self.loan(borrow_date=at(date(2025, 10, 31)))  # before the window
        data = self.dashboard(range='year')
        labels = [row['label'] for row in data['total_checkouts']]
        self.assertEqual((labels[0], labels[-1], len(labels)), ('2025-11', '2026-10', 12))
        self.assertEqual(data['statistics']['borrows']['value'], 1)

    def test_senior_high_calendar_is_selectable(self):
        shs = self.term(education_level=EducationLevel.SENIOR_HIGH, start_date=date(2026, 8, 3), end_date=date(2026, 12, 18))
        self.term()
        data = self.dashboard(education_level='senior_high')
        self.assertEqual(data['academic_term']['term']['id'], shs.pk)
