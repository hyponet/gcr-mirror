import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from project.models import Namespace, Project


class Command(BaseCommand):
    help = 'Reload sync source config.'

    def handle(self, *args, **options):
        config_path = settings.TARGET_CONFIG_FILE
        try:
            with open(config_path, "r") as f:
                payload = f.read()
            content = yaml.load(payload)
        except OSError as e:
            raise CommandError(
                'Can not get config file: {}.'.format(e))
        except ValueError as e:
            raise CommandError(
                'Load config file error: {}.'.format(e))
        namespaces = content.get("namespaces", {})
        projects = content.get("projects", {})
        try:
            for p_name, project in projects.items():
                Project.objects.create_project(
                    name=p_name,
                    project_name=project['project_name'],
                    registry_host=project['registry_host'],
                    registry_namespace=project.get("registry_namespace", ""),
                    registry_username=project.get("registry_username", ""),
                    registry_password=project.get("registry_password", ""),
                )

            for n_name, namespace in namespaces.items():
                if namespace['registry_host'] != "https://gcr.io":
                    raise CommandError("Do not support others.")
                Namespace.objects.create_namespace(
                    name=n_name,
                    registry_host=namespace['registry_host'],
                    registry_username=namespace.get("registry_username", ""),
                    registry_password=namespace.get("registry_password", ""),
                )
        except KeyError as e:
            raise CommandError("Config error, miss key: {}".format(e))

        self.stdout.write(self.style.SUCCESS('Load config successfully.'))
