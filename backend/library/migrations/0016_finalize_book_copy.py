from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0015_backfill_book_copies'),
    ]

    operations = [
        migrations.AlterField(
            model_name='borrowrecords',
            name='copy',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='loans', to='library.bookcopy'),
        ),
        migrations.RemoveField(
            model_name='borrowrecords',
            name='book',
        ),
        migrations.RemoveField(
            model_name='books',
            name='condition',
        ),
        migrations.RemoveField(
            model_name='books',
            name='date_acquired',
        ),
        migrations.AddConstraint(
            model_name='borrowrecords',
            constraint=models.UniqueConstraint(condition=models.Q(('status__in', ['Pending', 'Active', 'Due', 'Overdue'])), fields=('copy',), name='loan_one_open_per_copy'),
        ),
    ]
