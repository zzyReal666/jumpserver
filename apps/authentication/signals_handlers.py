from importlib import import_module

from django.conf import settings
from django.contrib.auth import user_logged_in
from django.core.cache import cache
from django.dispatch import receiver

from jms_oidc_rp.signals import openid_user_login_failed, openid_user_login_success

from .signals import post_auth_success, post_auth_failed


@receiver(user_logged_in)
def on_user_auth_login_success(sender, user, request, **kwargs):
    if settings.USER_LOGIN_SINGLE_MACHINE_ENABLED:
        user_id = 'single_machine_login_' + str(user.id)
        session_key = cache.get(user_id)
        if session_key and session_key != request.session.session_key:
            session = import_module(settings.SESSION_ENGINE).SessionStore(session_key)
            session.delete()
        cache.set(user_id, request.session.session_key, None)


@receiver(openid_user_login_success)
def on_oidc_user_login_success(sender, request, user, **kwargs):
    post_auth_success.send(sender, user=user, request=request)


@receiver(openid_user_login_failed)
def on_oidc_user_login_failed(sender, username, request, reason, **kwargs):
    post_auth_failed.send(sender, username=username, request=request, reason=reason)
