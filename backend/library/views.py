import csv
import io
import json
from .analytics import circulation_trends, borrowing_frequency, inventory_status
from django.views.decorators.csrf import csrf_exempt
from .decorators import admin_role
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import F

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination

from .models import Books, BorrowRecords, UserProfile, StatusChoices
from .serializers import AllBorrowRecordSerializer, UserBorrowRecordSerializer, BooksSerializer, AddBooksSerializer
from .serializers import DashboardLoanSerializer, DashboardPageQuerySerializer
from . import user_analytics

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_books(request):
    books = Books.objects.all()

    serializer = BooksSerializer(books, many=True)
    return Response({"data": serializer.data}, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_books(request):
    call_number = request.data.get("call_number")
    isbn = request.data.get("isbn")
    title = request.data.get("title")
    author = request.data.get("author")

    if not all([call_number, isbn, title, author]):
        return Response({'message': 'Missing important fields'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = AddBooksSerializer(data=request.data)

    if not serializer.is_valid():
        print(serializer.errors)

        return Response({"message": serializer.errors["isbn"][0]}, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response({'message':'Book Successfully Added!'}, status=status.HTTP_200_OK)

@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def edit_book(request):
    isbn = request.data.get("isbn")

    if not isbn:
        return Response({"message":"Missing isbn"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        book = Books.objects.get(isbn=isbn)
    except Books.DoesNotExist:
        return Response({"message":"Book does not exist"}, status=status.HTTP_404_NOT_FOUND)

    new_call_number = request.data.get("callNumber")

    if new_call_number and Books.objects.exclude(pk=book.pk).filter(call_number=new_call_number).exists():
        return Response({"message":"Call number already exists"}, status=status.HTTP_400_BAD_REQUEST)

    book.description = request.data.get("description", book.description)
    book.title = request.data.get("title", book.title)
    book.author = request.data.get("author", book.author)
    book.call_number = new_call_number or book.call_number
    book.pages = request.data.get("pages", book.pages)
    book.publisher = request.data.get("publisher", book.publisher)
    book.year_published = request.data.get("yearPublished", book.year_published)
    book.tags = request.data.get("tags", book.tags)

    book.save()

    return Response ({"message":"Book Successfully Edited"}, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def borrow_book(request):
    id_number = request.data.get("id_number")
    isbn = request.data.get("isbn")

    try:
        user = UserProfile.objects.get(id_number=id_number)
    except UserProfile.DoesNotExist:
        return Response({"message":"User not found"}, status=status.HTTP_404_NOT_FOUND)

    try:
        book = Books.objects.get(isbn=isbn)
    except Books.DoesNotExist:
        return Response({"message":"Book not found"}, status=status.HTTP_404_NOT_FOUND)

    if BorrowRecords.objects.filter(book=book, return_date__isnull=True).exists():
        return Response({"message":"Book is already borrowed"}, status=status.HTTP_400_BAD_REQUEST)

    BorrowRecords.objects.create(
        status = StatusChoices.PENDING,
        user = user,
        book = book
    )

    return Response({"message":"Book successfully borrowed"}, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def get_user_borrowed_books(request):
    id_number = request.data.get("id")

    try:
        user = UserProfile.objects.get(id_number=id_number)
    except UserProfile.DoesNotExist:
        return Response({"message":"User not found"}, status=status.HTTP_404_NOT_FOUND)

    borrowed_books = BorrowRecords.objects.filter(user=user, return_date__isnull=True)
    serializer = UserBorrowRecordSerializer(borrowed_books, many=True)

    return Response({"books": serializer.data}, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_borrowed_books(request):
    records = BorrowRecords.objects.filter(user__user__isnull=False).select_related("user__user", "book")
    serializer = AllBorrowRecordSerializer(records, many=True)

    return Response({
        "message": "Borrowed books fetched successfully",
        "data":serializer.data
    }, status=status.HTTP_200_OK)

# TO FIX
# You can do this in frontend
# Just export the table contents
@csrf_exempt
def export_borrowed_books_csv(request):
    if request.method != 'GET':
        return JsonResponse({'status': 'failed', 'message': 'Invalid request method'})

    try:
        records = BorrowRecords.objects.filter(
            user__user__isnull=False
        ).select_related("user__user", "book")

        buffer = io.StringIO()
        writer = csv.writer(buffer)

        # Header row
        writer.writerow([
            'Record ID',
            'Status',
            'Borrow Date',
            'Due Date',
            'Return Date',
            # User fields
            'User ID Number',
            'First Name',
            'Middle Name',
            'Last Name',
            'Email',
            'Program',
            # Book fields
            'Book Title',
            'ISBN',
            'Call Number',
        ])

        for r in records:
            writer.writerow([
                r.pk,
                r.status,
                r.borrow_date.strftime('%Y-%m-%d %H:%M') if r.borrow_date else '',
                r.due_date.isoformat() if r.due_date else '',
                r.return_date.isoformat() if r.return_date else '',
                # User fields
                r.user.id_number,
                r.user.first_name,
                r.user.middle_name or '',
                r.user.last_name,
                r.user.user.email,
                r.user.program or '',
                # Book fields
                r.book.title,
                r.book.isbn,
                r.book.call_number,
            ])
        current_date = timezone.now().strftime('%Y_%m_%d_%H%M')
        response = HttpResponse(buffer.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="borrowed_books_{current_date}.csv"'
        return response

    except Exception as e:
        return JsonResponse({"status": "failed", "message": "CSV export failed", "error": str(e)})

@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def accept_borrowed_book(request):
    isbn = request.data.get("isbn")
    call_num = request.data.get("call_num")

    book_record = BorrowRecords.objects.filter(book__isbn=isbn, book__call_number=call_num, return_date__isnull=True).first()
    if not book_record:
        return Response({"message":"Book not found"}, status=status.HTTP_404_NOT_FOUND)

    book_record.borrow_date = timezone.now()
    book_record.due_date = user_analytics.library_today(book_record.borrow_date) + timezone.timedelta(days=7)
    book_record.status = StatusChoices.ACTIVE

    book_record.save()

    return Response({
        "message":"Borrower Accepted",
        "book" : {
                "status": book_record.status,
                "due_date":book_record.due_date.isoformat(),
            }
        }, status=status.HTTP_200_OK);

@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def return_book(request):
    isbn = request.data.get("isbn")
    call_num = request.data.get("call_num")

    book = BorrowRecords.objects.filter(
        book__isbn=isbn,
        book__call_number=call_num,
        return_date__isnull=True
    ).first()
    
    if not book:
        return Response({"message": "No active book found"}, status=status.HTTP_404_NOT_FOUND)

    book.status = StatusChoices.RETURNED

    book.return_date = user_analytics.library_today()
    book.save()

    return Response({"message": "Book returned successfully"}, status=status.HTTP_200_OK)
    
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def cancel_borrowed_book(request):
    isbn = request.data.get("isbn")
    call_num = request.data.get("call_num")

    book = BorrowRecords.objects.filter(
        book__isbn=isbn, 
        book__call_number=call_num, 
        return_date__isnull=True,
        status=StatusChoices.PENDING
    ).first()
    
    if not book:
        return Response({"message": "No active book found"}, status=status.HTTP_404_NOT_FOUND)

    book.status = StatusChoices.CANCELLED
    book.save()

    return Response({"message": "Book borrow cancelled successfully"}, status=status.HTTP_200_OK)

#NOT FINSIHED, WILL FIX LATER
@csrf_exempt
@admin_role #checks if user is admin, spoofable rn tho
def analytics_dashboard(request):
    if request.method != 'GET':
        return JsonResponse({"status":"failed", "message":"Invalid request method"})
    try:
        data = {
            'circulation_trends' : circulation_trends(),
            'borrowing_frequency' : borrowing_frequency(),
            'inventory_status': inventory_status(),
        }
        return JsonResponse({'status' : 'success', 'message' : 'Analytics data fetched successfully','data' : data})
    except Exception as e:
        return JsonResponse({'status' : 'failed', 'message' : 'Analytics data fetch failed', 'error' : str(e)})


def _dashboard_profile(request):
    try:
        return request.user.profile
    except UserProfile.DoesNotExist:
        raise NotFound('User profile not found.')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_analytics(request):
    profile = _dashboard_profile(request)
    return Response(user_analytics.dashboard(profile, timezone.now()))


def _dashboard_loan_page(request, loans, now, summary=None):
    query = DashboardPageQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    paginator = PageNumberPagination()
    paginator.page_size = query.validated_data['page_size']
    loans = loans.select_related('book', 'fine').order_by(F('borrow_date').desc(nulls_last=True), '-pk')
    page = paginator.paginate_queryset(loans, request)
    serializer = DashboardLoanSerializer(page, many=True, context={'today': user_analytics.library_today(now)})
    response = paginator.get_paginated_response(serializer.data)
    if summary is not None:
        response.data['summary'] = summary
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_current_loans(request):
    profile = _dashboard_profile(request)
    now = timezone.now()
    return _dashboard_loan_page(request, user_analytics.current_loans(profile, now), now)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_borrowing_history(request):
    profile = _dashboard_profile(request)
    now = timezone.now()
    return _dashboard_loan_page(
        request, user_analytics.actual_loans(profile, now), now,
        summary=user_analytics.history_summary(profile, now),
    )
