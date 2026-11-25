from django.core.management.base import BaseCommand

from library.recommender.build import rebuild_recommendations


class Command(BaseCommand):
    help = "Rebuild the stored TF-IDF book recommendations."

    def handle(self, *args, **options):
        stats = rebuild_recommendations()
        self.stdout.write(
            f"items={stats.items} works={stats.works} vocabulary={stats.vocabulary} "
            f"pairs={stats.pairs} seconds={stats.seconds:.2f}"
        )
