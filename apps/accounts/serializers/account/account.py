from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

from assets.models import Asset
from accounts.const import SecretType, Source
from accounts.models import Account, AccountTemplate
from accounts.tasks import push_accounts_to_assets
from common.serializers.fields import ObjectRelatedField, LabeledChoiceField
from common.serializers import SecretReadableMixin, BulkModelSerializer
from .base import BaseAccountSerializer


class AccountSerializerCreateMixin(BulkModelSerializer):
    template = serializers.UUIDField(
        required=False, allow_null=True, write_only=True,
        label=_('Account template')
    )
    push_now = serializers.BooleanField(
        default=False, label=_("Push now"), write_only=True
    )
    has_secret = serializers.BooleanField(label=_("Has secret"), read_only=True)

    @staticmethod
    def validate_template(value):
        try:
            return AccountTemplate.objects.get(id=value)
        except AccountTemplate.DoesNotExist:
            raise serializers.ValidationError(_('Account template not found'))

    @staticmethod
    def replace_attrs(account_template: AccountTemplate, attrs: dict):
        exclude_fields = [
            '_state', 'org_id', 'id', 'date_created',
            'date_updated'
        ]
        template_attrs = {
            k: v for k, v in account_template.__dict__.items()
            if k not in exclude_fields
        }
        for k, v in template_attrs.items():
            attrs.setdefault(k, v)

    def validate(self, attrs):
        account_template = attrs.pop('template', None)
        if account_template:
            self.replace_attrs(account_template, attrs)
        self.push_now = attrs.pop('push_now', False)
        return super().validate(attrs)

    def create(self, validated_data):
        instance = super().create(validated_data)
        if self.push_now:
            push_accounts_to_assets.delay([instance.id], [instance.asset_id])
        return instance


class AccountAssetSerializer(serializers.ModelSerializer):
    platform = ObjectRelatedField(read_only=True)

    class Meta:
        model = Asset
        fields = ['id', 'name', 'address', 'platform']

    def to_internal_value(self, data):
        if isinstance(data, dict):
            i = data.get('id')
        else:
            i = data

        try:
            return Asset.objects.get(id=i)
        except Asset.DoesNotExist:
            raise serializers.ValidationError(_('Asset not found'))


class AccountSerializer(AccountSerializerCreateMixin, BaseAccountSerializer):
    asset = AccountAssetSerializer(label=_('Asset'))
    source = LabeledChoiceField(choices=Source.choices, label=_("Source"), read_only=True)
    su_from = ObjectRelatedField(
        required=False, queryset=Account.objects, allow_null=True, allow_empty=True,
        label=_('Su from'), attrs=('id', 'name', 'username')
    )

    class Meta(BaseAccountSerializer.Meta):
        model = Account
        fields = BaseAccountSerializer.Meta.fields \
                 + ['su_from', 'version', 'asset'] \
                 + ['template', 'push_now', 'source']
        extra_kwargs = {
            **BaseAccountSerializer.Meta.extra_kwargs,
            'name': {'required': False, 'allow_null': True},
        }

    def validate_name(self, value):
        if not value:
            value = self.initial_data.get('username')
        return value

    @classmethod
    def setup_eager_loading(cls, queryset):
        """ Perform necessary eager loading of data. """
        queryset = queryset.prefetch_related('asset', 'asset__platform')
        return queryset


class AccountSecretSerializer(SecretReadableMixin, AccountSerializer):
    class Meta(AccountSerializer.Meta):
        extra_kwargs = {
            'secret': {'write_only': False},
        }


class AccountHistorySerializer(serializers.ModelSerializer):
    secret_type = LabeledChoiceField(choices=SecretType.choices, label=_('Secret type'))

    class Meta:
        model = Account.history.model
        fields = ['id', 'secret', 'secret_type', 'version', 'history_date', 'history_user']
        read_only_fields = fields


class AccountTaskSerializer(serializers.Serializer):
    ACTION_CHOICES = (
        ('test', 'test'),
    )
    action = serializers.ChoiceField(choices=ACTION_CHOICES, write_only=True)
    task = serializers.CharField(read_only=True)
