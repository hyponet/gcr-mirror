from django.core.management.base import BaseCommand, CommandError

from project.models import Namespace


class Command(BaseCommand):
    help = 'Update namespace project.'

    def handle(self, *args, **options):
        try:
            Namespace.objects.flush_namespace_project()
        except Exception as e:
            raise CommandError(e)
        self.stdout.write(self.style.SUCCESS('Successfully.'))
