from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase

from .models import AcademicTerm, AcademicYear


class AcademicYearTests(TestCase):
    def setUp(self):
        self.timeline = AcademicYear.objects.create(
            academic_year="2026-2027",
            education_level="college",
            start_date=date(2026, 8, 17),
            end_date=date(2027, 6, 1),
        )

    def make_semester(self, **overrides):
        values = {
            "academic_year_timeline": self.timeline,
            "academic_year": "2026-2027",
            "semester": "1",
            "education_level": "college",
            "start_date": date(2026, 8, 17),
            "end_date": date(2026, 12, 18),
        }
        values.update(overrides)
        semester = AcademicTerm(**values)
        semester.full_clean()
        semester.save()
        return semester

    def test_two_semesters_share_academic_year_timeline(self):
        first = self.make_semester()
        second = self.make_semester(
            semester="2",
            start_date=date(2027, 1, 4),
            end_date=date(2027, 6, 1),
        )
        self.assertEqual(
            set(self.timeline.semesters.values_list("pk", flat=True)),
            {first.pk, second.pk},
        )

    def test_unlinked_legacy_semester_remains_valid(self):
        semester = self.make_semester(academic_year_timeline=None)
        semester.refresh_from_db()
        self.assertIsNone(semester.academic_year_timeline_id)
        self.assertEqual(semester.academic_year, "2026-2027")

    def test_semester_dates_must_fit_parent_inclusively(self):
        for field, value in (
            ("start_date", date(2026, 8, 16)),
            ("end_date", date(2027, 6, 2)),
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.make_semester(**{field: value})
        semester = self.make_semester(end_date=self.timeline.end_date)
        self.assertEqual(semester.start_date, self.timeline.start_date)
        self.assertEqual(semester.end_date, self.timeline.end_date)

    def test_linked_semester_requires_matching_label_and_education_level(self):
        for field, value in (
            ("academic_year", "2027-2028"),
            ("education_level", "senior_high"),
        ):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.make_semester(**{field: value})

    def test_default_year_timeline_accepts_specific_cohort(self):
        semester = self.make_semester(year_level="1")
        self.assertEqual(semester.academic_year_timeline_id, self.timeline.pk)

    def test_specific_year_timeline_requires_same_cohort(self):
        self.timeline.year_level = "1"
        self.timeline.save()
        for cohort in (None, "", "2"):
            with self.subTest(cohort=cohort), self.assertRaises(ValidationError):
                self.make_semester(year_level=cohort)
        semester = self.make_semester(year_level="1")
        self.assertEqual(semester.year_level, self.timeline.year_level)

    def test_parent_date_edit_cannot_exclude_existing_semester(self):
        self.make_semester()
        for field, value in (
            ("start_date", date(2026, 8, 18)),
            ("end_date", date(2026, 12, 17)),
        ):
            self.timeline.refresh_from_db()
            with self.subTest(field=field), self.assertRaises(ValidationError):
                setattr(self.timeline, field, value)
                self.timeline.save()
        self.timeline.refresh_from_db()
        self.assertEqual(self.timeline.start_date, date(2026, 8, 17))
        self.assertEqual(self.timeline.end_date, date(2027, 6, 1))

    def test_parent_dates_can_match_semester_boundaries(self):
        semester = self.make_semester()
        self.timeline.start_date = semester.start_date
        self.timeline.end_date = semester.end_date
        self.timeline.save()
        self.timeline.refresh_from_db()
        self.assertEqual(self.timeline.end_date, semester.end_date)

    def test_parent_scope_edit_cannot_invalidate_existing_semester(self):
        self.make_semester(year_level="1")
        for field, value in (
            ("academic_year", "2027-2028"),
            ("education_level", "senior_high"),
            ("year_level", "2"),
        ):
            self.timeline.refresh_from_db()
            with self.subTest(field=field), self.assertRaises(ValidationError):
                setattr(self.timeline, field, value)
                self.timeline.save()
        self.timeline.refresh_from_db()
        self.assertEqual(self.timeline.academic_year, "2026-2027")
        self.assertEqual(self.timeline.education_level, "college")
        self.assertFalse(self.timeline.year_level)

    def test_parent_can_adopt_cohort_matching_all_children(self):
        self.make_semester(year_level="1")
        self.timeline.year_level = "1"
        self.timeline.save()
        self.timeline.refresh_from_db()
        self.assertEqual(self.timeline.year_level, "1")

    def test_parent_with_linked_semester_cannot_be_deleted(self):
        semester = self.make_semester()
        with self.assertRaises(ProtectedError):
            self.timeline.delete()
        self.assertTrue(AcademicTerm.objects.filter(pk=semester.pk).exists())

    def test_unlinked_semester_does_not_protect_unused_parent(self):
        semester = self.make_semester(academic_year_timeline=None)
        self.timeline.delete()
        self.assertTrue(AcademicTerm.objects.filter(pk=semester.pk).exists())

    def test_invalid_parent_dates_rejected_on_save(self):
        self.timeline.end_date = date(2026, 8, 16)
        with self.assertRaises(ValidationError):
            self.timeline.save()

    def test_database_enforces_parent_date_order(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            AcademicYear.objects.filter(pk=self.timeline.pk).update(
                end_date=date(2026, 8, 16)
            )

    def test_default_scope_unique_for_null_and_empty_year_levels(self):
        for cohort in (None, ""):
            with self.subTest(cohort=cohort), self.assertRaises(ValidationError):
                AcademicYear.objects.create(
                    academic_year="2026-2027",
                    education_level="college",
                    year_level=cohort,
                    start_date=date(2026, 8, 17),
                    end_date=date(2027, 6, 1),
                )

    def test_database_enforces_default_scope_uniqueness(self):
        for cohort in (None, ""):
            with self.subTest(cohort=cohort):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    AcademicYear.objects.bulk_create([
                        AcademicYear(
                            academic_year="2026-2027",
                            education_level="college",
                            year_level=cohort,
                            start_date=date(2026, 8, 17),
                            end_date=date(2027, 6, 1),
                        )
                    ])

    def test_cohort_override_is_distinct_but_cannot_be_duplicated(self):
        override = AcademicYear.objects.create(
            academic_year="2026-2027",
            education_level="college",
            year_level="1",
            start_date=date(2026, 8, 24),
            end_date=date(2027, 6, 1),
        )
        self.assertNotEqual(override.pk, self.timeline.pk)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AcademicYear.objects.bulk_create([
                AcademicYear(
                    academic_year=override.academic_year,
                    education_level=override.education_level,
                    year_level=override.year_level,
                    start_date=override.start_date,
                    end_date=override.end_date,
                )
            ])

    def test_invalid_year_level_rejected(self):
        self.timeline.year_level = "first"
        with self.assertRaises(ValidationError):
            self.timeline.save()
