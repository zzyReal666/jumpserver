# -*- coding: utf-8 -*-
#
from functools import partial
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from common.mixins import CommonBulkSerializerMixin
from common.validators import PhoneValidator
from rbac.permissions import RBACPermission
from rbac.models import OrgRoleBinding, SystemRoleBinding
from ..models import User
from ..const import PasswordStrategy
from rbac.models import Role
from rbac.builtin import BuiltinRole

__all__ = [
    'UserSerializer', 'MiniUserSerializer',
    'InviteSerializer', 'ServiceAccountSerializer',
]


class RolesSerializerMixin(serializers.Serializer):
    system_roles = serializers.ManyRelatedField(
        child_relation=serializers.PrimaryKeyRelatedField(queryset=Role.system_roles),
        label=_('System roles'),
    )
    org_roles = serializers.ManyRelatedField(
        child_relation=serializers.PrimaryKeyRelatedField(queryset=Role.org_roles),
        label=_('Org roles'),
    )
    system_roles_display = serializers.SerializerMethodField(label=_('System roles'))
    org_roles_display = serializers.SerializerMethodField(label=_('Org roles'))

    @staticmethod
    def get_system_roles_display(user):
        return user.system_roles.display

    @staticmethod
    def get_org_roles_display(user):
        return user.org_roles.display

    def pop_roles_if_need(self, fields):
        request = self.context.get('request')
        view = self.context.get('view')

        if not all([request, view, hasattr(view, 'action')]):
            return fields
        if request.user.is_anonymous:
            return fields

        action = view.action or 'list'
        model_cls_field_mapper = {
            SystemRoleBinding: ['system_roles', 'system_roles_display'],
            OrgRoleBinding: ['org_roles', 'system_roles_display']
        }

        for model_cls, fields_names in model_cls_field_mapper.items():
            perms = RBACPermission.parse_action_model_perms(action, model_cls)
            if request.user.has_perms(perms):
                continue
            # 没有权限就去掉
            for field_name in fields_names:
                fields.pop(field_name, None)
        return fields

    def get_fields(self):
        fields = super().get_fields()
        self.pop_roles_if_need(fields)
        return fields


