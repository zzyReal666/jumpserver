# -*- coding: utf-8 -*-
#

from django.dispatch import receiver
from django_auth_ldap.backend import populate_user
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django_cas_ng.signals import cas_user_authenticated
from django.db.models.signals import post_save

from jms_oidc_rp.signals import openid_create_or_update_user

from authentication.backends.saml2.signals import saml2_create_or_update_user
from common.utils import get_logger
from .signals import post_user_create
from .models import User, UserPasswordHistory


logger = get_logger(__file__)


def user_authenticated_handle(user, created, source, attrs=None, **kwargs):
    if created and settings.ONLY_ALLOW_EXIST_USER_AUTH:
        user.delete()
        raise PermissionDenied(f'Not allow non-exist user auth: {user.username}')
    if created:
        user.source = source
        user.save()
    elif not created and settings.AUTH_SAML2_ALWAYS_UPDATE_USER:
        attr_whitelist = ('user', 'username', 'email', 'phone', 'comment')
        logger.debug(
            "Receive saml2 user updated signal: {}, "
            "Update user info: {},"
            "(Update only properties in the whitelist. [{}])"
            "".format(user, str(attrs), ','.join(attr_whitelist))
        )
        if attrs is not None:
            for key, value in attrs.items():
                if key in attr_whitelist and value:
                    setattr(user, key, value)
            user.save()


@receiver(post_save, sender=User)
def save_passwd_change(sender, instance: User, **kwargs):
    passwds = UserPasswordHistory.objects.filter(user=instance).order_by('-date_created')\
                  .values_list('password', flat=True)[:int(settings.OLD_PASSWORD_HISTORY_LIMIT_COUNT)]

    for p in passwds:
        if instance.password == p:
            break
    else:
        UserPasswordHistory.objects.create(
            user=instance, password=instance.password,
            date_created=instance.date_password_last_updated
        )


@receiver(post_user_create)
def on_user_create(sender, user=None, **kwargs):
    logger.debug("Receive user `{}` create signal".format(user.name))
    from .utils import send_user_created_mail
    logger.info("   - Sending welcome mail ...".format(user.name))
    if user.can_send_created_mail():
        send_user_created_mail(user)


@receiver(cas_user_authenticated)
def on_cas_user_authenticated(sender, user, created, **kwargs):
    source = user.Source.cas.value
    user_authenticated_handle(user, created, source)


@receiver(saml2_create_or_update_user)
def on_saml2_create_or_update_user(sender, user, created, attrs, **kwargs):
    source = user.Source.saml2.value
    user_authenticated_handle(user, created, source, attrs, **kwargs)


@receiver(populate_user)
def on_ldap_create_user(sender, user, ldap_user, **kwargs):
    if user and user.username not in ['admin']:
        exists = User.objects.filter(username=user.username).exists()
        if not exists:
            user.source = user.Source.ldap.value
            user.save()


@receiver(openid_create_or_update_user)
def on_openid_create_or_update_user(sender, request, user, created, name, username, email, **kwargs):
    if created and settings.ONLY_ALLOW_EXIST_USER_AUTH:
        user.delete()
        raise PermissionDenied(f'Not allow non-exist user auth: {username}')

    if created:
        logger.debug(
            "Receive OpenID user created signal: {}, "
            "Set user source is: {}".format(user, User.Source.openid.value)
        )
        user.source = User.Source.openid.value
        user.save()
    elif not created and settings.AUTH_OPENID_ALWAYS_UPDATE_USER:
        logger.debug(
            "Receive OpenID user updated signal: {}, "
            "Update user info: {}"
            "".format(user, "name: {}|username: {}|email: {}".format(name, username, email))
        )
        user.name = name
        user.username = username
        user.email = email
        user.save()
