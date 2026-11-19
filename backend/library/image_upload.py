import uuid
from django.core.exceptions import ValidationError
from .supabase_client import supabase

def upload_book_cover(image):
    allowed_types={
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp"}

    if image.content_type not in allowed_types:
        raise ValidationError("Only JPG, PNG, and WEBP images are allowed")

    if image.size > 5 * 1024 * 1024:
        raise ValidationError("Image must not exceed 5 MB")

    extension = allowed_types[image.content_type]
    file_path = f"covers/{uuid.uuid4()}.{extension}"

    supabase.storage.from_("book-covers").upload(
        path=file_path,
        file=image.read(),
        file_options={
            "content-type": image.content_type,
            "upsert": "false"
        }
    )

    cover_url = supabase.storage.from_("book-covers").get_public_url(file_path)

    return cover_url, file_path

def delete_book_cover(file_path):
    supabase.storage.from_("book-covers").remove([file_path])