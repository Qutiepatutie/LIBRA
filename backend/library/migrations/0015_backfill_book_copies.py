from django.db import migrations
from django.db.models import Exists, OuterRef, Subquery


def create_first_copies(apps, schema_editor):
    """Every existing book becomes a title with copy 1; every loan points at that copy."""
    db = schema_editor.connection.alias
    Books = apps.get_model('library', 'Books')
    BookCopy = apps.get_model('library', 'BookCopy')
    BorrowRecords = apps.get_model('library', 'BorrowRecords')

    # Accession stays blank: the library has not supplied barcodes for existing books.
    BookCopy.objects.using(db).bulk_create(
        (
            BookCopy(book_id=book_id, copy_number=1, accession_number='',
                     condition=condition, date_acquired=date_acquired, is_archived=False)
            for book_id, condition, date_acquired
            in Books.objects.using(db).values_list('pk', 'condition', 'date_acquired').iterator()
        ),
        batch_size=1000,
    )
    first_copy = BookCopy.objects.using(db).filter(book_id=OuterRef('book_id'), copy_number=1).values('pk')[:1]
    BorrowRecords.objects.using(db).update(copy_id=Subquery(first_copy))


def restore_book_fields(apps, schema_editor):
    """Put the lowest-numbered copy's details back on its title and relink loans to titles."""
    db = schema_editor.connection.alias
    Books = apps.get_model('library', 'Books')
    BookCopy = apps.get_model('library', 'BookCopy')
    BorrowRecords = apps.get_model('library', 'BorrowRecords')

    lowest = BookCopy.objects.using(db).filter(book_id=OuterRef('pk')).order_by('copy_number')
    # Titles without copies keep the defaults the reverse of 0016 gave them.
    Books.objects.using(db).filter(Exists(lowest)).update(
        condition=Subquery(lowest.values('condition')[:1]),
        date_acquired=Subquery(lowest.values('date_acquired')[:1]),
    )
    copy_book = BookCopy.objects.using(db).filter(pk=OuterRef('copy_id')).values('book_id')[:1]
    BorrowRecords.objects.using(db).update(book_id=Subquery(copy_book))


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0014_bookcopy'),
    ]

    operations = [
        migrations.RunPython(create_first_copies, restore_book_fields),
    ]
