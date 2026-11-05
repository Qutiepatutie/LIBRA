import csv
import io
import json
from django.views.decorators.csrf import csrf_exempt
from .permissions import IsAdminRole
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import F

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination

from .models import Books, BorrowRecords, UserProfile, RoomReservation, StatusChoices, ItemType, ConditionChoices
from .serializers import AllBorrowRecordSerializer, UserBorrowRecordSerializer, BooksSerializer, AddBooksSerializer, RoomReservationSerializer
from .serializers import DashboardLoanSerializer, DashboardPageQuerySerializer, CirculationQuerySerializer, BorrowersQuerySerializer
from . import admin_analytics, inventory_analytics, borrower_analytics, user_analytics

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
    title = request.data.get("title")
    author = request.data.get("author")

    # ISBN is optional for theses; AddBooksSerializer requires it for books.
    if not all([call_number, title, author]):
        return Response({'message': 'Missing important fields'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = AddBooksSerializer(data=request.data)

    if not serializer.is_valid():
        first_errors = next(iter(serializer.errors.values()))
        return Response({"message": first_errors[0], "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response({'message':'Book Successfully Added!'}, status=status.HTTP_200_OK)

def _requested_book_id(request):
    """Items are identified by primary key: theses may lack an ISBN and call numbers can be edited."""
    try:
        return int(request.data.get("book_id"))
    except (TypeError, ValueError):
        return None

def _missing_book_id():
    return Response({"message": "Missing book_id"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def edit_book(request):
    book_id = _requested_book_id(request)

    if book_id is None:
        return _missing_book_id()

    try:
        book = Books.objects.get(pk=book_id)
    except Books.DoesNotExist:
        return Response({"message":"Book does not exist"}, status=status.HTTP_404_NOT_FOUND)

    new_call_number = request.data.get("call_number")

    if new_call_number and Books.objects.exclude(pk=book.pk).filter(call_number=new_call_number).exists():
        return Response({"message":"Call number already exists"}, status=status.HTTP_400_BAD_REQUEST)

    item_type = request.data.get("itemType", book.item_type)
    condition = request.data.get("condition", book.condition)
    if item_type not in ItemType.values:
        return Response({"message":"Invalid item type"}, status=status.HTTP_400_BAD_REQUEST)
    if condition not in ConditionChoices.values:
        return Response({"message":"Invalid condition"}, status=status.HTTP_400_BAD_REQUEST)

    book.description = request.data.get("description", book.description)
    book.title = request.data.get("title", book.title)
    book.author = request.data.get("author", book.author)
    book.call_number = new_call_number or book.call_number
    book.pages = request.data.get("pages", book.pages)
    book.publisher = request.data.get("publisher", book.publisher)
    book.year_published = request.data.get("year_published", book.year_published)
    book.tags = request.data.get("tags", book.tags)
    book.item_type = item_type
    book.condition = condition

    book.save()

    return Response ({"message":"Book Successfully Edited"}, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def borrow_book(request):
    id_number = request.data.get("id_number")
    book_id = _requested_book_id(request)

    try:
        user = UserProfile.objects.get(id_number=id_number)
    except UserProfile.DoesNotExist:
        return Response({"message":"User not found"}, status=status.HTTP_404_NOT_FOUND)

    if book_id is None:
        return _missing_book_id()

    try:
        book = Books.objects.get(pk=book_id)
    except Books.DoesNotExist:
        return Response({"message":"Book not found"}, status=status.HTTP_404_NOT_FOUND)

    # A pending request or any checkout not yet returned (Active, Due, Overdue) holds the item.
    open_statuses = [StatusChoices.PENDING, *user_analytics.OPEN_STATUSES]
    if BorrowRecords.objects.filter(book=book, status__in=open_statuses).exists():
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
    book_id = _requested_book_id(request)
    if book_id is None:
        return _missing_book_id()

    # Only a pending request can be accepted; cancelled ones also have no return date.
    book_record = BorrowRecords.objects.filter(book_id=book_id, status=StatusChoices.PENDING).first()
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
    book_id = _requested_book_id(request)
    if book_id is None:
        return _missing_book_id()

    book = BorrowRecords.objects.filter(
        book_id=book_id,
        status__in=user_analytics.OPEN_STATUSES,
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
    book_id = _requested_book_id(request)
    if book_id is None:
        return _missing_book_id()

    book = BorrowRecords.objects.filter(
        book_id=book_id,
        return_date__isnull=True,
        status=StatusChoices.PENDING
    ).first()
    
    if not book:
        return Response({"message": "No active book found"}, status=status.HTTP_404_NOT_FOUND)

    book.status = StatusChoices.CANCELLED
    book.save()

    return Response({"message": "Book borrow cancelled successfully"}, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def reserve_room(request):
    try:
        user = request.user.profile
    except UserProfile.DoesNotExist:
        return Response({"message":"User not found"}, status=status.HTTP_404_NOT_FOUND)

    if RoomReservation.objects.filter(user=user, status=(StatusChoices.PENDING)):
        return Response({"message":"You cannot reserve 2 or more room at a time"}, status=status.HTTP_400_BAD_REQUEST)
    
    serializer = RoomReservationSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({
            "message": "Invalid request",
            "errors": serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)

    serializer.save(user=user)
    return Response({
        "message": "Room Reserved Successfully",
        "data": serializer.data,
    }, status=status.HTTP_201_CREATED)
    
@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def accept_reserved_room(request):
    start_time = request.data.get("start_time")
    end_time = request.data.get("end_time")
    
    try:
        reservation = RoomReservation.objects.get(
            start_time=start_time,
            end_time=end_time,
            status=StatusChoices.PENDING
        ) 
        
    except RoomReservation.DoesNotExist:
            return Response({
                "message":"Reservation not found"
            }, status=status.HTTP_404_NOT_FOUND)

    reservation.status = StatusChoices.ACTIVE
    
    reservation.save(update_fields=["status", "updated_at"])

    return Response({
        "message": "Current room reservation is now active",
    }, status=status.HTTP_200_OK)

@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def cancel_reserved_room(request):
    start_time = request.data.get("start_time")
    end_time = request.data.get("end_time")
    
    try:
        reservation = RoomReservation.objects.get(
            start_time=start_time,
            end_time=end_time,
            status=StatusChoices.PENDING
        ) 
        
    except RoomReservation.DoesNotExist:
            return Response({
                "message":"Reservation not found"
            }, status=status.HTTP_404_NOT_FOUND)

    reservation.status = StatusChoices.CANCELLED
    
    reservation.save(update_fields=["status", "updated_at"])

    return Response({
        "message": "Current room reservation is Cancelled",
    }, status=status.HTTP_200_OK)


def update_expired_reservation():
    now = timezone.localtime().time()

    RoomReservation.objects.filter(
        status=StatusChoices.ACTIVE,
        end_time__lte=now
    ).update(
        status=StatusChoices.COMPLETED,
        updated_at=timezone.now()
    )

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_reserved_rooms(request):
    update_expired_reservation()
    
    try:
        user = request.user.profile
    except UserProfile.DoesNotExist:
        return Response({"message":"User not found"}, status=status.HTTP_404_NOT_FOUND)
    
    reserved_rooms = RoomReservation.objects.filter(user=user, status__in=[StatusChoices.PENDING, StatusChoices.ACTIVE])
    serializer = RoomReservationSerializer(reserved_rooms, many=True)

    return Response({
        "message": "Reserved room fetched successfully",
        "data": serializer.data
    }, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_reserved_rooms(request):
    update_expired_reservation()
    # if request.user.role != 'admin':
    #     return Response({
    #         "message":"Permission Denied"
    #     }, status=status.HTTP_403_FORBIDDEN)
        
    reserved_rooms = RoomReservation.objects.all()
    serializer = RoomReservationSerializer(reserved_rooms, many=True)

    return Response({
        "message": "Reserved room fetched successfully",
        "data": serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def get_circulation_dashboard(request):
    query = CirculationQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    return Response(admin_analytics.circulation_dashboard(query.validated_data, timezone.now()))


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def get_inventory_dashboard(request):
    return Response(inventory_analytics.inventory_dashboard(timezone.now()))
  
@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdminRole])
def get_borrowers_dashboard(request):
    query = BorrowersQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    return Response(borrower_analytics.borrowers_dashboard(query.validated_data, timezone.now()))


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
