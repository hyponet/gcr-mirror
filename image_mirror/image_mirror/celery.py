from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'image_mirror.settings')
app = Celery('image_mirror', include=["worker"])
app.config_from_object('django.conf:settings', namespace='CELERY')

# Sentry
if os.getenv("WORKER_SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.getenv("WORKER_SENTRY_DSN"), integrations=[CeleryIntegration()])
