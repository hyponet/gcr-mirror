import time
import logging
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

from common import utils
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


def registry_validate(registry_host):
    if not registry_host:
        raise ValidationError("registry host can not set null.")
    if not (str(registry_host).startswith("https://")
            or str(registry_host).startswith("http://")):
        raise ValidationError("registry host must start with http(s)://")

    gcr_client = GcrClient(registry_host)
    if not gcr_client.is_valid():
        raise ValidationError("registry host error.")


class NamespaceManager(models.Manager):
    def create_namespace(self, name, registry_host,
                         registry_username, registry_password):
        name = str(name).strip()
        registry_host = str(registry_host).strip()
        try:
            self.get(name=name, registry_host=registry_host)
            return
        except models.ObjectDoesNotExist:
            pass
        self.create(name=name, registry_host=registry_host,
                    registry_username=registry_username,
                    registry_password=registry_password)

    def flush_namespace_project(self):
        LOG.debug("Start namespace flush.")
        last_flush_at = int(time.time() - FLUSH_NAMESPACE_MAX_TIME)
        LOG.debug("Last flush at: {}".format(last_flush_at))
        _namespaces = self.filter(updated_at__lte=last_flush_at).all()
        for n in _namespaces:
            try:
                n.update_projects()
                # 防止 ban
                time.sleep(1)
            except Exception as e:
                LOG.error("Flush namespaces[{}] error: {}"
                          .format(n.id, e), exc_info=True)
        LOG.debug("Flush namespace finish.")


