from rest_framework import serializers

from ..models import SystemUser


class SystemUserSerializer(serializers.ModelSerializer):
    """
    系统用户
    """
    unreachable_amount = serializers.SerializerMethodField()
    reachable_amount = serializers.SerializerMethodField()
    unreachable_assets = serializers.SerializerMethodField()
    reachable_assets = serializers.SerializerMethodField()
    assets_amount = serializers.SerializerMethodField()

    class Meta:
        model = SystemUser
        exclude = ('_password', '_private_key', '_public_key')

    @staticmethod
    def get_unreachable_assets(obj):
        return obj.unreachable_assets

    @staticmethod
    def get_reachable_assets(obj):
        return obj.reachable_assets

    def get_unreachable_amount(self, obj):
        return len(self.get_unreachable_assets(obj))

    def get_reachable_amount(self, obj):
        return len(self.get_reachable_assets(obj))

    @staticmethod
    def get_assets_amount(obj):
        return len(obj.assets)


class SystemUserAuthSerializer(serializers.ModelSerializer):
    """
    系统用户认证信息
    """
    password = serializers.CharField(max_length=1024)
    private_key = serializers.CharField(max_length=4096)

    class Meta:
        model = SystemUser
        fields = [
            "id", "name", "username", "protocol",
            "password", "private_key",
        ]


class AssetSystemUserSerializer(serializers.ModelSerializer):
    """
    查看授权的资产系统用户的数据结构，这个和AssetSerializer不同，字段少
    """
    class Meta:
        model = SystemUser
        fields = ('id', 'name', 'username', 'priority', 'protocol',  'comment',)


class SystemUserSimpleSerializer(serializers.ModelSerializer):
    """
    系统用户最基本信息的数据结构
    """
    class Meta:
        model = SystemUser
        fields = ('id', 'name', 'username')