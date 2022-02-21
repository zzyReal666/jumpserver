#!/usr/bin/env python
# -*- coding: utf-8 -*-
# 

import uuid
import logging
from functools import reduce
from collections import OrderedDict

from django.db import models
from django.utils.translation import ugettext_lazy as _
from rest_framework.exceptions import ValidationError

from common.fields.model import JsonDictTextField
from common.utils import lazyproperty
from orgs.mixins.models import OrgModelMixin, OrgManager

from .base import AbsConnectivity

__all__ = ['Asset', 'ProtocolsMixin', 'Platform', 'AssetQuerySet']
logger = logging.getLogger(__name__)


def default_cluster():
    from .cluster import Cluster
    name = "Default"
    defaults = {"name": name}
    cluster, created = Cluster.objects.get_or_create(
        defaults=defaults, name=name
    )
    return cluster.id


def default_node():
    try:
        from .node import Node
        root = Node.org_root()
        return Node.objects.filter(id=root.id)
    except:
        return None


class AssetManager(OrgManager):
    pass


class AssetQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def valid(self):
        return self.active()

    def has_protocol(self, name):
        return self.filter(protocols__contains=name)


class ProtocolsMixin:
    protocols = ''

    class Protocol(models.TextChoices):
        ssh = 'ssh', 'SSH'
        rdp = 'rdp', 'RDP'
        telnet = 'telnet', 'Telnet'
        vnc = 'vnc', 'VNC'

    @property
    def protocols_as_list(self):
        if not self.protocols:
            return []
        return self.protocols.split(' ')

    @property
    def protocols_as_dict(self):
        d = OrderedDict()
        protocols = self.protocols_as_list
        for i in protocols:
            if '/' not in i:
                continue
            name, port = i.split('/')[:2]
            if not all([name, port]):
                continue
            d[name] = int(port)
        return d

    @property
    def protocols_as_json(self):
        return [
            {"name": name, "port": port}
            for name, port in self.protocols_as_dict.items()
        ]

    def has_protocol(self, name):
        return name in self.protocols_as_dict

    @property
    def ssh_port(self):
        return self.protocols_as_dict.get("ssh", 22)


class NodesRelationMixin:
    NODES_CACHE_KEY = 'ASSET_NODES_{}'
    ALL_ASSET_NODES_CACHE_KEY = 'ALL_ASSETS_NODES'
    CACHE_TIME = 3600 * 24 * 7
    id = ""
    _all_nodes_keys = None

    def get_nodes(self):
        from .node import Node
        nodes = self.nodes.all()
        if not nodes:
            nodes = Node.objects.filter(id=Node.org_root().id)
        return nodes

    def get_all_nodes(self, flat=False):
        nodes = []
        for node in self.get_nodes():
            _nodes = node.get_ancestors(with_self=True)
            nodes.append(_nodes)
        if flat:
            nodes = list(reduce(lambda x, y: set(x) | set(y), nodes))
        return nodes


class Platform(models.Model):
    CHARSET_CHOICES = (
        ('utf8', 'UTF-8'),
        ('gbk', 'GBK'),
    )
    BASE_CHOICES = (
        ('Linux', 'Linux'),
        ('Unix', 'Unix'),
        ('MacOS', 'MacOS'),
        ('BSD', 'BSD'),
        ('Windows', 'Windows'),
        ('Other', 'Other'),
    )
    name = models.SlugField(verbose_name=_("Name"), unique=True, allow_unicode=True)
    base = models.CharField(choices=BASE_CHOICES, max_length=16, default='Linux', verbose_name=_("Base"))
    charset = models.CharField(default='utf8', choices=CHARSET_CHOICES, max_length=8, verbose_name=_("Charset"))
    meta = JsonDictTextField(blank=True, null=True, verbose_name=_("Meta"))
    internal = models.BooleanField(default=False, verbose_name=_("Internal"))
    comment = models.TextField(blank=True, null=True, verbose_name=_("Comment"))

    @classmethod
    def default(cls):
        linux, created = cls.objects.get_or_create(
            defaults={'name': 'Linux'}, name='Linux'
        )
        return linux.id

    def is_windows(self):
        return self.base.lower() in ('windows',)

    def is_unixlike(self):
        return self.base.lower() in ("linux", "unix", "macos", "bsd")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Platform")
        # ordering = ('name',)


