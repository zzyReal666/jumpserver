# -*- coding: utf-8 -*-
#
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from common.serializers import AdaptedBulkListSerializer

from ..models import Node, AdminUser
from orgs.mixins import BulkOrgResourceModelSerializer

from .base import AuthSerializer


class AdminUserSerializer(BulkOrgResourceModelSerializer):
    """
    管理用户
    """
    password = serializers.CharField(
        required=False, write_only=True, label=_('Password')
    )

    class Meta:
        list_serializer_class = AdaptedBulkListSerializer
        model = AdminUser
        fields = [
            'id', 'name', 'username', 'password', 'comment',
            'connectivity_amount', 'assets_amount',
            'date_created', 'date_updated', 'created_by',
        ]

        extra_kwargs = {
            'date_created': {'read_only': True},
            'date_updated': {'read_only': True},
            'created_by': {'read_only': True},
            'assets_amount': {'label': _('Asset')},
            'connectivity_amount': {'label': _('Connectivity')},
        }


class AdminUserAuthSerializer(AuthSerializer):

    class Meta:
        model = AdminUser
        fields = ['password', 'private_key']


class ReplaceNodeAdminUserSerializer(serializers.ModelSerializer):
    """
    管理用户更新关联到的集群
    """
    nodes = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Node.objects.all()
    )

    class Meta:
        model = AdminUser
        fields = ['id', 'nodes']


class TaskIDSerializer(serializers.Serializer):
    task = serializers.CharField(read_only=True)
