from django.core.management.base import BaseCommand, CommandError

from project.models import Project


class Command(BaseCommand):
    help = 'Update projects tags'

    def handle(self, *args, **options):
        try:
            Project.objects.flush_projects_tag()
        except Exception as e:
            raise CommandError(e)
        self.stdout.write(self.style.SUCCESS('Successfully.'))
