from json.decoder import JSONDecodeError

from django.utils import timezone
import requests
import re

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes

from library.recommender.preprocess import MAX_TAGS


def _description_text(raw_desc):
    # Open Library descriptions are either a string or {"type": ..., "value": ...}
    if isinstance(raw_desc, dict):
        raw_desc = raw_desc.get("value")
    return raw_desc.strip() if isinstance(raw_desc, str) else ""


# Create your views here.
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def autofillBookInfo(request):
    today = timezone.localtime().isoformat()
    isbn = request.query_params.get("isbn")

    if not isbn:
        return Response({"message":"ISBN is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        book_response = requests.get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data", timeout=5)
        book_response.raise_for_status()
    except requests.RequestException:
        return Response({"message":"External service error"}, status=status.HTTP_502_BAD_GATEWAY)

    try:
        data1 = book_response.json()
    except JSONDecodeError:
        return Response({"message" : "No book found"}, status=status.HTTP_404_NOT_FOUND)

    book_data = data1.get(f"ISBN:{isbn}")
    
    if not book_data: 
        return Response({"message" : "No book found"}, status=status.HTTP_404_NOT_FOUND)

    key = book_data.get("key", "")
    parts = key.split("/")
    workKey = parts[2] if len(parts) > 2 else None

    if not workKey:
        return Response({"message": "Invalid book data"}, status=status.HTTP_502_BAD_GATEWAY)
    try:
        work_response = requests.get(f"https://openlibrary.org/books/{workKey}.json", timeout=5)
        work_response.raise_for_status()
    except requests.RequestException:
        return Response({"message":"External service error"}, status=status.HTTP_502_BAD_GATEWAY)
    
    work_data = work_response.json()

    subjectNames = book_data.get("subjects") or []
    subjects = []
    for s in subjectNames:
        name = s["name"].strip()
        if name and name not in subjects:
            subjects.append(name)
    subjects = subjects[:MAX_TAGS]

    publishDate = book_data.get("publish_date") or ""

    # Format date
    yearPublished = re.sub(r"[^0-9]", "", publishDate)[-4:] or "Unknown"

    desc = ""
    works = work_data.get("works") or []
    works_key = works[0].get("key") if works and isinstance(works[0], dict) else None
    if isinstance(works_key, str) and re.fullmatch(r"/works/OL\d+W", works_key):
        try:
            works_response = requests.get(f"https://openlibrary.org{works_key}.json", timeout=5)
            works_response.raise_for_status()
            desc = _description_text(works_response.json().get("description"))
        except (requests.RequestException, ValueError, AttributeError):
            desc = ""
    if not desc:
        desc = _description_text(work_data.get("description"))

    # Format fields 
    title = book_data.get("title") or "Unknown"
    authors = book_data.get("authors") or []
    publishers = book_data.get("publishers") or []
    
    author = (
        authors[0]["name"]
        if authors
        else "Unknown"
    )
    publisher = (
        publishers[0]["name"]
        if publishers
        else "Unknown"
        
    )
    
    edition = work_data.get("edition_name") or "Unknown"
    pages = book_data.get("number_of_pages") or book_data.get("pagination") or "Unknown"
    cover_url = (
        f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg"
        if isbn else None
    )

    # Set book object
    book = {
        "title" : title,
        "author" : author,
        "edition" : edition,
        "description" : desc,
        "publisher" : publisher, 
        "year_published" : yearPublished,
        "date_acquired" : today,
        "pages" : pages,
        "tags" : subjects,
        "cover_url" : cover_url
        
    }

    return Response ({
        "message" : "book found",
        "book" : book,
    }, status=status.HTTP_200_OK)
