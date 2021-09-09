from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers

__all__ = [
    'OIDCSettingSerializer', 'KeycloakSettingSerializer',
]


class CommonSettingSerializer(serializers.Serializer):
    # OpenID 公有配置参数 (version <= 1.5.8 或 version >= 1.5.8)
    BASE_SITE_URL = serializers.CharField(
        required=False, allow_null=True, max_length=1024, label=_('Base site url')
    )
    AUTH_OPENID_CLIENT_ID = serializers.CharField(
        required=False, max_length=1024, label=_('Client Id')
    )
    AUTH_OPENID_CLIENT_SECRET = serializers.CharField(
        required=False, max_length=1024,  write_only=True, label=_('Client Secret')
    )
    AUTH_OPENID_SHARE_SESSION = serializers.BooleanField(required=False, label=_('Share session'))
    AUTH_OPENID_IGNORE_SSL_VERIFICATION = serializers.BooleanField(
        required=False, label=_('Ignore ssl verification')
    )


class KeycloakSettingSerializer(CommonSettingSerializer):
    # OpenID 旧配置参数 (version <= 1.5.8 (discarded))
    AUTH_OPENID_KEYCLOAK = serializers.BooleanField(
        label=_("Use Keycloak"), required=False, default=False
    )
    AUTH_OPENID_SERVER_URL = serializers.CharField(
        required=False, max_length=1024, label=_('Server url')
    )
    AUTH_OPENID_REALM_NAME = serializers.CharField(
        required=False, max_length=1024, allow_null=True, label=_('Realm name')
    )


class OIDCSettingSerializer(KeycloakSettingSerializer):
    # OpenID 新配置参数 (version >= 1.5.9)
    AUTH_OPENID = serializers.BooleanField(required=False, label=_('Enable OPENID Auth'))
    AUTH_OPENID_PROVIDER_ENDPOINT = serializers.CharField(
        required=False, max_length=1024, label=_('Provider endpoint')
    )
    AUTH_OPENID_PROVIDER_AUTHORIZATION_ENDPOINT = serializers.CharField(
        required=False, max_length=1024, label=_('Provider auth endpoint')
    )
    AUTH_OPENID_PROVIDER_TOKEN_ENDPOINT = serializers.CharField(
        required=False, max_length=1024, label=_('Provider token endpoint')
    )
    AUTH_OPENID_PROVIDER_JWKS_ENDPOINT = serializers.CharField(
        required=False, max_length=1024, label=_('Provider jwks endpoint')
    )
    AUTH_OPENID_PROVIDER_USERINFO_ENDPOINT = serializers.CharField(
        required=False, max_length=1024, label=_('Provider userinfo endpoint')
    )
    AUTH_OPENID_PROVIDER_END_SESSION_ENDPOINT = serializers.CharField(
        required=False, max_length=1024, label=_('Provider end session endpoint')
    )
    AUTH_OPENID_PROVIDER_SIGNATURE_ALG = serializers.CharField(
        required=False, max_length=1024, label=_('Provider sign alg')
    )
    AUTH_OPENID_PROVIDER_SIGNATURE_KEY = serializers.CharField(
        required=False, max_length=1024, allow_null=True, label=_('Provider sign key')
    )
    AUTH_OPENID_SCOPES = serializers.CharField(required=False, max_length=1024, label=_('Scopes'))
    AUTH_OPENID_ID_TOKEN_MAX_AGE = serializers.IntegerField(
        required=False, label=_('Id token max age')
    )
    AUTH_OPENID_ID_TOKEN_INCLUDE_CLAIMS = serializers.BooleanField(
        required=False, label=_('Id token include claims')
    )
    AUTH_OPENID_USE_STATE = serializers.BooleanField(required=False, label=_('Use state'))
    AUTH_OPENID_USE_NONCE = serializers.BooleanField(required=False, label=_('Use nonce'))
    AUTH_OPENID_ALWAYS_UPDATE_USER = serializers.BooleanField(
        required=False, label=_('Always update user')
    )

