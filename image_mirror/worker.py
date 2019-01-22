from __future__ import absolute_import, unicode_literals
import os
import json
from celery import Celery
import docker
from docker.errors import DockerException

from project.models import Tag, Project
from image_mirror.settings import TARGET_REGISTRY_USERNAME, TARGET_REGISTRY_PASSWORD

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'image_mirror.settings')

app = Celery('image_mirror')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock')
docker.from_env()


class ImageError(Exception):
    error_id = "IMAGE_ERROR"

    def __init__(self, msg):
        self.error_msg = msg


class ImagePullError(ImageError):
    error_id = "IMAGE_PULL_ERROR"


class ImagePushError(ImageError):
    error_id = "IMAGE_PUSH_ERROR"


class ImageTagError(ImageError):
    error_id = "IMAGE_TAG_ERROR"


@app.task(bind=True, default_retry_delay=300, max_retries=3)
def sync_image(self, project_id, tag_id):
    tag = Tag.objects.get(tag_id=tag_id)
    project = Project.objects.get(project_id=project_id)
    tag.status = "syncing"
    tag.save()
    try:
        assert tag.project_id == project_id
        pull_image_from_source(project, tag)
        tag_image(project, tag)
        push_image_to_target(project, tag)
        tag.status = "synced"
    except ImageError as exc:
        tag.status = "error"
        tag.error_message = exc.error_msg
        self.retry(countdown=10, exc=exc)
    finally:
        tag.save()


def tag_image(project, tag):
    tag_name = tag.name or "latest"
    try:
        docker_client.api.tag(project.source_image, project.target_image, tag=tag_name)
    except DockerException as e:
        raise ImageTagError("Tag image error: {}".format(e))


def pull_image_from_source(project, tag):
    tag_name = tag.name or "latest"
    logs = []
    auth = {
        "username": TARGET_REGISTRY_USERNAME,
        "password": TARGET_REGISTRY_PASSWORD,
    }
    try:
        for line in docker_client.api.pull(project.source_image,
                                           tag=tag_name,
                                           auth_config=auth,
                                           stream=True,
                                           decode=True):
            logs.append(json.dumps(line, indent=4))
        for l in logs:
            if "error" in l:
                raise ImagePullError(logs)
    except DockerException as e:
        raise ImagePullError("Image pull error: {}".format(e))


def push_image_to_target(project, tag):
    tag_name = tag.name or "latest"
    logs = []
    try:
        for line in docker_client.api.push(project.target_image, tag=tag_name, stream=True, decode=True):
            logs.append(json.dumps(line, indent=4))
        for l in logs:
            if "error" in l:
                raise ImagePushError(logs)
    except DockerException as e:
        raise ImagePushError("Image push error: {}".format(e))
