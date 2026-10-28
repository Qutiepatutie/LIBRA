from rest_framework import serializers
from .models import Books, BorrowRecords
from accounts.serializers import UserProfileSerializer, UserLoginSerializer
from django.utils import timezone
from .models import StatusChoices
from .user_analytics import library_timezone, money

class BooksSerializer(serializers.ModelSerializer):
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
            "date_acquired",
            "item_type"
        ]
        
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
            "date_acquired",
            "item_type"
        ]

    def validate_isbn(self, value):
        if Books.objects.filter(isbn=value).exists():
            raise serializers.ValidationError(
                "Book already exists"
            )
        return value

class AllBorrowRecordSerializer(serializers.ModelSerializer):
    user = UserProfileSerializer(read_only=True)
    email = serializers.CharField(source="user.user.email")
    book = BooksSerializer(read_only=True)
    
    class Meta:
        model = BorrowRecords
        fields = [
            "user",
            "email",
            "book",
            "borrow_date",
            "return_date",
            "due_date",
            "status"
        ]
        
class UserBorrowRecordSerializer(serializers.ModelSerializer):
    cover_url = serializers.CharField(source="book.cover_url")
    
    class Meta:
        model = BorrowRecords
        fields = [
            "cover_url",
            "due_date",
            "status"
        ]


class DashboardLoanSerializer(serializers.ModelSerializer):
    loan_id = serializers.IntegerField(source='pk', read_only=True)
    book_id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(source='book.title', read_only=True)
    call_number = serializers.CharField(source='book.call_number', read_only=True)
    borrow_date = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    fine = serializers.SerializerMethodField()

    class Meta:
        model = BorrowRecords
        fields = ('loan_id', 'book_id', 'title', 'call_number', 'borrow_date',
                  'due_date', 'return_date', 'status', 'fine')

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
