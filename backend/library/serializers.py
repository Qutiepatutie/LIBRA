from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from .models import BookCopy, Books, BorrowRecords, RoomReservation, ItemType
from .copies import available_copies
from accounts.models import EducationLevel
from accounts.serializers import UserProfileSerializer, UserLoginSerializer
from django.utils import timezone
from .models import StatusChoices
from .user_analytics import library_timezone, money

# Title fields only; nested in loan records, where copy lists and counts do not belong.
class BookTitleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Books
        fields = [
            "id",
            "call_number",
            "isbn",
            "title",
            "author",
            "edition",
            "description",
            "tags",
            "publisher",
            "year_published",
            "pages",
            "cover_url",
            "item_type",
            "is_archived",
        ]

class CopyRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookCopy
        fields = ["id", "copy_number", "accession_number"]

class CopySerializer(serializers.ModelSerializer):
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = BookCopy
        fields = ["id", "copy_number", "accession_number", "condition", "date_acquired", "is_available"]

    def get_is_available(self, copy):
        # Listings annotate is_available (see copies.with_availability) so a page of copies costs no extra queries.
        if hasattr(copy, "is_available"):
            return copy.is_available
        return available_copies().filter(pk=copy.pk).exists()

class BooksSerializer(BookTitleSerializer):
    total_copies = serializers.IntegerField(read_only=True)
    available_copies = serializers.IntegerField(read_only=True)
    # Filled by the Prefetch in copies.catalog_books: non-archived copies, by copy number.
    copies = CopySerializer(source="listed_copies", many=True, read_only=True)

    class Meta(BookTitleSerializer.Meta):
        fields = BookTitleSerializer.Meta.fields + ["total_copies", "available_copies", "copies"]

class AddBooksSerializer(serializers.ModelSerializer):
    class Meta:
        model = Books
        fields = [
            "call_number",
            "isbn",
            "title",
            "author",
            "edition",
            "description",
            "tags",
            "publisher",
            "year_published",
            "pages",
            "cover_url",
            "item_type",
        ]
        extra_kwargs = {
            # Mirrors books_isbn_unique_nonblank: blank ISBNs (theses) may repeat.
            "isbn": {"validators": [
                UniqueValidator(queryset=Books.objects.exclude(isbn=""), message="Book already exists"),
            ]},
        }

    def validate(self, attrs):
        if not attrs.get("isbn") and attrs.get("item_type", ItemType.BOOK) != ItemType.THESIS:
            raise serializers.ValidationError({"isbn": "ISBN is required for books."})
        return attrs

# The per-copy fields accepted by addBook, addCopy and editCopy; every one is optional.
class CopyFieldsSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookCopy
        fields = ["accession_number", "condition", "date_acquired"]
        extra_kwargs = {
            # Mirrors book_copy_accession_unique_nonblank: copies without a barcode may repeat ''.
            "accession_number": {"validators": [
                UniqueValidator(queryset=BookCopy.objects.exclude(accession_number=""),
                                message="Accession number already exists"),
            ]},
            "condition": {"error_messages": {
                "invalid_choice": "Invalid condition", "blank": "Invalid condition", "null": "Invalid condition",
            }},
        }

class AllBorrowRecordSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    email = serializers.CharField(source="user.user.email")
    book = BookTitleSerializer(read_only=True)
    copy = CopyRefSerializer(read_only=True)
    
    class Meta:
        model = BorrowRecords
        fields = [
            "id",
            "user",
            "email",
            "book",
            "copy",
            "borrow_date",
            "return_date",
            "due_date",
            "status"
        ]
        
class UserBorrowRecordSerializer(serializers.ModelSerializer):
    cover_url = serializers.CharField(source="copy.book.cover_url")
    
    class Meta:
        model = BorrowRecords
        fields = [
            "id",
            "cover_url",
            "due_date",
            "status"
        ]

class RoomReservationSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    email = serializers.CharField(
        source="user.user.email",
        read_only=True
    )

    class Meta:
        model = RoomReservation
        fields = [
            "user",
            "email",
            "campus",
            "department",
            "participants",
            "lrc",
            "room",
            "start_time",
            "end_time",
            "status",
            "created_at",
            "updated_at"
        ]

class DashboardLoanSerializer(serializers.ModelSerializer):
    loan_id = serializers.IntegerField(source='pk', read_only=True)
    book_id = serializers.IntegerField(source='copy.book_id', read_only=True)
    title = serializers.CharField(source='copy.book.title', read_only=True)
    call_number = serializers.CharField(source='copy.book.call_number', read_only=True)
    copy_number = serializers.IntegerField(source='copy.copy_number', read_only=True)
    accession_number = serializers.CharField(source='copy.accession_number', read_only=True)
    borrow_date = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    fine = serializers.SerializerMethodField()

    class Meta:
        model = BorrowRecords
        fields = ('loan_id', 'book_id', 'title', 'call_number', 'copy_number', 'accession_number',
                  'borrow_date', 'due_date', 'return_date', 'status', 'fine')

    def get_borrow_date(self, loan):
        if loan.status == StatusChoices.PENDING or loan.borrow_date is None:
            return None
        return timezone.localtime(loan.borrow_date, library_timezone()).isoformat()

    def get_status(self, loan):
        if loan.status == StatusChoices.PENDING:
            return 'Pending'
        if loan.return_date:
            return 'Returned'
        if loan.due_date and loan.due_date < self.context['today']:
            return 'Overdue'
        if loan.due_date == self.context['today']:
            return 'Due'
        return 'Active'

    def get_fine(self, loan):
        fine = getattr(loan, 'fine', None)
        assessed, paid = (fine.amount_assessed, fine.amount_paid) if fine else (0, 0)
        return {'currency': 'PHP', 'amount_assessed': money(assessed),
                'amount_paid': money(paid), 'outstanding': money(assessed - paid)}


class DashboardPageQuerySerializer(serializers.Serializer):
    page = serializers.IntegerField(default=1, min_value=1)
    page_size = serializers.IntegerField(default=20, min_value=1, max_value=100)


class CirculationQuerySerializer(serializers.Serializer):
    range = serializers.ChoiceField(choices=('day', 'week', 'semester', 'year'), default='week')
    item_type = serializers.ChoiceField(choices=('all', *ItemType.values), default='all')
    # Repeat the parameter to group several programs, e.g. one college's degrees.
    program = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    academic_year = serializers.CharField(required=False, default='')
    semester = serializers.CharField(required=False, default='')
    education_level = serializers.ChoiceField(choices=EducationLevel.choices, default=EducationLevel.COLLEGE)

    def validate(self, attrs):
        # Dropdowns send "all" for an unfiltered value; treat it like an omitted parameter.
        for field in ('academic_year', 'semester'):
            if attrs[field].strip().lower() == 'all':
                attrs[field] = ''
        attrs['program'] = [program for program in attrs['program'] if program.strip().lower() != 'all']
        return attrs


class BorrowersQuerySerializer(CirculationQuerySerializer):
    # Which borrowers the Borrowers tab counts; Circulation always counts everyone.
    role = serializers.ChoiceField(choices=('student', 'faculty', 'all'), default='student')
