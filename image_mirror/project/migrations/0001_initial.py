# Generated by Django 2.1.5 on 2019-01-22 14:02

import common.utils
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Namespace',
            fields=[
                ('id', models.CharField(default=common.utils.gen_uuid, max_length=36, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=256)),
                ('registry_host', models.CharField(default='https://gcr.io', max_length=256)),
                ('registry_username', models.CharField(max_length=256, null=True)),
                ('registry_password', models.CharField(max_length=128, null=True)),
                ('created_at', models.BigIntegerField(default=common.utils.get_time)),
                ('updated_at', models.BigIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.CharField(default=common.utils.gen_uuid, max_length=36, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=256, unique=True)),
                ('project_name', models.CharField(max_length=256, unique=True)),
                ('namespace_id', models.CharField(db_index=True, max_length=36, null=True)),
                ('source_image', models.CharField(db_index=True, max_length=256)),
                ('target_image', models.CharField(db_index=True, max_length=256)),
                ('registry_host', models.CharField(default='https://gcr.io', max_length=256)),
                ('registry_namespace', models.CharField(blank=True, default='', max_length=128)),
                ('registry_username', models.CharField(max_length=256, null=True)),
                ('registry_password', models.CharField(max_length=128, null=True)),
                ('created_at', models.BigIntegerField(default=common.utils.get_time)),
                ('updated_at', models.BigIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('id', models.CharField(default=common.utils.gen_uuid, max_length=36, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=256)),
                ('project_id', models.CharField(db_index=True, max_length=36)),
                ('image_url', models.CharField(blank=True, default='', max_length=256)),
                ('status', models.CharField(choices=[('pending', '等待同步'), ('syncing', '正在同步'), ('synced', '同步完成'), ('error', '异常')], db_index=True, default='pending', max_length=128)),
                ('error_message', models.TextField()),
                ('created_at', models.BigIntegerField(default=common.utils.get_time)),
                ('updated_at', models.BigIntegerField(default=common.utils.get_time)),
            ],
        ),
    ]
