from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0013_books_is_archived'),
    ]

    operations = [
        migrations.CreateModel(
            name='BookCopy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('copy_number', models.PositiveIntegerField()),
                ('accession_number', models.CharField(blank=True, max_length=50)),
                ('condition', models.CharField(choices=[('good', 'Good'), ('lost', 'Lost'), ('damaged', 'Damaged')], default='good', max_length=20)),
                ('date_acquired', models.CharField(blank=True, max_length=100)),
                ('is_archived', models.BooleanField(default=False)),
                ('book', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='copies', to='library.books')),
            ],
            options={
                'db_table': 'book_copies',
                'constraints': [
                    models.UniqueConstraint(fields=('book', 'copy_number'), name='book_copy_number_unique'),
                    models.UniqueConstraint(condition=models.Q(('accession_number', ''), _negated=True), fields=('accession_number',), name='book_copy_accession_unique_nonblank'),
                ],
            },
        ),
        # Both loan links stay nullable until the backfill has filled copy (and, on the way back, book).
        migrations.AddField(
            model_name='borrowrecords',
            name='copy',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='loans', to='library.bookcopy'),
        ),
        migrations.AlterField(
            model_name='borrowrecords',
            name='book',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='library.books'),
        ),
    ]
