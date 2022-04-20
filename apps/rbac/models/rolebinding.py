from django.utils.translation import gettext_lazy as _
from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from rest_framework.serializers import ValidationError

from common.db.models import JMSModel
from common.utils import lazyproperty
from orgs.utils import current_org, tmp_to_root_org
from .role import Role
from ..const import Scope

__all__ = ['RoleBinding', 'SystemRoleBinding', 'OrgRoleBinding']


class RoleBindingManager(models.Manager):
    def get_queryset(self):
        queryset = super(RoleBindingManager, self).get_queryset()
        q = Q(scope=Scope.system, org__isnull=True)
        if not current_org.is_root():
            q |= Q(org_id=current_org.id, scope=Scope.org)
        queryset = queryset.filter(q)
        return queryset

    def root_all(self):
        queryset = super().get_queryset()
        if current_org.is_root():
            return queryset
        return self.get_queryset()


class RoleBinding(JMSModel):
    Scope = Scope
    """ 定义 用户-角色 关系 """
    scope = models.CharField(
        max_length=128, choices=Scope.choices, default=Scope.system,
        verbose_name=_('Scope')
    )
    user = models.ForeignKey(
        'users.User', related_name='role_bindings', on_delete=models.CASCADE, verbose_name=_('User')
    )
    role = models.ForeignKey(
        Role, related_name='role_bindings', on_delete=models.CASCADE, verbose_name=_('Role')
    )
    org = models.ForeignKey(
        'orgs.Organization', related_name='role_bindings', blank=True, null=True,
        on_delete=models.CASCADE, verbose_name=_('Organization')
    )
    objects = RoleBindingManager()

    class Meta:
        verbose_name = _('Role binding')
        unique_together = [
            ('user', 'role', 'org'),
        ]

    def __str__(self):
        display = '{user} & {role}'.format(user=self.user, role=self.role)
        if self.org:
            display += ' | {org}'.format(org=self.org)
        return display

    @property
    def org_name(self):
        if self.org:
            return self.org.name
        return ''

    def save(self, *args, **kwargs):
        self.scope = self.role.scope
        self.clean()
        return super().save(*args, **kwargs)

    @classmethod
    def get_user_perms(cls, user):
        roles = cls.get_user_roles(user)
        return Role.get_roles_perms(roles)

    @classmethod
    def get_role_users(cls, role):
        from users.models import User
        bindings = cls.objects.root_all().filter(role=role, scope=role.scope)
        user_ids = bindings.values_list('user', flat=True).distinct()
        return User.objects.filter(id__in=user_ids)

    @classmethod
    def get_user_roles(cls, user):
        bindings = cls.objects.filter(user=user)
        roles_id = bindings.values_list('role', flat=True).distinct()
        return Role.objects.filter(id__in=roles_id)

    @lazyproperty
    def user_display(self):
        return self.user.name

    @lazyproperty
    def role_display(self):
        return self.role.display_name

    def is_scope_org(self):
        return self.scope == Scope.org

    @classmethod
    def get_user_has_the_perm_orgs(cls, perm, user):
        from orgs.models import Organization

        roles = Role.get_roles_by_perm(perm)
        with tmp_to_root_org():
            bindings = list(cls.objects.root_all().filter(role__in=roles, user=user))

        system_bindings = [b for b in bindings if b.scope == Role.Scope.system.value]
        # 工作台仅限于自己加入的组织
        if perm == 'rbac.view_workbench':
            all_orgs = user.orgs.all()
        else:
            all_orgs = Organization.objects.all()

        # 有系统级别的绑定，就代表在所有组织有这个权限
        if system_bindings:
            orgs = all_orgs
        else:
            org_ids = [b.org.id for b in bindings if b.org]
            orgs = all_orgs.filter(id__in=org_ids)

        # 全局组织
        if orgs and perm != 'rbac.view_workbench' and user.has_perm('orgs.view_rootorg'):
            orgs = [Organization.root(), *list(orgs)]
        return orgs


class OrgRoleBindingManager(RoleBindingManager):
    def get_queryset(self):
        queryset = super(RoleBindingManager, self).get_queryset()
        if current_org.is_root():
            queryset = queryset.none()
        else:
            queryset = queryset.filter(org_id=current_org.id, scope=Scope.org)
        return queryset


class OrgRoleBinding(RoleBinding):
    objects = OrgRoleBindingManager()

    def save(self, *args, **kwargs):
        self.org_id = current_org.id
        self.scope = Scope.org
        return super().save(*args, **kwargs)

    def delete(self, **kwargs):
        has_other_role = self.__class__.objects \
            .filter(user=self.user, scope=self.scope) \
            .exclude(id=self.id) \
            .exists()
        if not has_other_role:
            error = _('User last role in org, can not be delete, '
                      'you can remove user from org instead')
            raise ValidationError({'error': error})
        return super().delete(**kwargs)

    class Meta:
        proxy = True
        verbose_name = _('Organization role binding')


class SystemRoleBindingManager(RoleBindingManager):
    def get_queryset(self):
        queryset = super(RoleBindingManager, self).get_queryset()\
            .filter(scope=Scope.system)
        return queryset


class SystemRoleBinding(RoleBinding):
    objects = SystemRoleBindingManager()

    class Meta:
        proxy = True
        verbose_name = _('System role binding')

    def save(self, *args, **kwargs):
        self.scope = Scope.system
        return super().save(*args, **kwargs)

    def clean(self):
        kwargs = dict(role=self.role, user=self.user, scope=self.scope)
        exists = self.__class__.objects.filter(**kwargs).exists()
        if exists:
            msg = "Duplicate for key 'role_user' of system role binding, {}_{}".format(
                self.role.id, self.user.id
            )
            raise ValidationError(msg)
