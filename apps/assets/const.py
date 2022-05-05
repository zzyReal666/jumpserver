from django.db import models
from django.utils.translation import gettext_lazy as _
from common.db.models import IncludesTextChoicesMeta


__all__ = [
    'Category', 'HostTypes', 'NetworkTypes', 'DatabaseTypes',
    'RemoteAppTypes', 'CloudTypes', 'Protocol', 'AllTypes',
]


class PlatformMixin:
    @classmethod
    def platform_limits(cls):
        return {}


class Category(PlatformMixin, models.TextChoices):
    HOST = 'host', _('Host')
    NETWORK = 'network', _("NetworkDevice")
    DATABASE = 'database', _("Database")
    REMOTE_APP = 'remote_app', _("Remote app")
    CLOUD = 'cloud', _("Clouding")

    @classmethod
    def platform_limits(cls):
        return {
            cls.HOST: {
                'has_domain': True,
                'protocols_limit': ['ssh', 'rdp', 'vnc', 'telnet']
            },
            cls.NETWORK: {
                'has_domain': True,
                'protocols_limit': ['ssh', 'telnet']
            },
            cls.DATABASE: {
                'has_domain': True
            },
            cls.REMOTE_APP: {
                'has_domain': True
            },
            cls.CLOUD: {
                'has_domain': False,
                'protocol_limit': []
            }
        }


class HostTypes(PlatformMixin, models.TextChoices):
    LINUX = 'linux', 'Linux'
    WINDOWS = 'windows', 'Windows'
    UNIX = 'unix', 'Unix'
    BSD = 'bsd', 'BSD'
    MACOS = 'macos', 'MacOS'
    MAINFRAME = 'mainframe', _("Mainframe")
    OTHER_HOST = 'other_host', _("Other host")

    @classmethod
    def platform_limits(cls):
        return {}

    @classmethod
    def get_default_port(cls):
        defaults = {
            cls.LINUX: 22,
            cls.WINDOWS: 3389,
            cls.UNIX: 22,
            cls.BSD: 22,
            cls.MACOS: 22,
            cls.MAINFRAME: 22,
        }


class NetworkTypes(PlatformMixin, models.TextChoices):
    SWITCH = 'switch', _("Switch")
    ROUTER = 'router', _("Router")
    FIREWALL = 'firewall', _("Firewall")
    OTHER_NETWORK = 'other_network', _("Other device")


class DatabaseTypes(PlatformMixin, models.TextChoices):
    MYSQL = 'mysql', 'MySQL'
    MARIADB = 'mariadb', 'MariaDB'
    POSTGRESQL = 'postgresql', 'PostgreSQL'
    ORACLE = 'oracle', 'Oracle'
    SQLSERVER = 'sqlserver', 'SQLServer'
    MONGODB = 'mongodb', 'MongoDB'
    REDIS = 'redis', 'Redis'

    @classmethod
    def platform_limits(cls):
        meta = {}
        for name, label in cls.choices:
            meta[name] = {
                'protocols_limit': [name]
            }
        return meta


class RemoteAppTypes(PlatformMixin, models.TextChoices):
    CHROME = 'chrome', 'Chrome'
    VSPHERE = 'vmware_client', 'vSphere client'
    MYSQL_WORKBENCH = 'mysql_workbench', 'MySQL workbench'
    GENERAL_REMOTE_APP = 'general_remote_app', _("Custom")


class CloudTypes(PlatformMixin, models.TextChoices):
    K8S = 'k8s', 'Kubernetes'


class AllTypes(metaclass=IncludesTextChoicesMeta):
    choices: list
    includes = [
        HostTypes, NetworkTypes, DatabaseTypes,
        RemoteAppTypes, CloudTypes
    ]

    @classmethod
    def get_type_limits(cls, category, tp):
        limits = Category.platform_limits().get(category, {})
        types_cls = dict(cls.category_types()).get(category)
        if not types_cls:
            return {}
        types_limits = types_cls.platform_limits() or {}
        type_limits = types_limits.get(tp, {})
        limits.update(type_limits)

        _protocols_limit = limits.get('protocols_limit', [])
        default_ports = Protocol.default_ports()
        protocols_limit = []
        for p in _protocols_limit:
            port = default_ports.get(p, 0)
            protocols_limit.append(f'{p}/{port}')
        limits['protocols_limit'] = protocols_limit
        return limits

    @classmethod
    def category_types(cls):
        return (
            (Category.HOST, HostTypes),
            (Category.NETWORK, NetworkTypes),
            (Category.DATABASE, DatabaseTypes),
            (Category.REMOTE_APP, RemoteAppTypes),
            (Category.CLOUD, CloudTypes)
        )

    @classmethod
    def grouped_choices(cls):
        grouped_types = [(str(ca), tp.choices) for ca, tp in cls.category_types()]
        return grouped_types

    @classmethod
    def grouped_choices_to_objs(cls):
        choices = cls.serialize_to_objs(Category.choices)
        mapper = dict(cls.grouped_choices())
        for choice in choices:
            children = cls.serialize_to_objs(mapper[choice['value']])
            choice['children'] = children
        return choices

    @staticmethod
    def serialize_to_objs(choices):
        title = ['value', 'display_name']
        return [dict(zip(title, choice)) for choice in choices]


class Protocol(models.TextChoices):
    ssh = 'ssh', 'SSH'
    rdp = 'rdp', 'RDP'
    telnet = 'telnet', 'Telnet'
    vnc = 'vnc', 'VNC'

    mysql = 'mysql', 'MySQL'
    mariadb = 'mariadb', 'MariaDB'
    oracle = 'oracle', 'Oracle'
    postgresql = 'postgresql', 'PostgreSQL'
    sqlserver = 'sqlserver', 'SQLServer'
    redis = 'redis', 'Redis'
    mongodb = 'mongodb', 'MongoDB'

    k8s = 'k8s', 'K8S'

    @classmethod
    def host_protocols(cls):
        return [cls.ssh, cls.rdp, cls.telnet, cls.vnc]

    @classmethod
    def db_protocols(cls):
        return [
            cls.mysql, cls.mariadb, cls.postgresql, cls.oracle,
            cls.sqlserver, cls.redis, cls.mongodb,
        ]

    @classmethod
    def default_ports(cls):
        return {
            cls.ssh: 22,
            cls.rdp: 3389,
            cls.vnc: 5900,
            cls.telnet: 21,

            cls.mysql: 3306,
            cls.mariadb: 3306,
            cls.postgresql: 5432,
            cls.oracle: 1521,
            cls.sqlserver: 1433,
            cls.mongodb: 27017,
            cls.redis: 6379,

            cls.k8s: 0
        }

