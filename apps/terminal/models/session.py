from __future__ import unicode_literals

import os
import uuid

from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.cache import cache

from assets.models import Asset
from users.models import User
from orgs.mixins.models import OrgModelMixin
from django.db.models import TextChoices
from ..backends import get_multi_command_storage


class Session(OrgModelMixin):
    class LOGIN_FROM(TextChoices):
        ST = 'ST', 'SSH Terminal'
        RT = 'RT', 'RDP Terminal'
        WT = 'WT', 'Web Terminal'

    class PROTOCOL(TextChoices):
        SSH = 'ssh', 'ssh'
        RDP = 'rdp', 'rdp'
        VNC = 'vnc', 'vnc'
        TELNET = 'telnet', 'telnet'
        MYSQL = 'mysql', 'mysql'
        ORACLE = 'oracle', 'oracle'
        MARIADB = 'mariadb', 'mariadb'
        SQLSERVER = 'sqlserver', 'sqlserver'
        POSTGRESQL = 'postgresql', 'postgresql'
        REDIS = 'redis', 'redis'
        MONGODB = 'mongodb', 'MongoDB'
        K8S = 'k8s', 'kubernetes'

    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    user = models.CharField(max_length=128, verbose_name=_("User"), db_index=True)
    user_id = models.CharField(blank=True, default='', max_length=36, db_index=True)
    asset = models.CharField(max_length=128, verbose_name=_("Asset"), db_index=True)
    asset_id = models.CharField(blank=True, default='', max_length=36, db_index=True)
    system_user = models.CharField(max_length=128, verbose_name=_("System user"), db_index=True)
    system_user_id = models.CharField(blank=True, default='', max_length=36, db_index=True)
    login_from = models.CharField(max_length=2, choices=LOGIN_FROM.choices, default="ST", verbose_name=_("Login from"))
    remote_addr = models.CharField(max_length=128, verbose_name=_("Remote addr"), blank=True, null=True)
    is_success = models.BooleanField(default=True, db_index=True)
    is_finished = models.BooleanField(default=False, db_index=True)
    has_replay = models.BooleanField(default=False, verbose_name=_("Replay"))
    has_command = models.BooleanField(default=False, verbose_name=_("Command"))
    terminal = models.ForeignKey('terminal.Terminal', null=True, on_delete=models.DO_NOTHING, db_constraint=False)
    protocol = models.CharField(choices=PROTOCOL.choices, default='ssh', max_length=16, db_index=True)
    date_start = models.DateTimeField(verbose_name=_("Date start"), db_index=True, default=timezone.now)
    date_end = models.DateTimeField(verbose_name=_("Date end"), null=True)

    upload_to = 'replay'
    ACTIVE_CACHE_KEY_PREFIX = 'SESSION_ACTIVE_{}'
    SUFFIX_MAP = {1: '.gz', 2: '.replay.gz', 3: '.cast.gz'}
    DEFAULT_SUFFIXES = ['.replay.gz', '.cast.gz', '.gz']

    # Todo: 将来干掉 local_path, 使用 default storage 实现
    def get_all_possible_local_path(self):
        """
        获取所有可能的本地存储录像文件路径
        :return:
        """
        return [self.get_local_storage_path_by_suffix(suffix)
                for suffix in self.SUFFIX_MAP.values()]

    def get_all_possible_relative_path(self):
        """
        获取所有可能的外部存储录像文件路径
        :return:
        """
        return [self.get_relative_path_by_suffix(suffix)
                for suffix in self.SUFFIX_MAP.values()]

    def get_local_storage_path_by_suffix(self, suffix='.cast.gz'):
        """
        local_path: replay/2021-12-08/session_id.cast.gz
        通过后缀名获取本地存储的录像文件路径
        :param suffix: .cast.gz | '.replay.gz' | '.gz'
        :return:
        """
        rel_path = self.get_relative_path_by_suffix(suffix)
        if suffix == '.gz':
            # 兼容 v1 的版本
            return rel_path
        return os.path.join(self.upload_to, rel_path)

    def get_relative_path_by_suffix(self, suffix='.cast.gz'):
        """
        relative_path: 2021-12-08/session_id.cast.gz
        通过后缀名获取外部存储录像文件路径
        :param suffix: .cast.gz | '.replay.gz' | '.gz'
        :return:
        """
        date = self.date_start.strftime('%Y-%m-%d')
        return os.path.join(date, str(self.id) + suffix)

    def get_local_path_by_relative_path(self, rel_path):
        """
        2021-12-08/session_id.cast.gz
        :param rel_path:
        :return: replay/2021-12-08/session_id.cast.gz
        """
        return '{}/{}'.format(self.upload_to, rel_path)

    def get_relative_path_by_local_path(self, local_path):
        return local_path.replace('{}/'.format(self.upload_to), '')

    def find_ok_relative_path_in_storage(self, storage):
        session_paths = self.get_all_possible_relative_path()
        for rel_path in session_paths:
            if storage.exists(rel_path):
                return rel_path

    @property
    def asset_obj(self):
        return Asset.objects.get(id=self.asset_id)

    @property
    def user_obj(self):
        return User.objects.get(id=self.user_id)

    def can_replay(self):
        return self.has_replay

    @property
    def can_join(self):
        _PROTOCOL = self.PROTOCOL
        if self.is_finished:
            return False
        if self.login_from == self.LOGIN_FROM.RT:
            return False
        if self.protocol in [
            _PROTOCOL.SSH, _PROTOCOL.VNC, _PROTOCOL.RDP,
            _PROTOCOL.TELNET, _PROTOCOL.K8S
        ]:
            return True
        else:
            return False

    @property
    def db_protocols(self):
        _PROTOCOL = self.PROTOCOL
        return [_PROTOCOL.MYSQL, _PROTOCOL.MARIADB, _PROTOCOL.ORACLE,
                _PROTOCOL.POSTGRESQL, _PROTOCOL.SQLSERVER,
                _PROTOCOL.REDIS, _PROTOCOL.MONGODB]

    @property
    def can_terminate(self):
        _PROTOCOL = self.PROTOCOL
        if self.is_finished:
            return False
        else:
            return True

    def save_replay_to_storage_with_version(self, f, version=2):
        suffix = self.SUFFIX_MAP.get(version, '.cast.gz')
        local_path = self.get_local_storage_path_by_suffix(suffix)
        try:
            name = default_storage.save(local_path, f)
        except OSError as e:
            return None, e

        if settings.SERVER_REPLAY_STORAGE:
            from ..tasks import upload_session_replay_to_external_storage
            upload_session_replay_to_external_storage.delay(str(self.id))
        return name, None

    @classmethod
    def set_sessions_active(cls, session_ids):
        data = {cls.ACTIVE_CACHE_KEY_PREFIX.format(i): i for i in session_ids}
        cache.set_many(data, timeout=5 * 60)

    @classmethod
    def get_active_sessions(cls):
        return cls.objects.filter(is_finished=False)

    def is_active(self):
        key = self.ACTIVE_CACHE_KEY_PREFIX.format(self.id)
        return bool(cache.get(key))

    @property
    def command_amount(self):
        command_store = get_multi_command_storage()
        return command_store.count(session=str(self.id))

    @property
    def login_from_display(self):
        return self.get_login_from_display()

    @classmethod
    def generate_fake(cls, count=100, is_finished=True):
        import random
        from orgs.models import Organization
        from users.models import User
        from assets.models import Asset, SystemUser
        from orgs.utils import get_current_org
        from common.utils.random import random_datetime, random_ip

        org = get_current_org()
        if not org or org.is_root():
            Organization.default().change_to()
        i = 0
        users = User.objects.all()[:100]
        assets = Asset.objects.all()[:100]
        system_users = SystemUser.objects.all()[:100]
        while i < count:
            user_random = random.choices(users, k=10)
            assets_random = random.choices(assets, k=10)
            system_users = random.choices(system_users, k=10)

            ziped = zip(user_random, assets_random, system_users)
            sessions = []
            now = timezone.now()
            month_ago = now - timezone.timedelta(days=30)
            for user, asset, system_user in ziped:
                ip = random_ip()
                date_start = random_datetime(month_ago, now)
                date_end = random_datetime(date_start, date_start + timezone.timedelta(hours=2))
                data = dict(
                    user=str(user), user_id=user.id,
                    asset=str(asset), asset_id=asset.id,
                    system_user=str(system_user), system_user_id=system_user.id,
                    remote_addr=ip,
                    date_start=date_start,
                    date_end=date_end,
                    is_finished=is_finished,
                )
                sessions.append(Session(**data))
            cls.objects.bulk_create(sessions)
            i += 10

    class Meta:
        db_table = "terminal_session"
        ordering = ["-date_start"]
        verbose_name = _('Session record')
        permissions = [
            ('monitor_session', _('Can monitor session')),
            ('share_session', _('Can share session')),
            ('terminate_session', _('Can terminate session')),
            ('validate_sessionactionperm', _('Can validate session action perm')),
        ]

    def __str__(self):
        return "{0.id} of {0.user} to {0.asset}".format(self)
