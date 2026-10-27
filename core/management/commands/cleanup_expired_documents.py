from django.core.management.base import BaseCommand
from core.services.document_cleanup import cleanup_expired_documents


class Command(BaseCommand):
    help = "Delete expired document-processing files"

    def handle(self, *args, **options):
        result = cleanup_expired_documents()

        self.stdout.write(
            self.style.SUCCESS(
                f"Cleanup complete: {result['deleted']} deleted, "
                f"{result['failed']} failed."
            )
        )