import os.path
import random

import yaml
from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import default_storage
from django.db import models
from django.utils.translation import gettext_lazy as _
from rest_framework.serializers import ValidationError

from common.db.models import JMSBaseModel

__all__ = ['Applet', 'AppletPublication']


class Applet(JMSBaseModel):
    class Type(models.TextChoices):
        general = 'general', _('General')
        web = 'web', _('Web')

    name = models.SlugField(max_length=128, verbose_name=_('Name'), unique=True)
    display_name = models.CharField(max_length=128, verbose_name=_('Display name'))
    version = models.CharField(max_length=16, verbose_name=_('Version'))
    author = models.CharField(max_length=128, verbose_name=_('Author'))
    type = models.CharField(max_length=16, verbose_name=_('Type'), default='general', choices=Type.choices)
    is_active = models.BooleanField(default=True, verbose_name=_('Is active'))
    builtin = models.BooleanField(default=False, verbose_name=_('Builtin'))
    protocols = models.JSONField(default=list, verbose_name=_('Protocol'))
    tags = models.JSONField(default=list, verbose_name=_('Tags'))
    comment = models.TextField(default='', blank=True, verbose_name=_('Comment'))
    hosts = models.ManyToManyField(
        through_fields=('applet', 'host'), through='AppletPublication',
        to='AppletHost', verbose_name=_('Hosts')
    )

    def __str__(self):
        return self.name

    @property
    def path(self):
        if self.builtin:
            return os.path.join(settings.APPS_DIR, 'terminal', 'applets', self.name)
        else:
            return default_storage.path('applets/{}'.format(self.name))

    @property
    def manifest(self):
        path = os.path.join(self.path, 'manifest.yml')
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            return yaml.safe_load(f)

    @property
    def icon(self):
        path = os.path.join(self.path, 'icon.png')
        if not os.path.exists(path):
            return None
        return os.path.join(settings.MEDIA_URL, 'applets', self.name, 'icon.png')

    @staticmethod
    def validate_pkg(d):
        files = ['manifest.yml', 'icon.png', 'i18n.yml', 'setup.yml']
        for name in files:
            path = os.path.join(d, name)
            if not os.path.exists(path):
                raise ValidationError({'error': 'Missing file {}'.format(path)})

        with open(os.path.join(d, 'manifest.yml')) as f:
            manifest = yaml.safe_load(f)

        if not manifest.get('name', ''):
            raise ValidationError({'error': 'Missing name in manifest.yml'})
        return manifest

    @classmethod
    def install_from_dir(cls, path):
        from terminal.serializers import AppletSerializer

        manifest = cls.validate_pkg(path)
        name = manifest['name']
        instance = cls.objects.filter(name=name).first()
        serializer = AppletSerializer(instance=instance, data=manifest)
        serializer.is_valid()
        serializer.save(builtin=True)
        return instance

    def select_host_account(self):
        hosts = list(self.hosts.all())
        if not hosts:
            return None

        host = random.choice(hosts)
        using_keys = cache.keys('host_accounts_{}_*'.format(host.id)) or []
        accounts_used = cache.get_many(using_keys)
        accounts = host.accounts.all().exclude(username__in=accounts_used)

        if not accounts:
            accounts = host.accounts.all()
        if not accounts:
            return None

        account = random.choice(accounts)
        ttl = 60 * 60 * 24
        lock_key = 'applet_host_accounts_{}_{}'.format(host.id, account.username)
        cache.set(lock_key, account.username, ttl)

        return {
            'host': host,
            'account': account,
            'lock_key': lock_key,
            'ttl': ttl
        }

    @staticmethod
    def release_host_and_account(host_id, username):
        key = 'applet_host_accounts_{}_{}'.format(host_id, username)
        cache.delete(key)


class AppletPublication(JMSBaseModel):
    applet = models.ForeignKey('Applet', on_delete=models.PROTECT, related_name='publications',
                               verbose_name=_('Applet'))
    host = models.ForeignKey('AppletHost', on_delete=models.PROTECT, related_name='publications',
                             verbose_name=_('Host'))
    status = models.CharField(max_length=16, default='ready', verbose_name=_('Status'))
    comment = models.TextField(default='', blank=True, verbose_name=_('Comment'))

    class Meta:
        unique_together = ('applet', 'host')
