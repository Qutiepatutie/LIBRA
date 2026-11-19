import csv
import io
from django.views.decorators.csrf import csrf_exempt
from .permissions import IsAdminRole
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError
from django.db.models import Exists, F, OuterRef, Prefetch

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.pagination import PageNumberPagination

from .models import BookCopy, Books, BorrowRecords, UserProfile, RoomReservation, StatusChoices, ItemType
from .serializers import AllBorrowRecordSerializer, UserBorrowRecordSerializer, BooksSerializer, AddBooksSerializer, RoomReservationSerializer
from .serializers import CopyFieldsSerializer, CopyRefSerializer, CopySerializer
from .serializers import DashboardLoanSerializer, DashboardPageQuerySerializer, CirculationQuerySerializer, BorrowersQuerySerializer
from .copies import HOLD_STATUSES, assign_copy, available_copies, next_copy_number, with_copy_counts
from . import admin_analytics, inventory_analytics, borrower_analytics, user_analytics
from .image_upload import upload_book_cover,delete_book_cover

COPY_FIELDS = ("accession_number", "condition", "date_acquired")

def with_availability(copies_qs):
    """Annotate is_available from the single rule in copies.py, so listing copies costs no query per copy."""
    return copies_qs.annotate(is_available=Exists(available_copies().filter(pk=OuterRef("pk"))))

def _copy_payload(copy):
    return CopySerializer(with_availability(BookCopy.objects.filter(pk=copy.pk)).get()).data

def _copy_fields(request):
    # A null means "not given", so the model default applies instead of "Invalid condition".
    return {field: request.data[field] for field in COPY_FIELDS if request.data.get(field) is not None}

