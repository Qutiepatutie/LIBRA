from django.core.management.base import BaseCommand, CommandError

from library.recommender.evaluation import explain_pair


class Command(BaseCommand):
    help = "Explain one recommendation pair term by term."

    def add_arguments(self, parser):
        parser.add_argument("book_id", type=int)
        parser.add_argument("candidate_id", type=int)

    def handle(self, *args, **options):
        try:
            result = explain_pair(options["book_id"], options["candidate_id"])
        except ValueError as error:
            raise CommandError(str(error))
        for t in result["terms"]:
            self.stdout.write(
                f"{t['term']}: tf_a={t['tf_a']} tf_b={t['tf_b']} idf={t['idf']:.4f} "
                f"tfidf_a={t['tfidf_a']:.4f} tfidf_b={t['tfidf_b']:.4f} "
                f"w_a={t['weight_a']:.4f} w_b={t['weight_b']:.4f} contribution={t['contribution']:.4f}")
        self.stdout.write(f"norm_a = {result['norm_a']:.4f}  norm_b = {result['norm_b']:.4f}")
        self.stdout.write(f"TOTAL SCORE = {result['score']:.4f}")
