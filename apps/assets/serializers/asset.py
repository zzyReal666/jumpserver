# -*- coding: utf-8 -*-
#
from rest_framework import serializers
from rest_framework_bulk.serializers import BulkListSerializer

from common.mixins import BulkSerializerMixin
from ..models import Asset, Node
from .system_user import AssetSystemUserSerializer

__all__ = [
    'AssetSerializer', 'AssetGrantedSerializer', 'MyAssetGrantedSerializer',
]


class NodeTMPSerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()
    assets_amount = serializers.SerializerMethodField()

    class Meta:
        model = Node
        fields = ['id', 'key', 'value', 'parent', 'assets_amount', 'is_node']
        list_serializer_class = BulkListSerializer

    @staticmethod
    def get_parent(obj):
        return obj.parent.id

    @staticmethod
    def get_assets_amount(obj):
        return obj.get_all_assets().count()

    def get_fields(self):
        fields = super().get_fields()
        field = fields["key"]
        field.required = False
        return fields


class AssetSerializer(BulkSerializerMixin, serializers.ModelSerializer):
    """
    资产的数据结构
    """

    class Meta:
        model = Asset
        list_serializer_class = BulkListSerializer
        fields = '__all__'
        validators = []  # If not set to [], partial bulk update will be error

    def get_field_names(self, declared_fields, info):
        fields = super().get_field_names(declared_fields, info)
        fields.extend([
            'hardware_info', 'is_connective',
        ])
        return fields


class AssetGrantedSerializer(serializers.ModelSerializer):
    """
    被授权资产的数据结构
    """
    system_users_granted = AssetSystemUserSerializer(many=True, read_only=True)
    system_users_join = serializers.SerializerMethodField()
    nodes = NodeTMPSerializer(many=True, read_only=True)

    class Meta:
        model = Asset
        fields = (
            "id", "hostname", "ip", "port", "system_users_granted",
            "is_active", "system_users_join", "os", 'domain', "nodes",
            "platform", "comment"
        )

    @staticmethod
    def get_system_users_join(obj):
        system_users = [s.username for s in obj.system_users_granted]
        return ', '.join(system_users)


class MyAssetGrantedSerializer(AssetGrantedSerializer):
    """
    普通用户获取授权的资产定义的数据结构
    """

    class Meta:
        model = Asset
        fields = (
            "id", "hostname", "system_users_granted",
            "is_active", "system_users_join",
            "os", "platform", "comment",
        )
