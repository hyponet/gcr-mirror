from django.core.management.base import BaseCommand, CommandError

from project.models import Project, Tag


class Command(BaseCommand):
    help = 'Retry error sync task.'

    def handle(self, *args, **options):
        Tag.objects.retry_migrate_tasks()
        self.stdout.write(self.style.SUCCESS('Successfully.'))
