from django.core.management.base import BaseCommand
from e_learning.services import QuizGradingService

class Command(BaseCommand):
    help = 'Bulk grade all ungraded short-answer quiz responses using AI.'

    def handle(self, *args, **options):
        self.stdout.write("Starting bulk grading process...")
        count = QuizGradingService.evaluate_bulk_attempts()
        self.stdout.write(self.style.SUCCESS(f"Successfully graded {count} short-answer responses."))