class AbsHardwareInfo(models.Model):
    # Collect
    vendor = models.CharField(max_length=64, null=True, blank=True, verbose_name=_('Vendor'))
    model = models.CharField(max_length=54, null=True, blank=True, verbose_name=_('Model'))
    sn = models.CharField(max_length=128, null=True, blank=True, verbose_name=_('Serial number'))

    cpu_model = models.CharField(max_length=64, null=True, blank=True, verbose_name=_('CPU model'))
    cpu_count = models.IntegerField(null=True, verbose_name=_('CPU count'))
    cpu_cores = models.IntegerField(null=True, verbose_name=_('CPU cores'))
    cpu_vcpus = models.IntegerField(null=True, verbose_name=_('CPU vcpus'))
    memory = models.CharField(max_length=64, null=True, blank=True, verbose_name=_('Memory'))
    disk_total = models.CharField(max_length=1024, null=True, blank=True, verbose_name=_('Disk total'))
    disk_info = models.CharField(max_length=1024, null=True, blank=True, verbose_name=_('Disk info'))

    os = models.CharField(max_length=128, null=True, blank=True, verbose_name=_('OS'))
    os_version = models.CharField(max_length=16, null=True, blank=True, verbose_name=_('OS version'))
    os_arch = models.CharField(max_length=16, blank=True, null=True, verbose_name=_('OS arch'))
    hostname_raw = models.CharField(max_length=128, blank=True, null=True, verbose_name=_('Hostname raw'))

    class Meta:
        abstract = True

    @property
    def cpu_info(self):
        info = ""
        if self.cpu_model:
            info += self.cpu_model
        if self.cpu_count and self.cpu_cores:
            info += "{}*{}".format(self.cpu_count, self.cpu_cores)
        return info

    @property
    def hardware_info(self):
        if self.cpu_count:
            return '{} Core {} {}'.format(
                self.cpu_vcpus or self.cpu_count * self.cpu_cores,
                self.memory, self.disk_total
            )
        else:
            return ''


