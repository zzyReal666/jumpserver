# -*- coding: utf-8 -*-
#
import time

from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from rest_framework.views import APIView, Response
from rest_framework import status
from rest_framework.generics import (
    ListAPIView, get_object_or_404
)

from orgs.utils import tmp_to_root_org
from applications.models import Application
from perms.utils.application.permission import (
    get_application_system_user_ids,
    validate_permission,
)
from .mixin import RoleAdminMixin, RoleUserMixin
from perms.hands import User, SystemUser
from perms import serializers


__all__ = [
    'UserGrantedApplicationSystemUsersApi',
    'MyGrantedApplicationSystemUsersApi',
    'ValidateUserApplicationPermissionApi'
]


class GrantedApplicationSystemUsersMixin(ListAPIView):
    serializer_class = serializers.ApplicationSystemUserSerializer
    only_fields = serializers.ApplicationSystemUserSerializer.Meta.only_fields
    user: None

    def get_application_system_user_ids(self, application):
        return get_application_system_user_ids(self.user, application)

    def get_queryset(self):
        application_id = self.kwargs.get('application_id')
        application = get_object_or_404(Application, id=application_id)
        system_user_ids = self.get_application_system_user_ids(application)
        system_users = SystemUser.objects.filter(id__in=system_user_ids)\
            .only(*self.only_fields).order_by('priority')
        return system_users


class UserGrantedApplicationSystemUsersApi(RoleAdminMixin, GrantedApplicationSystemUsersMixin):
    pass


class MyGrantedApplicationSystemUsersApi(RoleUserMixin, GrantedApplicationSystemUsersMixin):
    pass


@method_decorator(tmp_to_root_org(), name='get')
class ValidateUserApplicationPermissionApi(APIView):
    rbac_perms = {
        'GET': 'ops.view_applicationpermission'
    }

    def get(self, request, *args, **kwargs):
        user_id = request.query_params.get('user_id', '')
        application_id = request.query_params.get('application_id', '')
        system_user_id = request.query_params.get('system_user_id', '')

        data = {
            'has_permission': False,
            'expire_at': int(time.time()),
            'actions': []
        }
        if not all((user_id, application_id, system_user_id)):
            return Response(data)

        user = User.objects.get(id=user_id)
        application = Application.objects.get(id=application_id)
        system_user = SystemUser.objects.get(id=system_user_id)
        has_perm, actions, expire_at = validate_permission(user, application, system_user)
        status_code = status.HTTP_200_OK if has_perm else status.HTTP_403_FORBIDDEN
        data = {
            'has_permission': has_perm,
            'expire_at': int(expire_at),
            'actions': actions
        }
        return Response(data, status=status_code)
