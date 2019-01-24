import threading
import logging
from django.contrib import admin

from .models import Namespace, Project, Tag

LOG = logging.getLogger(__name__)


def flush_namespace(modeladmin, request, queryset):
    def _async_flush(namespaces):
        for n in namespaces:
            try:
                n.update_projects()
            except Exception as e:
                LOG.error(e, exec_info=True)

    _namespaces = queryset.all()
    threading.Thread(target=_async_flush, args=(_namespaces,)).start()


def flush_project(modeladmin, request, queryset):
    def _async_flush(projects):
        for p in projects:
            try:
                p.update_project_tags()
            except Exception as e:
                LOG.error(e, exec_info=True)

    _projects = queryset.all()
    threading.Thread(target=_async_flush, args=(_projects,)).start()


def try_migrate_image(modeladmin, request, queryset):
    def _async_flush(tags):
        for t in tags:
            try:
                t.migrate()
            except Exception as e:
                LOG.error(e, exec_info=True)

    _tags = queryset.all()
    threading.Thread(target=_async_flush, args=(_tags,)).start()


flush_namespace.short_description = "Flush selected namespace projects"
flush_project.short_description = "Flush selected project tags"
try_migrate_image.short_description = "Try send migrate task to worker"


class NamespaceAdmin(admin.ModelAdmin):
    fieldsets = (
        ["基本信息", {"fields": ("id", ("create_time", "update_time"))}],
        ["名称", {"fields": ("name",)}],
        ["镜像仓库", {
            "fields":
                ("registry_host", ("registry_username", "registry_password"))
        }],
    )
    readonly_fields = ["id", "create_time", "update_time"]
    list_display = ["id", "name", "registry_host", "update_time"]
    actions = [flush_namespace]


class ProjectAdmin(admin.ModelAdmin):
    fieldsets = (
        ["基本信息", {"fields": ("id", ("create_time", "update_time"))}],
        ["项目信息", {"fields": (("name", "project_name"),)}],
        ["镜像", {"fields": ("source_image", "target_image", "tag_count")}],
        ["镜像仓库", {
            "fields":
                (
                    "registry_host", "registry_namespace",
                    ("registry_username", "registry_password"),
                )
        }],
    )
    readonly_fields = ["id", "source_image", "target_image", "tag_count",
                       "create_time", "update_time"]
    list_display = ["name", "source_image", "target_image", "tag_count", "update_time"]
    search_fields = ["name", "source_image", "target_image"]
    actions = [flush_project]


class TagAdmin(admin.ModelAdmin):
    fieldsets = (
        ["基本信息", {"fields": ("id", ("create_time", "update_time"))}],
        ["项目信息", {"fields": ("project", "name")}],
        ["镜像信息", {"fields": ("image_url",)}],
        ["同步任务", {"fields": ("status", "error_message")}],
    )
    list_display = ["project", "name", "image_url", "status", "create_time"]
    search_fields = ["image_url"]
    list_filter = ["status"]
    actions = [try_migrate_image]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request):
        return False


admin.site.register(Namespace, NamespaceAdmin)
admin.site.register(Project, ProjectAdmin)
admin.site.register(Tag, TagAdmin)