class Asset(AbsConnectivity, AbsHardwareInfo, ProtocolsMixin, NodesRelationMixin, OrgModelMixin):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    ip = models.CharField(max_length=128, verbose_name=_('IP'), db_index=True)
    hostname = models.CharField(max_length=128, verbose_name=_('Hostname'))
    protocol = models.CharField(max_length=128, default=ProtocolsMixin.Protocol.ssh,
                                choices=ProtocolsMixin.Protocol.choices, verbose_name=_('Protocol'))
    port = models.IntegerField(default=22, verbose_name=_('Port'))
    protocols = models.CharField(max_length=128, default='ssh/22', blank=True, verbose_name=_("Protocols"))
    platform = models.ForeignKey(Platform, default=Platform.default, on_delete=models.PROTECT, verbose_name=_("Platform"), related_name='assets')
    domain = models.ForeignKey("assets.Domain", null=True, blank=True, related_name='assets', verbose_name=_("Domain"), on_delete=models.SET_NULL)
    nodes = models.ManyToManyField('assets.Node', default=default_node, related_name='assets', verbose_name=_("Nodes"))
    is_active = models.BooleanField(default=True, verbose_name=_('Is active'))

    # Auth
    admin_user = models.ForeignKey('assets.SystemUser', on_delete=models.SET_NULL, null=True, verbose_name=_("Admin user"), related_name='admin_assets')

    # Some information
    public_ip = models.CharField(max_length=128, blank=True, null=True, verbose_name=_('Public IP'))
    number = models.CharField(max_length=32, null=True, blank=True, verbose_name=_('Asset number'))

    labels = models.ManyToManyField('assets.Label', blank=True, related_name='assets', verbose_name=_("Labels"))
    created_by = models.CharField(max_length=128, null=True, blank=True, verbose_name=_('Created by'))
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name=_('Date created'))
    comment = models.TextField(default='', blank=True, verbose_name=_('Comment'))

    objects = AssetManager.from_queryset(AssetQuerySet)()

    def __str__(self):
        return '{0.hostname}({0.ip})'.format(self)

    def set_admin_user_relation(self):
        from .authbook import AuthBook
        if not self.admin_user:
            return
        if self.admin_user.type != 'admin':
            raise ValidationError('System user should be type admin')

        defaults = {'asset': self, 'systemuser': self.admin_user, 'org_id': self.org_id}
        AuthBook.objects.get_or_create(defaults=defaults, asset=self, systemuser=self.admin_user)

    @property
    def admin_user_display(self):
        if not self.admin_user:
            return ''
        return str(self.admin_user)

    @property
    def is_valid(self):
        warning = ''
        if not self.is_active:
            warning += ' inactive'
        if warning:
            return False, warning
        return True, warning

    @lazyproperty
    def platform_base(self):
        return self.platform.base

    @lazyproperty
    def admin_user_username(self):
        """求可连接性时，直接用用户名去取，避免再查一次admin user
        serializer 中直接通过annotate方式返回了这个
        """
        return self.admin_user.username

    def is_windows(self):
        return self.platform.is_windows()

    def is_unixlike(self):
        return self.platform.is_unixlike()

    def is_support_ansible(self):
        return self.has_protocol('ssh') and self.platform_base not in ("Other",)

    def get_auth_info(self):
        if not self.admin_user:
            return {}

        self.admin_user.load_asset_special_auth(self)
        info = {
            'username': self.admin_user.username,
            'password': self.admin_user.password,
            'private_key': self.admin_user.private_key_file,
        }
        return info

    def nodes_display(self):
        names = []
        for n in self.nodes.all():
            names.append(n.full_value)
        return names

    def labels_display(self):
        names = []
        for n in self.labels.all():
            names.append(n.name + ':' + n.value)
        return names

    def as_node(self):
        from .node import Node
        fake_node = Node()
        fake_node.id = self.id
        fake_node.key = self.id
        fake_node.value = self.hostname
        fake_node.asset = self
        fake_node.is_node = False
        return fake_node

    def as_tree_node(self, parent_node):
        from common.tree import TreeNode
        icon_skin = 'file'
        if self.platform_base.lower() == 'windows':
            icon_skin = 'windows'
        elif self.platform_base.lower() == 'linux':
            icon_skin = 'linux'
        data = {
            'id': str(self.id),
            'name': self.hostname,
            'title': self.ip,
            'pId': parent_node.key,
            'isParent': False,
            'open': False,
            'iconSkin': icon_skin,
            'meta': {
                'type': 'asset',
                'data': {
                    'id': self.id,
                    'hostname': self.hostname,
                    'ip': self.ip,
                    'protocols': self.protocols_as_list,
                    'platform': self.platform_base,
                }
            }
        }
        tree_node = TreeNode(**data)
        return tree_node

    def get_all_system_users(self):
        from .user import SystemUser
        system_user_ids = SystemUser.assets.through.objects.filter(asset=self)\
            .values_list('systemuser_id', flat=True)
        system_users = SystemUser.objects.filter(id__in=system_user_ids)
        return system_users

    class Meta:
        unique_together = [('org_id', 'hostname')]
        verbose_name = _("Asset")
        ordering = ["hostname", ]
        permissions = [
            ('test_assetconnectivity', 'Can test asset connectivity'),
            ('push_assetsystemuser', 'Can push system user to asset'),
        ]