def _first_error(serializer):
    first_errors = next(iter(serializer.errors.values()))
    return Response({"message": first_errors[0], "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

def _accession_taken():
    return Response({"message": "Accession number already exists"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_books(request):
    listed = with_availability(BookCopy.objects.filter(is_archived=False)).order_by("copy_number")
    books = with_copy_counts(Books.objects.filter(is_archived=False)).prefetch_related(
        Prefetch("copies", queryset=listed, to_attr="listed_copies"),
    )

    serializer = BooksSerializer(books, many=True)
    return Response({"data": serializer.data}, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def add_books(request):
    call_number = request.data.get("call_number")
    isbn = request.data.get("isbn")
    title = request.data.get("title")
    author = request.data.get("author")

    # ISBN is optional for theses; AddBooksSerializer requires it for books.
    if not all([call_number, title, author]):
        return Response({'message': 'Missing important fields'}, status=status.HTTP_400_BAD_REQUEST)

    book = Books.objects.filter(call_number=call_number, isbn=isbn).first()

    if book:
        if book.is_archived:
            book.is_archived = False
            book.save(update_fields=["is_archived"])

            return Response({'message':'Book Successfully Added!'}, status=status.HTTP_200_OK)
            
        return Response({'message': 'Book already exists'}, status=status.HTTP_400_BAD_REQUEST)

    data = request.data.copy()
    data.pop("cover_image", None)

    provided_cover_url = data.get("cover_url")

    serializer = AddBooksSerializer(data=data)
    
    if not serializer.is_valid():
        return _first_error(serializer)

    copy_serializer = CopyFieldsSerializer(data=_copy_fields(request))

    if not copy_serializer.is_valid():
        return _first_error(copy_serializer)

    image = request.FILES.get("cover_image")
    cover_url = provided_cover_url
    cover_path = None

    if image:
        try:
            cover_url, cover_path = upload_book_cover(image)
        except ValidationError as err:
            return Response(
                {"message": str(err)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception:
            return Response(
                {"message": "Failed to upload book cover"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
    # A title is never stored without its first copy.
    try:
        with transaction.atomic():
            book = serializer.save(cover_url=cover_url)
            copy_serializer.save(book=book, copy_number=1)
    except IntegrityError:
        if cover_path:
            delete_book_cover(cover_path)
        
        # Another request took the ISBN, call number or accession number after validation.
        return Response({'message': 'Book already exists'}, status=status.HTTP_400_BAD_REQUEST)

    except Exception:
        if cover_path:
            delete_book_cover(cover_path)

        raise

    return Response({'message':'Book Successfully Added!'}, status=status.HTTP_201_CREATED)

def _requested_id(request, key):
    try:
        return int(request.data.get(key))
    except (TypeError, ValueError):
        return None

def _requested_book_id(request):
    """Items are identified by primary key: theses may lack an ISBN and call numbers can be edited."""
    return _requested_id(request, "book_id")

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

    # Title fields only: condition and acquisition date belong to a copy (editCopy/).
    item_type = request.data.get("itemType", book.item_type)
    if item_type not in ItemType.values:
        return Response({"message":"Invalid item type"}, status=status.HTTP_400_BAD_REQUEST)

    book.description = request.data.get("description", book.description)
    book.title = request.data.get("title", book.title)
    book.author = request.data.get("author", book.author)
    book.call_number = new_call_number or book.call_number
    book.pages = request.data.get("pages", book.pages)
    book.publisher = request.data.get("publisher", book.publisher)
    book.year_published = request.data.get("year_published", book.year_published)
    book.tags = request.data.get("tags", book.tags)
    book.item_type = item_type

    book.save()

    return Response ({"message":"Book Successfully Edited"}, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def remove_book(request):
    book_id = _requested_book_id(request)

    if book_id is None:
        return _missing_book_id()

    try:
        book = Books.objects.get(pk=book_id)
    except Books.DoesNotExist:
        return Response({"message":"Book not found"}, status=status.HTTP_404_NOT_FOUND)

    book.is_archived = True
    book.save(update_fields=["is_archived"])

    return Response({"message":"Book successfully removed"}, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdminRole])
def add_copy(request):
    book_id = _requested_book_id(request)

    if book_id is None:
        return _missing_book_id()

    try:
        with transaction.atomic():
            # Lock the title so two concurrent adds cannot both take the same next copy number.
            book = Books.objects.select_for_update().filter(pk=book_id).first()
            if book is None:
                return Response({"message":"Book not found"}, status=status.HTTP_404_NOT_FOUND)
            if book.is_archived:
                return Response({"message":"Book is archived"}, status=status.HTTP_400_BAD_REQUEST)

            serializer = CopyFieldsSerializer(data=_copy_fields(request))
            if not serializer.is_valid():
                return _first_error(serializer)

            copy = serializer.save(book=book, copy_number=next_copy_number(book))
    except IntegrityError:
        return _accession_taken()

    return Response({"message":"Copy added", "copy":_copy_payload(copy)}, status=status.HTTP_201_CREATED)

def _requested_copy(request):
    """Return (copy, error response)."""
    copy_id = _requested_id(request, "copy_id")
    if copy_id is None:
        return None, Response({"message":"Missing copy_id"}, status=status.HTTP_400_BAD_REQUEST)

    copy = BookCopy.objects.filter(pk=copy_id).first()
    if copy is None:
        return None, Response({"message":"Copy not found"}, status=status.HTTP_404_NOT_FOUND)
    return copy, None

@api_view(["PUT"])
@permission_classes([IsAuthenticated, IsAdminRole])
def edit_copy(request):
    copy, error = _requested_copy(request)
    if error:
        return error

    serializer = CopyFieldsSerializer(copy, data=_copy_fields(request), partial=True)
    if not serializer.is_valid():
        return _first_error(serializer)

    try:
        with transaction.atomic():
            serializer.save()
    except IntegrityError:
        return _accession_taken()

    return Response({"message":"Copy successfully edited", "copy":_copy_payload(copy)}, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdminRole])
def remove_copy(request):
    copy, error = _requested_copy(request)
    if error:
        return error

    with transaction.atomic():
        # The same title lock as assign_copy, so a borrow cannot take this copy between check and archive.
        Books.objects.select_for_update().filter(pk=copy.book_id).first()
        if copy.loans.filter(status__in=HOLD_STATUSES).exists():
            return Response({"message":"Copy is on loan"}, status=status.HTTP_400_BAD_REQUEST)

        # Archived, not deleted, so its loan history survives.
        copy.is_archived = True
        copy.save(update_fields=["is_archived"])

    return Response({"message":"Copy successfully removed"}, status=status.HTTP_200_OK)

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

    with transaction.atomic():
        # Lock the title first so a double submit cannot pass the per-user check twice.
        book = Books.objects.select_for_update().filter(pk=book_id).first()
        if book is None:
            return Response({"message":"Book not found"}, status=status.HTTP_404_NOT_FOUND)

        if book.is_archived:
            return Response({"message":"Book is archived and cannot be borrowed"}, status=status.HTTP_400_BAD_REQUEST)

        if BorrowRecords.objects.filter(user=user, copy__book=book, status__in=HOLD_STATUSES).exists():
            return Response({"message":"You already have a request or loan for this book"}, status=status.HTTP_400_BAD_REQUEST)

        copy = assign_copy(book)
        if copy is None:
            return Response({"message":"All copies are currently borrowed"}, status=status.HTTP_400_BAD_REQUEST)

        loan = BorrowRecords.objects.create(
            status = StatusChoices.PENDING,
            user = user,
            copy = copy
        )

    return Response({
        "message":"Book successfully borrowed",
        "loan_id": loan.pk,
        "copy": CopyRefSerializer(copy).data,
    }, status=status.HTTP_200_OK)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def get_user_borrowed_books(request):
    id_number = request.data.get("id")

    try:
        user = UserProfile.objects.get(id_number=id_number)
    except UserProfile.DoesNotExist:
        return Response({"message":"User not found"}, status=status.HTTP_404_NOT_FOUND)

    borrowed_books = BorrowRecords.objects.filter(user=user, return_date__isnull=True).select_related("copy__book")
    serializer = UserBorrowRecordSerializer(borrowed_books, many=True)

    return Response({"books": serializer.data}, status=status.HTTP_200_OK)

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_all_borrowed_books(request):
    records = BorrowRecords.objects.filter(user__user__isnull=False).select_related("user__user", "copy__book")
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
        ).select_related("user__user", "copy__book")

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
            # Copy fields, appended so existing column positions do not move
            'Copy Number',
            'Accession Number',
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
                # Copy fields
                r.copy.copy_number,
                r.copy.accession_number,
            ])
        current_date = timezone.now().strftime('%Y_%m_%d_%H%M')
        response = HttpResponse(buffer.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="borrowed_books_{current_date}.csv"'
        return response

    except Exception as e:
        return JsonResponse({"status": "failed", "message": "CSV export failed", "error": str(e)})

def _requested_loan_id(request):
    """Several borrowers can hold copies of one title, so a loan is identified by its own id."""
    return _requested_id(request, "loan_id")

def _missing_loan_id():
    return Response({"message": "Missing loan_id"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def accept_borrowed_book(request):
    loan_id = _requested_loan_id(request)
    if loan_id is None:
        return _missing_loan_id()

    # Only a pending request can be accepted; cancelled ones also have no return date.
    book_record = BorrowRecords.objects.filter(pk=loan_id, status=StatusChoices.PENDING).first()
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
    loan_id = _requested_loan_id(request)
    if loan_id is None:
        return _missing_loan_id()

    book = BorrowRecords.objects.filter(
        pk=loan_id,
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
    loan_id = _requested_loan_id(request)
    if loan_id is None:
        return _missing_loan_id()

    book = BorrowRecords.objects.filter(
        pk=loan_id,
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
    loans = loans.select_related('copy__book', 'fine').order_by(F('borrow_date').desc(nulls_last=True), '-pk')
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
