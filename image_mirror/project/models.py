import uuid
import time
import logging
from django.db import models
from django.conf import settings

from common.registry_client import GcrClient

LOG = logging.getLogger(__name__)
FLUSH_NAMESPACE_MAX_TIME = settings.FLUSH_NAMESPACE_MAX_TIME
FLUSH_PROJECT_MAX_TIME = settings.FLUSH_PROJECT_MAX_TIME
MAX_MIGRATE_TASK_PRE_PROJECT = settings.MAX_MIGRATE_TASK_PRE_PROJECT
TARGET_REGISTRY_URL = settings.TARGET_REGISTRY_URL
TARGET_REGISTRY_NAMESPACE = settings.TARGET_REGISTRY_NAMESPACE
PROJECT_TAG_STATUS = [
    ("pending", "等待同步"),
    ("syncing", "正在同步"),
    ("synced", "同步完成"),
    ("error", "异常"),
]


class NamespaceManager(models.Manager):
    def flush_namespace_project(self):
        LOG.debug("Start namespace flush.")
        last_flush_at = int(time.time() - FLUSH_NAMESPACE_MAX_TIME)
        LOG.debug("Last flush at: {}".format(last_flush_at))
        _namespaces = self.filter(updated_at__lte=last_flush_at).all()
        for n in _namespaces:
            try:
                n.update_projects()
            except Exception as e:
                LOG.error("Flush namespaces[{}] error: {}"
                          .format(n.id, e), exc_info=True)
        LOG.debug("Flush namespace finish.")


class Namespace(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = models.CharField(max_length=256, null=False, blank=False)

    # 源制品仓库
    registry_host = models.CharField(max_length=256, null=False,
                                     blank=False, default="https://gcr.io")
    registry_username = models.CharField(max_length=256, null=True)
    registry_password = models.CharField(max_length=128, null=True)

    created_at = models.BigIntegerField(default=lambda: int(time.time()))
    updated_at = models.BigIntegerField(default=0)

    objects = NamespaceManager()

    def update_projects(self):
        registry_host = str(self.registry_host)
        if registry_host.startswith("http"):
            _, registry = registry_host.split("//")
        else:
            raise ValueError("registry_host error: {}".format(registry_host))

        gcr_client = GcrClient(registry_host)
        projects = gcr_client.get_project_by_namespace(self.name)
        for p in projects:
            name = "{namespace}-{project_name}" \
                .format(namespace=self.name, project_name=p)
            source_image = "{registry}/{namespace}/{project_name}" \
                .format(registry=registry, namespace=self.name, project_name=p)
            target_image = "{registry}/{namespace}/{project_name}" \
                .format(registry=TARGET_REGISTRY_URL,
                        namespace=TARGET_REGISTRY_NAMESPACE,
                        project_name=name)
            Project.objects.create_project_by_namespace(
                name, self, p, source_image, target_image)
        self.updated_at = int(time.time())
        self.save()
        LOG.info("Updated namespace: {}".format(self.name))


class ProjectManager(models.Manager):

    def create_project_by_namespace(self, name, namespace, project_name, source_image, target_image):
        try:
            project = self.filter(name=name).first()
            if project:
                LOG.debug("Project[{}] existed, skip.".format(name))
                return
        except models.ObjectDoesNotExist:
            LOG.debug("Project[{}] not found, try create.".format(name))
        self.create(name=name, project_name=project_name,
                    namespace_id=namespace.id,
                    registry_host=namespace.registry_host,
                    registry_namespace=namespace.name,
                    registry_username=namespace.registry_username,
                    registry_password=namespace.registry_password,
                    source_image=source_image, target_image=target_image)
        LOG.info("Created Project: {} to {}".format(source_image, target_image))

    def flush_projects_tag(self):
        LOG.debug("Start project flush.")
        last_flush_at = int(time.time() - FLUSH_NAMESPACE_MAX_TIME)
        LOG.debug("Last flush at: {}".format(last_flush_at))
        _projects = self.filter(updated_at__lte=last_flush_at).all()
        for p in _projects:
            p.update_project_tags()

        LOG.debug("Flush project finish.")

    def get_namespace_projects(self, namespace_id):
        return self.filter(namespace_id=namespace_id).all()


class Project(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = models.CharField(max_length=256, null=False, blank=False, unique=True)
    # 源 Registry 中的项目名
    project_name = models.CharField(max_length=256, null=False, blank=False, unique=True)
    namespace_id = models.CharField(max_length=36, db_index=True, null=True)

    # 需要同步的镜像
    source_image = models.CharField(max_length=256, null=False, blank=False, db_index=True)
    # 将镜像同步到哪去
    target_image = models.CharField(max_length=256, null=False, blank=False, db_index=True)

    # 源制品仓库
    registry_host = models.CharField(max_length=256, null=False,
                                     default="https://gcr.io", blank=False)
    registry_namespace = models.CharField(max_length=128, null=False, blank=True, default="")
    registry_username = models.CharField(max_length=256, null=True)
    registry_password = models.CharField(max_length=128, null=True)

    created_at = models.BigIntegerField(default=lambda: int(time.time()))
    updated_at = models.BigIntegerField(default=0)

    objects = ProjectManager()

    def update_project_tags(self):
        gcr_client = GcrClient(self.registry_host)
        tags = gcr_client.get_project_tags(
            self.project_name, namespace=self.registry_namespace or None)
        for t in tags:
            Tag.objects.create_tag_by_project(self, t)
        self.updated_at = int(time.time())
        self.save()
        LOG.info("Updated project: {}".format(self.name))


class TagManager(models.Manager):
    def create_tag_by_project(self, project, name):
        try:
            tag = self.filter(project_id=project.id, name=name).first()
            if tag:
                LOG.debug("Tag[{}] existed in Project {}, skip.".format(name, project.name))
                return
        except models.ObjectDoesNotExist:
            LOG.debug("Tag[{}] not found in Project {}, try create.".format(name, project.name))

        self.create(name=name, project_id=project.id)
        LOG.info("Created Tag: {}:{}".format(project.name, name))

    def migrate_project_images(self, project_id):
        tags = self.filter(project_id=project_id) \
                   .exclude(status="synced").all()[:MAX_MIGRATE_TASK_PRE_PROJECT]
        count = 0
        for t in tags:
            t.migrate()
            count += 1
        LOG.info("Finish send {} SYNC Project[{}] task to Worker".format(count, project_id))


class Tag(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = models.CharField(max_length=256, null=False, blank=False)

    project_id = models.CharField(max_length=36, null=False, blank=False, db_index=True)
    # 全量的 image 地址 target_image:tag_name
    image_url = models.CharField(max_length=256, null=False, blank=True, default="")

    status = models.CharField(max_length=128, db_index=True,
                              choices=PROJECT_TAG_STATUS, default="pending")
    error_message = models.TextField()

    created_at = models.BigIntegerField(default=lambda: int(time.time()))
    updated_at = models.BigIntegerField(default=lambda: int(time.time()))

    objects = TagManager()

    def migrate(self):
        if self.status == "synced":
            return

        # TODO 调用 Worker 的方法
