from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from accounts.models import EducationLevel, RoleChoices, UserLogin, UserProfile
from .models import AcademicTerm, AcademicYear, Books, BorrowRecords, ItemType, StatusChoices
from .tests import MANILA, NOW


URL = reverse('get_borrowers_dashboard')
DEFAULT_FILTERS = {'range': 'week', 'item_type': 'all', 'program': [], 'academic_year': '', 'semester': '',
                   'education_level': 'college'}


def at(year, month, day, hour=10, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=MANILA)


def weekdays(*counts):
    return [{'day': day, 'count': count} for day, count in zip(('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'), counts)]


@override_settings(LIBRARY_TIME_ZONE='Asia/Manila')
class BorrowersDashboardTests(TestCase):
    # NOW is Wednesday 2026-10-07 12:00 in Manila; this week runs Mon 10-05 to Sun 10-11,
    # and the same elapsed span of last week is [Mon 09-28 00:00, Wed 09-30 12:00).

    def setUp(self):
        clock = patch('django.utils.timezone.now', return_value=NOW)
        clock.start()
        self.addCleanup(clock.stop)
        self.admin = UserLogin.objects.create_user('admin@example.com', 'test-password', role=RoleChoices.ADMIN)
        UserProfile.objects.create(user=self.admin, id_number='admin')
        # Six registered students: four college (one with a blank level), one SHS, one without a program.
        self.cs = self.profile('cs', 'BS in Computer Science', EducationLevel.COLLEGE)
        self.nursing = self.profile('nursing', 'BS in Nursing', EducationLevel.COLLEGE)
        self.accountancy = self.profile('acct', 'BS in Accountancy', EducationLevel.COLLEGE)
        self.legacy = self.profile('legacy', 'BS in Information Technology', '')  # level inferred: college
        self.stem = self.profile('stem', 'STEM', EducationLevel.SENIOR_HIGH)
        self.blank = self.profile('blank', '', '')
        # Not part of the population, so their programs never show up either.
        self.faculty = self.profile('faculty', 'BS in Psychology', EducationLevel.COLLEGE, RoleChoices.FACULTY)
        self.disabled = self.profile('disabled', 'BS in Pharmacy', EducationLevel.COLLEGE)
        self.disabled.user.is_active = False
        self.disabled.user.save()
        self.book = self.make_book('600.T932')
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    def profile(self, id_number, program, education_level, role=RoleChoices.STUDENT):
        user = UserLogin.objects.create_user(f'{id_number}@example.com', 'test-password', role=role)
        return UserProfile.objects.create(user=user, id_number=id_number, program=program,
                                          education_level=education_level, year_level='1')

    def make_book(self, call_number, item_type=ItemType.BOOK):
        return Books.objects.create(call_number=call_number, title=f'Book {call_number}', author='Author',
                                    publisher='Publisher', year_published='2026', pages='100', item_type=item_type)

    def loan(self, profile, borrowed, returned=None, status=StatusChoices.ACTIVE, book=None):
        return BorrowRecords.objects.create(
            user=profile, book=book or self.book, borrow_date=borrowed, due_date=borrowed.date() + timedelta(days=7),
            return_date=returned, status=StatusChoices.RETURNED if returned else status,
        )

    def term(self, **changes):
        values = dict(academic_year='2026-2027', semester='1', education_level=EducationLevel.COLLEGE,
                      start_date=date(2026, 9, 1), end_date=date(2027, 1, 31))
        values.update(changes)
        return AcademicTerm.objects.create(**values)

    def get(self, expected=200, **params):
        response = self.client.get(URL, params)
        self.assertEqual(response.status_code, expected, getattr(response, 'data', None))
        return response.data

    def seed_week(self):
        # Current week, up to now.
        self.loan(self.cs, at(2026, 10, 5, 9), returned=date(2026, 10, 7))      # Mon; 2-day loan
        self.loan(self.cs, at(2026, 10, 6, 9))                                  # Tue
        self.loan(self.stem, at(2026, 10, 7, 8))                                # Wed (today)
        # Mon 00:30 Manila is Sun 16:30 UTC: still Monday, and a 1-day loan (not 2) when returned Tue.
        self.loan(self.legacy, at(2026, 10, 5, 0, 30), returned=date(2026, 10, 6))
        # Last week: inside the elapsed span ...
        self.loan(self.nursing, at(2026, 9, 29, 10))
        self.loan(self.cs, at(2026, 9, 30, 11))
        # ... and after it (Wed past 12:00, Fri), so not compared.
        self.loan(self.stem, at(2026, 9, 30, 13))
        self.loan(self.nursing, at(2026, 10, 2, 10))
        # Returns: this week's span is 10-05..10-07 (n = 3 days), so last week's is 09-28..09-30.
        self.loan(self.cs, at(2026, 9, 21), returned=date(2026, 10, 5))         # 14 days, current
        self.loan(self.stem, at(2026, 9, 20), returned=date(2026, 9, 30))       # 10 days, previous
        self.loan(self.nursing, at(2026, 9, 24), returned=date(2026, 10, 2))    # past the previous span
        # Never counted.
        self.loan(self.faculty, at(2026, 10, 5))
        self.loan(self.faculty, at(2026, 9, 25), returned=date(2026, 10, 6))
        self.loan(self.disabled, at(2026, 10, 5))
        self.loan(self.disabled, at(2026, 9, 25), returned=date(2026, 10, 6))
        self.loan(self.nursing, at(2026, 10, 7, 13))                            # after now
        self.loan(self.nursing, at(2026, 10, 5), status=StatusChoices.PENDING)
        self.loan(self.nursing, at(2026, 10, 5), status=StatusChoices.CANCELLED)

    def test_requires_an_authenticated_admin_and_only_allows_get(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(URL).status_code, 401)
        self.client.force_authenticate(self.cs.user)
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertEqual(self.client.get(URL, {'id_number': 'admin'}).status_code, 403)
        self.client.force_authenticate(None)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {AccessToken.for_user(self.admin)}')
        self.assertEqual(self.client.get(URL).status_code, 200)
        self.assertEqual(self.client.post(URL, {}).status_code, 405)

    def test_old_route_is_gone(self):
        with self.assertRaises(NoReverseMatch):
            reverse('get_admin_borrower_analytics')
        self.assertEqual(self.client.get('/getAdminBorrowerAnalytics/').status_code, 404)

    def test_week_envelope_and_statistics(self):
        self.seed_week()
        data = self.get()
        self.assertEqual(data['as_of'], '2026-10-07T12:00:00+08:00')
        self.assertEqual(data['timezone'], 'Asia/Manila')
        self.assertEqual(data['filters'], DEFAULT_FILTERS)
        self.assertEqual(data['period'], {'start_date': '2026-10-05', 'end_date': '2026-10-11',
                                          'previous_start_date': '2026-09-28'})
        self.assertEqual(data['academic_term'], {'status': 'not_configured', 'term': None})
        self.assertEqual(data['statistics'], {
            'registered_students': 6,
            # cs, legacy, stem borrowed this week: 3*100/6 = 50.0; inactive 6 - 3 = 3.
            'active_borrowers': {'value': 3, 'percentage': 50.0},
            'inactive_borrowers': {'value': 3, 'percentage': 50.0},
            # 4 this week vs nursing 09-29 + cs 09-30 11:00 = 2; (4 - 2)*100/2 = 100.0.
            'total_checkouts': {'value': 4, 'previous': 2, 'change_pct': 100.0},
            # (2 + 1 + 14)/3 = 5.67 vs 10/1 = 10.0; 5.67 - 10.0 = -4.33.
            'avg_loan_duration_days': {'value': 5.67, 'previous': 10.0, 'change': -4.33},
            # 4/3 = 1.33 vs 2/2 = 1.0; change 0.33.
            'avg_checkouts_per_borrower': {'value': 1.33, 'previous': 1.0, 'change': 0.33},
        })

    def test_week_charts(self):
        self.seed_week()
        data = self.get()
        self.assertEqual(data['borrowing_frequency_by_program'], {
            # Count desc, then name: the two zero-count programs tie and sort by name.
            'college': [
                {'program': 'BS in Computer Science', 'code': 'BSCS', 'count': 2},
                {'program': 'BS in Information Technology', 'code': 'BSIT', 'count': 1},
                {'program': 'BS in Accountancy', 'code': 'BSA', 'count': 0},
                {'program': 'BS in Nursing', 'code': 'BSN', 'count': 0},
            ],
            'senior_high': [{'program': 'STEM', 'code': 'STEM', 'count': 1}],
            'unassigned': [{'program': None, 'code': 'Unspecified', 'count': 0}],
        })
        # Mon: cs 09:00 + legacy 00:30 Manila (a UTC Sunday) = 2; Tue 1; Wed 1.
        self.assertEqual(data['checkouts_by_day_of_week'], weekdays(2, 1, 1, 0, 0, 0))

    def test_item_type_filters_loans_not_students(self):
        thesis = self.make_book('T-001', ItemType.THESIS)
        self.loan(self.cs, at(2026, 10, 6), returned=date(2026, 10, 7), book=thesis)  # 1 day
        self.loan(self.stem, at(2026, 10, 5), returned=date(2026, 10, 7))             # 2 days
        data = self.get(item_type='thesis')
        stats = data['statistics']
        self.assertEqual(data['filters']['item_type'], 'thesis')
        self.assertEqual(stats['registered_students'], 6)
        self.assertEqual(stats['active_borrowers'], {'value': 1, 'percentage': 16.7})  # 100/6 = 16.67
        self.assertEqual(stats['total_checkouts']['value'], 1)
        self.assertEqual(stats['avg_loan_duration_days']['value'], 1.0)
        self.assertEqual(data['borrowing_frequency_by_program']['college'][0]['count'], 1)
        self.assertEqual(data['borrowing_frequency_by_program']['senior_high'][0]['count'], 0)
        self.assertEqual(data['checkouts_by_day_of_week'], weekdays(0, 1, 0, 0, 0, 0))
        book = self.get(item_type='book')['statistics']
        self.assertEqual((book['total_checkouts']['value'], book['avg_loan_duration_days']['value']), (1, 2.0))

    def test_program_filter_scopes_the_population(self):
        self.seed_week()
        response = self.client.get(URL, {'program': ['BS in Computer Science', 'STEM', 'All']})
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data
        self.assertEqual(data['filters']['program'], ['BS in Computer Science', 'STEM'])
        stats = data['statistics']
        self.assertEqual(stats['registered_students'], 2)
        # cs Mon + Tue and stem Wed; both borrowed, so 2/2 = 100.0 and 3/2 = 1.5 per borrower.
        self.assertEqual(stats['active_borrowers'], {'value': 2, 'percentage': 100.0})
        self.assertEqual(stats['inactive_borrowers'], {'value': 0, 'percentage': 0.0})
        self.assertEqual(stats['total_checkouts'], {'value': 3, 'previous': 1, 'change_pct': 200.0})  # cs 09-30 11:00
        self.assertEqual(stats['avg_checkouts_per_borrower']['value'], 1.5)
        self.assertEqual(data['borrowing_frequency_by_program'], {
            'college': [{'program': 'BS in Computer Science', 'code': 'BSCS', 'count': 2}],
            'senior_high': [{'program': 'STEM', 'code': 'STEM', 'count': 1}],
            'unassigned': [],
        })
        everyone = self.get(program='All')
        self.assertEqual(everyone['filters']['program'], [])
        self.assertEqual(everyone['statistics']['registered_students'], 6)

    def test_rejects_invalid_params(self):
        for params in ({'range': 'month'}, {'item_type': 'magazine'}, {'education_level': 'grad'}):
            with self.subTest(params=params):
                self.get(expected=400, **params)

    def test_day_range_compares_yesterday_up_to_the_same_time(self):
        self.loan(self.cs, at(2026, 10, 7, 8))                                 # today
        self.loan(self.stem, at(2026, 10, 6, 9))                               # yesterday before 12:00
        self.loan(self.nursing, at(2026, 10, 6, 15))                           # yesterday after 12:00
        self.loan(self.legacy, at(2026, 10, 1), returned=date(2026, 10, 7))    # 6 days, today
        self.loan(self.nursing, at(2026, 10, 2), returned=date(2026, 10, 6))   # 4 days, yesterday
        data = self.get(range='day')
        self.assertEqual(data['period'], {'start_date': '2026-10-07', 'end_date': '2026-10-07',
                                          'previous_start_date': '2026-10-06'})
        stats = data['statistics']
        self.assertEqual(stats['active_borrowers'], {'value': 1, 'percentage': 16.7})     # 100/6
        self.assertEqual(stats['inactive_borrowers'], {'value': 5, 'percentage': 83.3})   # 500/6
        self.assertEqual(stats['total_checkouts'], {'value': 1, 'previous': 1, 'change_pct': 0.0})
        self.assertEqual(stats['avg_loan_duration_days'], {'value': 6.0, 'previous': 4.0, 'change': 2.0})
        self.assertEqual(stats['avg_checkouts_per_borrower'], {'value': 1.0, 'previous': 1.0, 'change': 0.0})
        self.assertEqual(data['checkouts_by_day_of_week'], weekdays(0, 0, 1, 0, 0, 0))

    def test_semester_range_compares_previous_term_and_drops_sundays_from_chart(self):
        self.term(academic_year='2025-2026', semester='2', start_date=date(2026, 2, 2), end_date=date(2026, 6, 30))
        current = self.term()  # Tue 2026-09-01 to Sun 2027-01-31
        # Elapsed: 09-01 00:00 to 10-07 12:00 = 36 days 12 h, so the previous span is [02-02, 03-10 12:00).
        # Returns: 09-01..10-07 is n = 37 days, so previous returns are 02-02..03-10.
        self.loan(self.cs, at(2026, 9, 1), returned=date(2026, 9, 5))       # Tue; 4 days
        self.loan(self.stem, at(2026, 10, 4))                               # Sunday: counted, not charted
        self.loan(self.legacy, at(2026, 10, 7, 9))                          # Wed
        self.loan(self.nursing, at(2026, 2, 3), returned=date(2026, 3, 10))  # previous; 35 days
        self.loan(self.stem, at(2026, 3, 2), returned=date(2026, 3, 11))    # previous checkout; return past span
        self.loan(self.cs, at(2026, 5, 1))                                  # previous term, past the elapsed span
        data = self.get(range='semester')
        self.assertEqual(data['academic_term']['status'], 'active')
        self.assertEqual(data['academic_term']['term']['id'], current.pk)
        self.assertEqual(data['period'], {'start_date': '2026-09-01', 'end_date': '2027-01-31',
                                          'previous_start_date': '2026-02-02'})
        stats = data['statistics']
        self.assertEqual(stats['active_borrowers'], {'value': 3, 'percentage': 50.0})
        # 3 vs 2: (3 - 2)*100/2 = 50.0.
        self.assertEqual(stats['total_checkouts'], {'value': 3, 'previous': 2, 'change_pct': 50.0})
        self.assertEqual(stats['avg_loan_duration_days'], {'value': 4.0, 'previous': 35.0, 'change': -31.0})
        self.assertEqual(stats['avg_checkouts_per_borrower'], {'value': 1.0, 'previous': 1.0, 'change': 0.0})
        self.assertEqual(data['checkouts_by_day_of_week'], weekdays(0, 1, 1, 0, 0, 0))

    def test_selected_past_term_without_an_earlier_term_has_no_comparison(self):
        past = self.term(academic_year='2025-2026', semester='2', start_date=date(2026, 2, 2), end_date=date(2026, 6, 30))
        self.term()
        self.loan(self.nursing, at(2026, 2, 3), returned=date(2026, 3, 10))  # 35 days
        self.loan(self.stem, at(2026, 3, 2), returned=date(2026, 3, 11))     # 9 days
        self.loan(self.cs, at(2026, 5, 1))
        data = self.get(range='semester', academic_year='2025-2026', semester='2')
        self.assertEqual(data['academic_term']['status'], 'selected')
        self.assertEqual(data['academic_term']['term']['id'], past.pk)
        self.assertEqual(data['period'], {'start_date': '2026-02-02', 'end_date': '2026-06-30',
                                          'previous_start_date': None})
        stats = data['statistics']
        self.assertEqual(stats['total_checkouts'], {'value': 3, 'previous': None, 'change_pct': None})
        self.assertEqual(stats['avg_loan_duration_days'], {'value': 22.0, 'previous': None, 'change': None})  # 44/2
        self.assertEqual(stats['avg_checkouts_per_borrower'], {'value': 1.0, 'previous': None, 'change': None})

    def test_education_level_picks_the_calendar_not_the_population(self):
        shs = self.term(education_level=EducationLevel.SENIOR_HIGH, start_date=date(2026, 8, 3), end_date=date(2026, 12, 18))
        self.term()
        self.loan(self.cs, at(2026, 8, 10))  # inside the SHS term only
        data = self.get(range='semester', education_level='senior_high')
        self.assertEqual(data['academic_term']['term']['id'], shs.pk)
        self.assertEqual(data['statistics']['registered_students'], 6)
        self.assertEqual(data['statistics']['total_checkouts']['value'], 1)
        self.assertEqual(data['borrowing_frequency_by_program']['college'][0],
                         {'program': 'BS in Computer Science', 'code': 'BSCS', 'count': 1})

    def test_semester_without_calendar_has_no_period(self):
        self.seed_week()
        data = self.get(range='semester')
        self.assertEqual(data['academic_term'], {'status': 'not_configured', 'term': None})
        self.assertIsNone(data['period'])
        self.assertEqual(data['statistics'], {
            'registered_students': 6, 'active_borrowers': None, 'inactive_borrowers': None,
            'total_checkouts': None, 'avg_loan_duration_days': None, 'avg_checkouts_per_borrower': None,
        })
        self.assertIsNone(data['borrowing_frequency_by_program'])
        self.assertIsNone(data['checkouts_by_day_of_week'])

    def test_year_range(self):
        timeline = AcademicYear.objects.create(academic_year='2026-2027', education_level=EducationLevel.COLLEGE,
                                               start_date=date(2026, 8, 15), end_date=date(2027, 7, 31))
        self.term(academic_year_timeline=timeline)
        # 2026-08-15 to 2027-08-01 is 351 days, so the previous span starts 2025-08-29 (365 - 351 = 14 days on).
        # Elapsed is 53 days 12 h, so last year's span ends 2025-10-21 12:00.
        self.loan(self.cs, at(2026, 8, 20))
        self.loan(self.stem, at(2025, 9, 15))
        self.loan(self.nursing, at(2025, 11, 1))  # past the elapsed span
        data = self.get(range='year')
        self.assertEqual(data['period'], {'start_date': '2026-08-15', 'end_date': '2027-07-31',
                                          'previous_start_date': '2025-08-29'})
        self.assertEqual(data['statistics']['total_checkouts'], {'value': 1, 'previous': 1, 'change_pct': 0.0})
        # Without a calendar: the twelve months 2025-11 through 2026-10, previous starting 365 days earlier.
        AcademicTerm.objects.all().delete()
        fallback = self.get(range='year')
        self.assertEqual(fallback['period'], {'start_date': '2025-11-01', 'end_date': '2026-10-31',
                                              'previous_start_date': '2024-11-01'})
        self.assertEqual(fallback['statistics']['total_checkouts']['value'], 2)  # nursing 2025-11-01, cs 2026-08-20

    def test_zero_denominators_are_null(self):
        nobody = self.get(program='Nobody')
        stats = nobody['statistics']
        self.assertEqual(stats['registered_students'], 0)
        self.assertEqual(stats['active_borrowers'], {'value': 0, 'percentage': None})
        self.assertEqual(stats['inactive_borrowers'], {'value': 0, 'percentage': None})
        self.assertEqual(nobody['borrowing_frequency_by_program'], {'college': [], 'senior_high': [], 'unassigned': []})
        self.assertEqual(nobody['checkouts_by_day_of_week'], weekdays(0, 0, 0, 0, 0, 0))
        quiet = self.get()['statistics']
        self.assertEqual(quiet['active_borrowers'], {'value': 0, 'percentage': 0.0})
        self.assertEqual(quiet['inactive_borrowers'], {'value': 6, 'percentage': 100.0})
        self.assertEqual(quiet['total_checkouts'], {'value': 0, 'previous': 0, 'change_pct': None})
        self.assertEqual(quiet['avg_loan_duration_days'], {'value': None, 'previous': None, 'change': None})
        self.assertEqual(quiet['avg_checkouts_per_borrower'], {'value': None, 'previous': None, 'change': None})
