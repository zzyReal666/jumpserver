# -*- coding: utf-8 -*-
#
import time

from django.conf import settings
from rest_framework import permissions

from authentication.const import ConfirmType
from common.exceptions import UserConfirmRequired


class IsValidUser(permissions.IsAuthenticated, permissions.BasePermission):
    """Allows access to valid user, is active and not expired"""

    def has_permission(self, request, view):
        return super(IsValidUser, self).has_permission(request, view) \
               and request.user.is_valid


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
    ttl = 300
    min_level = 1
    confirm_type = ConfirmType.ReLogin

    def has_permission(self, request, view):
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
