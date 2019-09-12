# ~*~ coding: utf-8 ~*~
import uuid

from django.core.cache import cache
from django.contrib.auth import logout
from django.utils.translation import ugettext as _

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_bulk import BulkModelViewSet

from common.permissions import (
    IsOrgAdmin, IsCurrentUserOrReadOnly, IsOrgAdminOrAppUser,
    CanUpdateDeleteUser,
)
from common.mixins import IDInCacheFilterMixin
from common.utils import get_logger
from orgs.utils import current_org
from .. import serializers
from ..models import User
from ..signals import post_user_create


logger = get_logger(__name__)
__all__ = [
    'UserViewSet', 'UserChangePasswordApi', 'UserUpdateGroupApi',
    'UserResetPasswordApi', 'UserResetPKApi', 'UserUpdatePKApi',
    'UserUnblockPKApi', 'UserProfileApi', 'UserResetOTPApi',
]


class UserViewSet(IDInCacheFilterMixin, BulkModelViewSet):
    filter_fields = ('username', 'email', 'name', 'id')
    search_fields = filter_fields
    queryset = User.objects.exclude(role=User.ROLE_APP)
    serializer_class = serializers.UserSerializer
    permission_classes = (IsOrgAdmin, CanUpdateDeleteUser)

    def send_created_signal(self, users):
        if not isinstance(users, list):
            users = [users]
        for user in users:
            post_user_create.send(self.__class__, user=user)

    def perform_create(self, serializer):
        users = serializer.save()
        if isinstance(users, User):
            users = [users]
        if current_org and current_org.is_real():
            current_org.users.add(*users)
        self.send_created_signal(users)

    def get_queryset(self):
        queryset = current_org.get_org_members().prefetch_related('groups')
        return queryset

    def get_permissions(self):
        if self.action in ["retrieve", "list"]:
            self.permission_classes = (IsOrgAdminOrAppUser,)
        return super().get_permissions()

    def allow_bulk_destroy(self, qs, filtered):
        return False

    def perform_bulk_update(self, serializer):
        # TODO: 需要测试
        users_ids = [
            d.get("id") or d.get("pk") for d in serializer.validated_data
        ]
        users = current_org.get_org_members().filter(id__in=users_ids)
        for user in users:
            self.check_object_permissions(self.request, user)
        return super().perform_bulk_update(serializer)


class UserChangePasswordApi(generics.RetrieveUpdateAPIView):
    permission_classes = (IsOrgAdmin,)
    queryset = User.objects.all()
    serializer_class = serializers.ChangeUserPasswordSerializer

    def perform_update(self, serializer):
        user = self.get_object()
        user.password_raw = serializer.validated_data["password"]
        user.save()


class UserUpdateGroupApi(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = serializers.UserUpdateGroupSerializer
    permission_classes = (IsOrgAdmin,)


class UserResetPasswordApi(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer
    permission_classes = (IsAuthenticated,)

    def perform_update(self, serializer):
        # Note: we are not updating the user object here.
        # We just do the reset-password stuff.
        from ..utils import send_reset_password_mail
        user = self.get_object()
        user.password_raw = str(uuid.uuid4())
        user.save()
        send_reset_password_mail(user)


class UserResetPKApi(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = serializers.UserSerializer
    permission_classes = (IsAuthenticated,)

    def perform_update(self, serializer):
        from ..utils import send_reset_ssh_key_mail
        user = self.get_object()
        user.is_public_key_valid = False
        user.save()
        send_reset_ssh_key_mail(user)


# 废弃
class UserUpdatePKApi(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = serializers.UserPKUpdateSerializer
    permission_classes = (IsCurrentUserOrReadOnly,)

    def perform_update(self, serializer):
        user = self.get_object()
        user.public_key = serializer.validated_data['public_key']
        user.save()


class UserUnblockPKApi(generics.UpdateAPIView):
    queryset = User.objects.all()
    permission_classes = (IsOrgAdmin,)
    serializer_class = serializers.UserSerializer
    key_prefix_limit = "_LOGIN_LIMIT_{}_{}"
    key_prefix_block = "_LOGIN_BLOCK_{}"

    def perform_update(self, serializer):
        user = self.get_object()
        username = user.username if user else ''
        key_limit = self.key_prefix_limit.format(username, '*')
        key_block = self.key_prefix_block.format(username)
        cache.delete_pattern(key_limit)
        cache.delete(key_block)


class UserProfileApi(generics.RetrieveAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = serializers.UserSerializer

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        age = request.session.get_expiry_age()
        request.session.set_expiry(age)
        return super().retrieve(request, *args, **kwargs)


class UserResetOTPApi(generics.RetrieveAPIView):
    queryset = User.objects.all()
    permission_classes = (IsOrgAdmin,)
    serializer_class = serializers.ResetOTPSerializer

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object() if kwargs.get('pk') else request.user
        if user == request.user:
            msg = _("Could not reset self otp, use profile reset instead")
            return Response({"error": msg}, status=401)
        if user.otp_enabled and user.otp_secret_key:
            user.otp_secret_key = ''
            user.save()
            logout(request)
        return Response({"msg": "success"})