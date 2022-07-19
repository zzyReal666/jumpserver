# -*- coding: utf-8 -*-
#
import time

from django.conf import settings
from rest_framework import permissions

from authentication.const import ConfirmType
from common.exceptions import UserConfirmRequired
from orgs.utils import tmp_to_root_org
from authentication.models import ConnectionToken
from common.utils import get_object_or_none


class IsValidUser(permissions.IsAuthenticated, permissions.BasePermission):
    """Allows access to valid user, is active and not expired"""

    def has_permission(self, request, view):
        return super(IsValidUser, self).has_permission(request, view) \
               and request.user.is_valid


class IsValidUserOrConnectionToken(IsValidUser):

    def has_permission(self, request, view):
        return super(IsValidUserOrConnectionToken, self).has_permission(request, view) \
               or self.is_valid_connection_token(request)

    @staticmethod
    def is_valid_connection_token(request):
        token_id = request.query_params.get('token')
        if not token_id:
            return False
        with tmp_to_root_org():
            token = get_object_or_none(ConnectionToken, id=token_id)
        return token and token.is_valid


class OnlySuperUser(IsValidUser):
    def has_permission(self, request, view):
        return super().has_permission(request, view) \
               and request.user.is_superuser


class WithBootstrapToken(permissions.BasePermission):
    def has_permission(self, request, view):
        authorization = request.META.get('HTTP_AUTHORIZATION', '')
        if not authorization:
            return False
        request_bootstrap_token = authorization.split()[-1]
        return settings.BOOTSTRAP_TOKEN == request_bootstrap_token


class UserConfirmation(permissions.BasePermission):
    ttl = 60 * 5
    min_level = 1
    confirm_type = ConfirmType.ReLogin

    def has_permission(self, request, view):
        if not settings.SECURITY_VIEW_AUTH_NEED_MFA:
            return True

        confirm_level = request.session.get('CONFIRM_LEVEL')
        confirm_time = request.session.get('CONFIRM_TIME')

        if not confirm_level or not confirm_time or \
                confirm_level < self.min_level or \
                confirm_time < time.time() - self.ttl:
            raise UserConfirmRequired(code=self.confirm_type)
        return True

    @classmethod
    def require(cls, confirm_type=ConfirmType.ReLogin, ttl=300):
        min_level = ConfirmType.values.index(confirm_type) + 1
        name = 'UserConfirmationLevel{}TTL{}'.format(min_level, ttl)
        return type(name, (cls,), {'min_level': min_level, 'ttl': ttl, 'confirm_type': confirm_type})