class UserSerializer(RolesSerializerMixin, CommonBulkSerializerMixin, serializers.ModelSerializer):
    password_strategy = serializers.ChoiceField(
        choices=PasswordStrategy.choices, default=PasswordStrategy.email, required=False,
        write_only=True, label=_('Password strategy')
    )
    mfa_enabled = serializers.BooleanField(read_only=True, label=_('MFA enabled'))
    mfa_force_enabled = serializers.BooleanField(read_only=True, label=_('MFA force enabled'))
    mfa_level_display = serializers.ReadOnlyField(
        source='get_mfa_level_display', label=_('MFA level display')
    )
    login_blocked = serializers.BooleanField(read_only=True, label=_('Login blocked'))
    is_expired = serializers.BooleanField(read_only=True, label=_('Is expired'))
    can_public_key_auth = serializers.ReadOnlyField(
        source='can_use_ssh_key_login', label=_('Can public key authentication')
    )
    # Todo: 这里看看该怎么搞
    # can_update = serializers.SerializerMethodField(label=_('Can update'))
    # can_delete = serializers.SerializerMethodField(label=_('Can delete'))
    custom_m2m_fields = ('system_roles', 'org_roles')

    class Meta:
        model = User
        # mini 是指能识别对象的最小单元
        fields_mini = ['id', 'name', 'username']
        # 只能写的字段, 这个虽然无法在框架上生效，但是更多对我们是提醒
        fields_write_only = [
            'password', 'public_key',
        ]
        # small 指的是 不需要计算的直接能从一张表中获取到的数据
        fields_small = fields_mini + fields_write_only + [
            'email', 'wechat', 'phone', 'mfa_level', 'source', 'source_display',
            'can_public_key_auth', 'need_update_password',
            'mfa_enabled', 'is_service_account', 'is_valid', 'is_expired', 'is_active',  # 布尔字段
            'date_expired', 'date_joined', 'last_login',  # 日期字段
            'created_by', 'comment',  # 通用字段
            'is_wecom_bound', 'is_dingtalk_bound', 'is_feishu_bound', 'is_otp_secret_key_bound',
            'wecom_id', 'dingtalk_id', 'feishu_id'
        ]
        # 包含不太常用的字段，可以没有
        fields_verbose = fields_small + [
            'mfa_level_display', 'mfa_force_enabled', 'is_first_login',
            'date_password_last_updated', 'avatar_url',
        ]
        # 外键的字段
        fields_fk = []
        # 多对多字段
        fields_m2m = [
            'groups', 'groups_display', 'system_roles', 'org_roles',
            'system_roles_display', 'org_roles_display'
        ]
        # 在serializer 上定义的字段
        fields_custom = ['login_blocked', 'password_strategy']
        fields = fields_verbose + fields_fk + fields_m2m + fields_custom

        read_only_fields = [
            'date_joined', 'last_login', 'created_by', 'is_first_login',
            'wecom_id', 'dingtalk_id', 'feishu_id'
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': False, 'allow_null': True, 'allow_blank': True},
            'public_key': {'write_only': True},
            'is_first_login': {'label': _('Is first login'), 'read_only': True},
            'is_valid': {'label': _('Is valid')},
            'is_service_account':  {'label': _('Is service account')},
            'is_expired': {'label': _('Is expired')},
            'avatar_url': {'label': _('Avatar url')},
            'created_by': {'read_only': True, 'allow_blank': True},
            'groups_display': {'label': _('Groups name')},
            'source_display': {'label': _('Source name')},
            'org_role_display': {'label': _('Organization role name')},
            'role_display': {'label': _('Super role name')},
            'total_role_display': {'label': _('Total role name')},
            'role': {'default': "User"},
            'is_wecom_bound': {'label': _('Is wecom bound')},
            'is_dingtalk_bound': {'label': _('Is dingtalk bound')},
            'is_feishu_bound': {'label': _('Is feishu bound')},
            'is_otp_secret_key_bound': {'label': _('Is OTP bound')},
            'phone': {'validators': [PhoneValidator()]},
            'system_role_display': {'label': _('System role name')},
        }

    def validate_password(self, password):
        password_strategy = self.initial_data.get('password_strategy')
        if self.instance is None and password_strategy != PasswordStrategy.custom:
            # 创建用户，使用邮件设置密码
            return
        if self.instance and not password:
            # 更新用户, 未设置密码
            return
        return password

    @staticmethod
    def change_password_to_raw(attrs):
        password = attrs.pop('password', None)
        if password:
            attrs['password_raw'] = password
        return attrs

    @staticmethod
    def clean_auth_fields(attrs):
        for field in ('password', 'public_key'):
            value = attrs.get(field)
            if not value:
                attrs.pop(field, None)
        return attrs

    def validate(self, attrs):
        attrs = self.change_password_to_raw(attrs)
        attrs = self.clean_auth_fields(attrs)
        attrs.pop('password_strategy', None)
        return attrs
    # Todo: 不知道怎么优化呢
    # def get_can_update(self, obj):
    #     return CanUpdateDeleteUser.has_update_object_permission(
    #         self.context['request'], self.context['view'], obj
    #     )
    #
    # def get_can_delete(self, obj):
    #     return CanUpdateDeleteUser.has_delete_object_permission(
    #         self.context['request'], self.context['view'], obj
    #     )

    def save_and_set_custom_m2m_fields(self, validated_data, save_handler):
        m2m_values = {
            f: validated_data.pop(f, None)
            for f in self.custom_m2m_fields
        }
        instance = save_handler(validated_data)
        for field_name, value in m2m_values.items():
            if value is None:
                continue
            field = getattr(instance, field_name)
            field.set(value)
        return instance

    def validate_is_active(self, is_active):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return is_active

        user = request.user
        if user.id == self.instance.id and not is_active:
            # 用户自己不能禁用启用自己
            raise serializers.ValidationError("Cannot inactive self")
        return is_active

    def update(self, instance, validated_data):
        save_handler = partial(super().update, instance)
        instance = self.save_and_set_custom_m2m_fields(validated_data, save_handler)
        return instance

    def create(self, validated_data):
        save_handler = super().create
        instance = self.save_and_set_custom_m2m_fields(validated_data, save_handler)
        return instance


class UserRetrieveSerializer(UserSerializer):
    login_confirm_settings = serializers.PrimaryKeyRelatedField(
        read_only=True, source='login_confirm_setting.reviewers', many=True
    )

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['login_confirm_settings']


class MiniUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = UserSerializer.Meta.fields_mini


class InviteSerializer(RolesSerializerMixin, serializers.Serializer):
    users = serializers.PrimaryKeyRelatedField(
        queryset=User.get_nature_users(), many=True, label=_('Select users'),
        help_text=_('为了安全，仅会返回 3 个用户，请输入名称精准匹配')
    )
    system_roles = None
    system_roles_display = None
    org_roles_display = None


class ServiceAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'access_key']
        read_only_fields = ['access_key']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from authentication.serializers import AccessKeySerializer
        self.fields['access_key'] = AccessKeySerializer(read_only=True)

    def get_username(self):
        return self.initial_data.get('name')

    def get_email(self):
        name = self.initial_data.get('name')
        return '{}@serviceaccount.local'.format(name)

    def validate_name(self, name):
        email = self.get_email()
        username = self.get_username()
        if self.instance:
            users = User.objects.exclude(id=self.instance.id)
        else:
            users = User.objects.all()
        if users.filter(email=email) or users.filter(username=username):
            raise serializers.ValidationError(_('name not unique'), code='unique')
        return name

    def create(self, validated_data):
        user, ak = User.create_service_account(validated_data['name'], validated_data['comment'])
        return user
