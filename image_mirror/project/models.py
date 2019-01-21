import uuid
import time
from django.db import models

PROJECT_TAG_STATUS = [
    ("pending", "等待同步"),
    ("syncing", "正在同步"),
    ("synced", "同步完成"),
    ("error", "异常"),
]


class Namespace(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = models.CharField(max_length=256, null=False, blank=False)

    # 源制品仓库
    registry_host = models.CharField(max_length=256, null=False, blank=False)
    registry_username = models.CharField(max_length=256, null=True)
    registry_password = models.CharField(max_length=128, null=True)

    created_at = models.BigIntegerField(default=lambda: int(time.time()))
    updated_at = models.BigIntegerField(default=lambda: int(time.time()))


class Project(models.Model):
    id = models.CharField(max_length=36, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = models.CharField(max_length=256, null=False, blank=False, unique=True)

    # 需要同步的镜像
    source_image = models.CharField(max_length=256, null=False, blank=False, db_index=True)
    # 将镜像同步到哪去
    target_image = models.CharField(max_length=256, null=False, blank=False, db_index=True)

    # 源制品仓库
    registry_host = models.CharField(max_length=256, null=False, blank=False)
    registry_namespace = models.CharField(max_length=128, null=False, blank=True)
    registry_username = models.CharField(max_length=256, null=True)
    registry_password = models.CharField(max_length=128, null=True)

    created_at = models.BigIntegerField(default=lambda: int(time.time()))
    updated_at = models.BigIntegerField(default=lambda: int(time.time()))


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