class Namespace(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=utils.gen_uuid)
    name = models.CharField(max_length=256, null=False, blank=False)

    # 源制品仓库
    registry_host = models.CharField(max_length=256, null=False, default="https://gcr.io",
                                     validators=[registry_validate])
    registry_username = models.CharField(max_length=256, null=True, blank=True)
    registry_password = models.CharField(max_length=128, null=True, blank=True)

    created_at = models.BigIntegerField(default=utils.get_time)
    updated_at = models.BigIntegerField(default=0)

    objects = NamespaceManager()

    def update_projects(self):
        registry_host = str(self.registry_host)

        gcr_client = GcrClient(registry_host)
        projects = gcr_client.get_project_by_namespace(self.name)
        for p in projects:
            name = "{namespace}-{project_name}" \
                .format(namespace=self.name, project_name=p)
            Project.objects.create_project_by_namespace(
                name, self, p)
        self.save()
        LOG.info("Updated namespace: {}".format(self.name))

    def save(self, *args, **kwargs):
        self.updated_at = int(time.time())
        super(Namespace, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        Project.objects.filter(namespace_id=self.id).delete()
        super(Namespace, self).delete(*args, **kwargs)

    @property
    def create_time(self):
        return utils.timestamp2datetime(self.created_at)

    @property
    def update_time(self):
        return utils.timestamp2datetime(self.updated_at)

    def __str__(self):
        return "Namespace [{}]".format(self.name)


class ProjectManager(models.Manager):

    def create_project(self, name, project_name, registry_host,
                       registry_namespace, registry_username, registry_password):
        name = str(name).strip()
        registry_host = str(registry_host).strip()
        try:
            self.get(name=name)
            return
        except models.ObjectDoesNotExist:
            pass
        self.create(name=name, project_name=project_name,
                    registry_host=registry_host,
                    registry_namespace=registry_namespace,
                    registry_username=registry_username,
                    registry_password=registry_password)

    def create_project_by_namespace(self, name, namespace, project_name):
        try:
            self.get(name=name)
            return
        except models.ObjectDoesNotExist:
            LOG.debug("Project[{}] not found, try create.".format(name))
        self.create(name=name, project_name=project_name,
                    namespace_id=namespace.id,
                    registry_host=namespace.registry_host,
                    registry_namespace=namespace.name,
                    registry_username=namespace.registry_username,
                    registry_password=namespace.registry_password)
        LOG.info("Created Project: {}".format(name))

    def flush_projects_tag(self):
        LOG.debug("Start project flush.")
        last_flush_at = int(time.time() - FLUSH_NAMESPACE_MAX_TIME)
        LOG.debug("Last flush at: {}".format(last_flush_at))
        _projects = self.filter(updated_at__lte=last_flush_at).all()
        for p in _projects:
            # 防止 ban
            time.sleep(1)
            p.update_project_tags()

        LOG.debug("Flush project finish.")

    def get_namespace_projects(self, namespace_id):
        return self.filter(namespace_id=namespace_id).all()


class Project(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=utils.gen_uuid)
    name = models.CharField(max_length=256, null=False, blank=False, unique=True)
    # 源 Registry 中的项目名
    project_name = models.CharField(max_length=256, null=False, blank=False)
    namespace_id = models.CharField(max_length=36, db_index=True, null=True, blank=True)

    # 需要同步的镜像
    source_image = models.CharField(max_length=256, null=False, blank=False, db_index=True)
    # 将镜像同步到哪去
    target_image = models.CharField(max_length=256, null=False, blank=False, db_index=True)

    # 源制品仓库
    registry_host = models.CharField(max_length=256, null=False, default="https://gcr.io",
                                     validators=[registry_validate])
    registry_namespace = models.CharField(max_length=128, null=False, blank=True, default="")
    registry_username = models.CharField(max_length=256, null=True, blank=True, default="")
    registry_password = models.CharField(max_length=128, null=True, blank=True, default="")

    created_at = models.BigIntegerField(default=utils.get_time)
    updated_at = models.BigIntegerField(default=0)

    objects = ProjectManager()

    def update_project_tags(self):
        gcr_client = GcrClient(self.registry_host)
        tags = gcr_client.get_project_tags(
            self.project_name, namespace=self.registry_namespace or None)
        for t in tags:
            Tag.objects.create_tag_by_project(self, t)
        try:
            latest = Tag.objects.get(project_id=self.id, name="latest")
            latest.status = "pending"
            latest.save()
        except models.ObjectDoesNotExist:
            pass
        self.save()
        LOG.info("Updated project: {}".format(self.name))

    def save(self, *args, **kwargs):
        _, registry = str(self.registry_host).split("//")
        if self.registry_namespace:
            source_image = "{registry}/{namespace}/{project_name}" \
                .format(registry=registry, namespace=self.registry_namespace,
                        project_name=self.project_name)
        else:
            source_image = "{registry}/{project_name}" \
                .format(registry=registry, project_name=self.project_name)
        target_image = "{registry}/{namespace}/{project_name}" \
            .format(registry=TARGET_REGISTRY_URL,
                    namespace=TARGET_REGISTRY_NAMESPACE,
                    project_name=self.name)
        if (self.source_image and self.source_image != source_image) \
                or (self.target_image and self.target_image != target_image):
            # 更换名称，Tag 删掉重新同步
            Tag.objects.filter(project_id=self.id).delete()

        self.source_image = source_image
        self.target_image = target_image

        self.updated_at = int(time.time())
        super(Project, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        Tag.objects.filter(project_id=self.id).delete()
        super(Project, self).delete(*args, **kwargs)

    @property
    def tag_count(self):
        return Tag.objects.filter(project_id=self.id).count()

    @property
    def create_time(self):
        return utils.timestamp2datetime(self.created_at)

    @property
    def update_time(self):
        return utils.timestamp2datetime(self.updated_at)

    def __str__(self):
        return "Project [{}]".format(self.name)


class TagManager(models.Manager):
    def create_tag_by_project(self, project, name):
        image_url = "{}:{}".format(project.target_image, name)
        try:
            tag = self.get(project_id=project.id, name=name)
            tag.image_url = image_url
            tag.save()
            return
        except models.ObjectDoesNotExist:
            LOG.debug("Tag[{}] not found in Project {}, try create.".format(name, project.name))

        self.create(name=name, project_id=project.id, image_url=image_url)
        LOG.info("Created Tag: {}:{}".format(project.name, name))

    def retry_migrate_tasks(self):
        tags = self.filter(status="error").all()
        count = 0
        for t in tags:
            t.status = "pending"
            t.save()
            t.migrate()
            count += 1
        LOG.info("Finish send {} SYNC error task to Worker".format(count))

    def migrate_project_images(self, project_id):
        tags = self.filter(project_id=project_id) \
                   .exclude(status="synced").all()[:MAX_MIGRATE_TASK_PRE_PROJECT]
        count = 0
        for t in tags:
            t.migrate()
            count += 1
        LOG.info("Finish send {} SYNC Project[{}] task to Worker".format(count, project_id))


class Tag(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=utils.gen_uuid)
    name = models.CharField(max_length=256, null=False, blank=False)

    project_id = models.CharField(max_length=36, null=False, blank=False, db_index=True)
    # 全量的 image 地址 target_image:tag_name
    image_url = models.CharField(max_length=256, null=False, blank=True, default="")

    status = models.CharField(max_length=128, db_index=True,
                              choices=PROJECT_TAG_STATUS, default="pending")
    error_message = models.TextField()

    created_at = models.BigIntegerField(default=utils.get_time)
    updated_at = models.BigIntegerField(default=utils.get_time)

    objects = TagManager()

    def migrate(self):
        if self.status == "synced":
            return

        from worker import sync_image
        sync_image.delay(self.project_id, self.id)

    def save(self, *args, **kwargs):
        self.updated_at = int(time.time())
        super(Tag, self).save(*args, **kwargs)

    @property
    def create_time(self):
        return utils.timestamp2datetime(self.created_at)

    @property
    def update_time(self):
        return utils.timestamp2datetime(self.updated_at)

    @property
    def project(self):
        try:
            return Project.objects.get(id=self.project_id)
        except models.ObjectDoesNotExist:
            return None

    def __str__(self):
        return "Tag [{}]".format(self.name)
