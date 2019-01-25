from __future__ import absolute_import, unicode_literals
import time
import docker
from docker.errors import DockerException
from django.conf import settings
import logging

from project.models import Tag, Project, models
from image_mirror.celery import app as celery_app

DOCKER_SOCK = "unix://var/run/docker.sock"
docker_client = docker.DockerClient(base_url=DOCKER_SOCK)
LOG = logging.getLogger(__name__)
TASK_RETRY_DELAY_TIME = 60


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


@celery_app.task(bind=True, default_retry_delay=TASK_RETRY_DELAY_TIME, max_retries=10)
def sync_image(self, project_id, tag_id):
    try:
        project = Project.objects.get(id=project_id)
        tag = Tag.objects.get(id=tag_id, project_id=project_id)
    except models.ObjectDoesNotExist as e:
        LOG.error(e, exc_info=True)
        return
    try_time = 50
    tag.status = "syncing"
    tag.save()
    try:
        while True:
            try:
                try_time -= 1
                time.sleep(TASK_RETRY_DELAY_TIME)
                pull_image_from_source(project, tag)
                tag_image(project, tag)
                push_image_to_target(project, tag)
                tag.status = "synced"
                LOG.info("Project {} Tag {} synced".format(project.name, tag.name))
                break
            except Exception as e:
                if try_time:
                    continue
                raise e
    except ImageError as exc:
        tag.status = "error"
        tag.error_message = exc.error_msg
        self.retry(countdown=TASK_RETRY_DELAY_TIME, exc=exc)
    finally:
        tag.save()


def tag_image(project, tag):
    tag_name = tag.name or "latest"
    image_url = "{}:{}".format(project.source_image, tag_name)
    try:
        docker_client.api.tag(image_url, project.target_image, tag=tag_name)
    except DockerException as e:
        raise ImageTagError("Tag image error: {}".format(e))


def pull_image_from_source(project, tag):
    tag_name = tag.name or "latest"
    image_url = "{}:{}".format(project.source_image, tag_name)
    LOG.info("Pull image: {}".format(image_url))
    try:
        for line in docker_client.api.pull(image_url, stream=True):
            if isinstance(line, bytes):
                line = line.decode()
            LOG.debug(line)
            if "error" in line:
                raise ImagePullError("Pull image {} get error log: {}".format(image_url, line))
    except Exception as e:
        raise ImagePullError("Image {} pull error: {}".format(image_url, e))


def push_image_to_target(project, tag):
    tag_name = tag.name or "latest"
    auth = {
        "username": settings.TARGET_REGISTRY_USERNAME,
        "password": settings.TARGET_REGISTRY_PASSWORD,
    }
    image_url = "{}:{}".format(project.target_image, tag_name)
    LOG.info("Push image: {}".format(image_url))
    try:
        for line in docker_client.api.push(image_url, auth_config=auth, stream=True):
            if isinstance(line, bytes):
                line = line.decode()
            LOG.debug(line)
            if "error" in line:
                raise ImagePushError("Push image {} get error log: {}".format(image_url, line))
    except Exception as e:
        raise ImagePushError("Image {} push error: {}".format(image_url, e))
    tag.image_url = image_url
