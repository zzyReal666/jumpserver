from django.db.models import Q, Count
from django.utils.translation import ugettext as _
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied

from common.api import JMSModelViewSet
from orgs.utils import current_org
from .permission import PermissionViewSet
from ..filters import RoleFilter
from ..models import Role, SystemRole, OrgRole, RoleBinding
from ..serializers import RoleSerializer, RoleUserSerializer

__all__ = [
    'RoleViewSet', 'SystemRoleViewSet', 'OrgRoleViewSet',
    'SystemRolePermissionsViewSet', 'OrgRolePermissionsViewSet',
]


class RoleViewSet(JMSModelViewSet):
    queryset = Role.objects.all()
    ordering = ('-builtin', 'scope', 'name')
    serializer_classes = {
        'default': RoleSerializer,
        'users': RoleUserSerializer,
    }
    filterset_class = RoleFilter
    search_fields = ('name', 'scope', 'builtin')
    rbac_perms = {
        'users': 'rbac.view_rolebinding'
    }

    def perform_destroy(self, instance):
        from orgs.utils import tmp_to_root_org
        if instance.builtin:
            error = _("Internal role, can't be destroy")
            raise PermissionDenied(error)

        with tmp_to_root_org():
            if instance.users.count() >= 1:
                error = _("The role has been bound to users, can't be destroy")
                raise PermissionDenied(error)
        return super().perform_destroy(instance)

    def perform_create(self, serializer):
        super(RoleViewSet, self).perform_create(serializer)
        self.set_permissions_if_need(serializer.instance)

    def set_permissions_if_need(self, instance):
        if not isinstance(instance, Role):
            return
        clone_from = self.request.query_params.get('clone_from')
        if not clone_from:
            return
        clone = Role.objects.filter(id=clone_from).first()
        if not clone:
            return
        instance.permissions.set(clone.get_permissions())

    @staticmethod
    def set_users_amount(queryset):
        """设置角色的用户绑定数量，以减少查询"""
        org_id = current_org.id
        q = Q(role__scope=Role.Scope.system) | Q(role__scope=Role.Scope.org, org_id=org_id)
        role_bindings = RoleBinding.objects.filter(q).values_list('role_id').annotate(user_count=Count('user_id'))
        role_user_amount_mapper = {role_id: user_count for role_id, user_count in role_bindings}
        queryset = queryset.annotate(permissions_amount=Count('permissions'))
        queryset = list(queryset)
        for role in queryset:
            role.users_amount = role_user_amount_mapper.get(role.id, 0)
        return queryset

    def paginate_queryset(self, queryset):
        page_queryset = super().paginate_queryset(queryset)  # 返回是 list 对象
        page_queryset_ids = [str(i.id) for i in page_queryset]
        queryset = queryset.filter(id__in=page_queryset_ids)
        queryset = self.set_users_amount(queryset)
        return queryset

    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.builtin:
            error = _("Internal role, can't be update")
            raise PermissionDenied(error)
        return super().perform_update(serializer)

    @action(methods=['GET'], detail=True)
    def users(self, *args, **kwargs):
        role = self.get_object()
        queryset = role.users
        return self.get_paginated_response_from_queryset(queryset)


class SystemRoleViewSet(RoleViewSet):
    perm_model = SystemRole

    def get_queryset(self):
        return super().get_queryset().filter(scope='system')


class OrgRoleViewSet(RoleViewSet):
    perm_model = OrgRole

    def get_queryset(self):
        return super().get_queryset().filter(scope='org')


class BaseRolePermissionsViewSet(PermissionViewSet):
    model = None
    role_pk = None
    filterset_fields = []
    http_method_names = ['get', 'option']
    check_disabled = False

    def get_queryset(self):
        role_id = self.kwargs.get(self.role_pk)
        if not role_id:
            return self.model.objects.none()

        role = self.model.objects.get(id=role_id)
        self.scope = role.scope
        self.check_disabled = role.builtin
        queryset = role.get_permissions() \
            .prefetch_related('content_type')
        return queryset


# Sub view set
class SystemRolePermissionsViewSet(BaseRolePermissionsViewSet):
    role_pk = 'system_role_pk'
    model = SystemRole
    rbac_perms = (
        ('get_tree', 'rbac.view_permission'),
    )


# Sub view set
class OrgRolePermissionsViewSet(BaseRolePermissionsViewSet):
    role_pk = 'org_role_pk'
    model = OrgRole
    rbac_perms = (
        ('get_tree', 'rbac.view_permission'),
    )
