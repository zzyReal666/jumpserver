# -*- coding: utf-8 -*-
#

from rest_framework import serializers

from common.fields import StringManyToManyField
from .models import AssetPermission
from assets.models import Node
from assets.serializers import AssetGrantedSerializer


class AssetPermissionCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetPermission
        exclude = ('created_by', 'date_created')


class AssetPermissionListSerializer(serializers.ModelSerializer):
    users = StringManyToManyField(many=True, read_only=True)
    user_groups = StringManyToManyField(many=True, read_only=True)
    assets = StringManyToManyField(many=True, read_only=True)
    nodes = StringManyToManyField(many=True, read_only=True)
    system_users = StringManyToManyField(many=True, read_only=True)
    inherit = serializers.SerializerMethodField()

    class Meta:
        model = AssetPermission
        fields = '__all__'

    @staticmethod
    def get_inherit(obj):
        if hasattr(obj, 'inherit'):
            return obj.inherit
        else:
            return None


class AssetPermissionUpdateUserSerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetPermission
        fields = ['id', 'users']


class AssetPermissionUpdateAssetSerializer(serializers.ModelSerializer):

    class Meta:
        model = AssetPermission
        fields = ['id', 'assets']


class AssetPermissionNodeSerializer(serializers.ModelSerializer):
    asset = AssetGrantedSerializer(required=False)
    assets_amount = serializers.SerializerMethodField()

    tree_id = serializers.SerializerMethodField()
    tree_parent = serializers.SerializerMethodField()

    class Meta:
        model = Node
        fields = [
            'id', 'key', 'value', 'asset', 'is_node', 'org_id',
            'tree_id', 'tree_parent', 'assets_amount',
        ]

    @staticmethod
    def get_assets_amount(obj):
        return obj.assets_amount

    @staticmethod
    def get_tree_id(obj):
        return obj.key

    @staticmethod
    def get_tree_parent(obj):
        return obj.parent_key
