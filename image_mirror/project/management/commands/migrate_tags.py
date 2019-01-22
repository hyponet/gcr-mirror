from django.core.management.base import BaseCommand, CommandError

from project.models import Project, Tag


class Command(BaseCommand):
    help = 'Reload sync source config.'

    def handle(self, *args, **options):
        all_projects = Project.objects.all()
        for p in all_projects:
            Tag.objects.migrate_project_images(p.id)
            self.stdout.write(self.style.NOTICE(
                'send project[{}] task finish.'.format(p.name)))
        self.stdout.write(self.style.SUCCESS('Successfully.'))
