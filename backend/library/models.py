from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from accounts.models import UserProfile, EducationLevel, year_level_validator

class StatusChoices(models.TextChoices):
    ACTIVE = 'Active'
    DUE = 'Due'
    OVERDUE = 'Overdue'
    PENDING = 'Pending'
    RETURNED = 'Returned'
    CANCELLED = 'Cancelled'

# Manages books
class Books(models.Model):
    call_number = models.CharField(
        max_length=50,
        unique=True
    )

    isbn = models.CharField(
        max_length=13,
        blank=True,
    )

    title = models.CharField(
        max_length=200
    )
    
    author = models.CharField(
        max_length=100
    )
    
    edition = models.CharField(
        max_length=50,
        blank=True
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    tags = models.JSONField(
        default=list,
        blank=True
    )

    publisher = models.CharField(
        max_length=100
    )

    year_published = models.CharField(
        max_length=4
    )

    pages = models.CharField(
        max_length=50
    )
    
    #Media
    cover_url = models.CharField(
        max_length=2048,
        blank=True,
        null=True,
    )

    date_acquired = models.CharField(
        max_length=100,
        blank=True
    )

    class Meta:
        db_table = 'books'
    
class BorrowRecords(models.Model):
    user = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE
    )

    book = models.ForeignKey(
        Books,
        on_delete=models.CASCADE
    )

    borrow_date = models.DateTimeField(
        blank=True,
        null=True,
    )

    return_date = models.DateField(
        blank=True,
        null=True
    )

    due_date = models.DateField(
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PENDING,
    )

    class Meta:
        db_table = 'borrow_records'
        indexes = [models.Index(fields=['user', 'borrow_date'], name='loan_user_borrow_idx')]


def effective_academic_terms(terms, year_level):
    """Choose cohort overrides before filtering dates, including future overrides."""
    selected = {}
    for term in terms:
        key = (term.academic_year, term.semester)
        if term.year_level == year_level and year_level:
            selected[key] = term
        elif not term.year_level and (key not in selected or not selected[key].year_level):
            selected[key] = term
    return list(selected.values())

class AcademicYear(models.Model):
    """The full academic-year timeline for an education level and optional cohort."""

    academic_year = models.CharField(max_length=50)
    education_level = models.CharField(max_length=50, choices=EducationLevel.choices)
    year_level = models.CharField(
        max_length=50, blank=True, null=True, validators=[year_level_validator],
    )
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        db_table = 'academic_year'
        constraints = [
            models.UniqueConstraint(
                fields=['academic_year', 'education_level', 'year_level'],
                name='unique_academic_year_scope',
            ),
            models.UniqueConstraint(
                fields=['academic_year', 'education_level'],
                condition=models.Q(year_level__isnull=True) | models.Q(year_level=''),
                name='unique_academic_year_default',
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F('start_date')),
                name='academic_year_valid_dates',
            ),
        ]

    def validate_semester(self, semester):
        """Keep the existing semester metadata consistent with its year timeline."""
        if (semester.academic_year != self.academic_year
                or semester.education_level != self.education_level
                or (self.year_level and semester.year_level != self.year_level)):
            raise ValidationError('Semester scope must match its academic-year timeline.')
        if semester.start_date < self.start_date or semester.end_date > self.end_date:
            raise ValidationError('Semester dates must fall within the academic-year timeline.')

    def clean(self):
        super().clean()
        if not self.start_date or not self.end_date:
            return
        if self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date must be on or after start date.'})
        if self.pk:
            for semester in self.semesters.all():
                self.validate_semester(semester)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.academic_year} / {self.education_level} / {self.year_level or "all years"}'


class AcademicTerm(models.Model):
    """One semester's calendar for an education level and optional cohort."""

    academic_year = models.CharField(
        max_length=50
    )

    # Existing semester calendars can be linked after full-year dates are configured.
    academic_year_timeline = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name='semesters',
        blank=True, null=True,
    )

    semester = models.CharField(
        max_length=50
    )
    education_level = models.CharField(
        max_length=50, choices=EducationLevel.choices
    )

    year_level = models.CharField( #optional for cases where one specific year level
        max_length=50,            #has a different Academic year schedule
        blank=True,
        null=True,
        validators=[year_level_validator],
    )

    start_date = models.DateField()

    end_date = models.DateField()

    def __str__(self):
        return f'{self.academic_year} / {self.semester} / {self.education_level} / {self.year_level or "all years"}'

    def clean(self):
        super().clean()
        if not self.start_date or not self.end_date:
            return
        if self.end_date < self.start_date:
            raise ValidationError({'end_date': 'End date must be on or after start date.'})
        if self.academic_year_timeline_id:
            timeline = AcademicYear.objects.filter(pk=self.academic_year_timeline_id).first()
            if timeline is not None:
                timeline.validate_semester(self)
        terms = list(type(self).objects.filter(education_level=self.education_level).exclude(pk=self.pk))
        terms.append(self)
        for year in {None, *(term.year_level for term in terms if term.year_level)}:
            effective = effective_academic_terms(terms, year)
            if self not in effective:
                continue
            for other in effective:
                if other is not self and self.start_date <= other.end_date and other.start_date <= self.end_date:
                    raise ValidationError('Effective academic terms cannot overlap for the same student cohort.')

    class Meta:
        db_table = 'academics_term'
        constraints = [
            models.UniqueConstraint(
                fields=['academic_year', 'semester', 'education_level', 'year_level'],
                name='unique_academic_term_scope',
            ),
            # Both NULL and an empty string represent the default year-level scope.
            models.UniqueConstraint(
                fields=['academic_year', 'semester', 'education_level'],
                condition=models.Q(year_level__isnull=True) | models.Q(year_level=''),
                name='unique_academic_term_default',
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F('start_date')),
                name='academic_term_valid_dates',
            ),
        ]


class LoanFine(models.Model):
    """Recorded totals in PHP; returning a loan does not settle its fine."""

    loan = models.OneToOneField(BorrowRecords,
        on_delete=models.PROTECT,
        related_name='fine'
    )
    amount_assessed = models.DecimalField(max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )

    amount_paid = models.DecimalField(max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )

    note = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'loan_fine'
        constraints = [
            models.CheckConstraint(condition=models.Q(amount_assessed__gte=0), name='fine_assessed_nonnegative'),
            models.CheckConstraint(condition=models.Q(amount_paid__gte=0), name='fine_paid_nonnegative'),
            models.CheckConstraint(condition=models.Q(amount_paid__lte=models.F('amount_assessed')), name='fine_paid_not_above_assessed'),
        ]

    def clean(self):
        super().clean()
        if self.loan_id and (not self.loan.borrow_date or self.loan.status in (StatusChoices.PENDING, StatusChoices.CANCELLED)):
            raise ValidationError({'loan': 'Fines require an actual checkout.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f'Loan {self.loan_id}: PHP {self.amount_assessed} assessed, {self.amount_paid} paid'
