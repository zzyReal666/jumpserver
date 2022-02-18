import uuid

from django.db import models
from django.utils.translation import ugettext_lazy as _

from common.utils import lazyproperty, settings
from common.tree import TreeNode


class Organization(models.Model):
    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    name = models.CharField(max_length=128, unique=True, verbose_name=_("Name"))
    created_by = models.CharField(max_length=32, null=True, blank=True, verbose_name=_('Created by'))
    date_created = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name=_('Date created'))
    comment = models.TextField(default='', blank=True, verbose_name=_('Comment'))
    members = models.ManyToManyField('users.User', related_name='orgs', through='rbac.RoleBinding', through_fields=('org', 'user'))

    ROOT_ID = '00000000-0000-0000-0000-000000000000'
    ROOT_NAME = _('GLOBAL')
    DEFAULT_ID = '00000000-0000-0000-0000-000000000002'
    DEFAULT_NAME = 'Default'
    orgs_mapping = None

    class Meta:
        verbose_name = _("Organization")
        permissions = (
            ('view_rootorg', _('Can view root org')),
        )

    def __str__(self):
        return str(self.name)

    @classmethod
    def get_instance(cls, id_or_name, default=None):
        assert default is None or isinstance(default, cls), (
            '`default` must be None or `Organization` instance'
        )
        org = cls.get_instance_from_memory(id_or_name)
        org = org or default
        return org

    @classmethod
    def get_instance_from_memory(cls, id_or_name):
        if not isinstance(cls.orgs_mapping, dict):
            cls.orgs_mapping = cls.construct_orgs_mapping()

        org = cls.orgs_mapping.get(str(id_or_name))
        if not org:
            # 内存失效速度慢于读取速度(on_org_create_or_update)
            cls.orgs_mapping = cls.construct_orgs_mapping()

        org = cls.orgs_mapping.get(str(id_or_name))
        return org

    @classmethod
    def construct_orgs_mapping(cls):
        orgs_mapping = {}
        for org in cls.objects.all():
            orgs_mapping[str(org.id)] = org
            orgs_mapping[str(org.name)] = org
        root_org = cls.root()
        orgs_mapping.update({
            root_org.id: root_org,
            'GLOBAL': root_org,
            '全局组织': root_org
        })
        return orgs_mapping

    @classmethod
    def expire_orgs_mapping(cls):
        cls.orgs_mapping = None

    def org_id(self):
        return self.id

    @classmethod
    def default(cls):
        defaults = dict(id=cls.DEFAULT_ID, name=cls.DEFAULT_NAME)
        obj, created = cls.objects.get_or_create(defaults=defaults, id=cls.DEFAULT_ID)
        return obj

    @classmethod
    def root(cls):
        name = settings.GLOBAL_ORG_DISPLAY_NAME or cls.ROOT_NAME
        return cls(id=cls.ROOT_ID, name=name)

    def is_root(self):
        return self.id == self.ROOT_ID

    def is_default(self):
        return str(self.id) == self.DEFAULT_ID

    def change_to(self):
        from .utils import set_current_org
        set_current_org(self)

    @lazyproperty
    def resource_statistics_cache(self):
        # Todo: 由于 redis 问题，没能获取到
        return {}
        from .caches import OrgResourceStatisticsCache
        return OrgResourceStatisticsCache(self)

    def get_members(self):
        return self.members.all().distinct()

    def add_member(self, user, role=None):
        from rbac.builtin import BuiltinRole
        from .utils import tmp_to_org
        role_id = BuiltinRole.org_user.id
        if role:
            role_id = role.id
        with tmp_to_org(self):
            self.members.through.objects.create(
                user=user, role_id=role_id,
                org_id=self.id, scope='org'
            )

    def get_total_resources_amount(self):
        from django.apps import apps
        from orgs.mixins.models import OrgModelMixin
        summary = {'users.Members': self.get_members().count()}
        for app_name, app_config in apps.app_configs.items():
            models_cls = app_config.get_models()
            for model in models_cls:
                if not issubclass(model, OrgModelMixin):
                    continue
                key = '{}.{}'.format(app_name, model.__name__)
                summary[key] = self.get_resource_amount(model)
        return summary

    def get_resource_amount(self, resource_model):
        from .utils import tmp_to_org
        from .mixins.models import OrgModelMixin

        if not issubclass(resource_model, OrgModelMixin):
            return 0
        with tmp_to_org(self):
            return resource_model.objects.all().count()

    def as_tree_node(self, oid, pid, opened=True):
        node = TreeNode(**{
            'id': oid,
            'name': self.name,
            'title': self.name,
            'pId': pid,
            'open': opened,
            'isParent': True,
            'meta': {
                'type': 'org'
            }
        })
        return node


# class OrgMemberManager(models.Manager):
#     def remove_users(self, org, users):
#         from users.models import User
#         pk_set = []
#         for user in users:
#             if hasattr(user, 'pk'):
#                 pk_set.append(user.pk)
#             else:
#                 pk_set.append(user)
#
#         send = partial(
#             signals.m2m_changed.send, sender=self.model,
#             instance=org, reverse=False, model=User,
#             pk_set=pk_set, using=self.db
#         )
#         send(action="pre_remove")
#         self.filter(org_id=org.id, user_id__in=pk_set).delete()
#         send(action="post_remove")


class OrganizationMember(models.Model):
    """
    注意：直接调用该 `Model.delete` `Model.objects.delete` 不会触发清理该用户的信号
    """

    id = models.UUIDField(default=uuid.uuid4, primary_key=True)
    org = models.ForeignKey(Organization, related_name='m2m_org_members', on_delete=models.CASCADE, verbose_name=_('Organization'))
    user = models.ForeignKey('users.User', related_name='m2m_org_members', on_delete=models.CASCADE, verbose_name=_('User'))
    role = models.CharField(max_length=16, default='User', verbose_name=_("Role"))
    date_created = models.DateTimeField(auto_now_add=True, verbose_name=_("Date created"))
    date_updated = models.DateTimeField(auto_now=True, verbose_name=_("Date updated"))
    created_by = models.CharField(max_length=128, null=True, verbose_name=_('Created by'))
    # objects = OrgMemberManager()

    class Meta:
        unique_together = [('org', 'user', 'role')]
        db_table = 'orgs_organization_members'

    def __str__(self):
        return '{} | {}'.format(self.user, self.org)
