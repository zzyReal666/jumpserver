# -*- coding: utf-8 -*-
#
from urllib.parse import urlencode
from functools import partial
import time

from django.conf import settings
from django.contrib.auth import authenticate
from django.shortcuts import reverse
from django.contrib.auth import BACKEND_SESSION_KEY

from common.utils import get_object_or_none, get_request_ip, get_logger
from users.models import User
from users.utils import (
    is_block_login, clean_failed_count
)
from . import errors
from .utils import rsa_decrypt
from .signals import post_auth_success, post_auth_failed
from .const import RSA_PRIVATE_KEY

logger = get_logger(__name__)


class AuthMixin:
    request = None

    def get_user_from_session(self):
        if self.request.session.is_empty():
            raise errors.SessionEmptyError()

        if all((self.request.user,
                not self.request.user.is_anonymous,
                BACKEND_SESSION_KEY in self.request.session)):
            user = self.request.user
            user.backend = self.request.session[BACKEND_SESSION_KEY]
            return user

        user_id = self.request.session.get('user_id')
        if not user_id:
            user = None
        else:
            user = get_object_or_none(User, pk=user_id)
        if not user:
            raise errors.SessionEmptyError()
        user.backend = self.request.session.get("auth_backend")
        return user

    def get_request_ip(self):
        ip = ''
        if hasattr(self.request, 'data'):
            ip = self.request.data.get('remote_addr', '')
        ip = ip or get_request_ip(self.request)
        return ip

    def check_is_block(self):
        if hasattr(self.request, 'data'):
            username = self.request.data.get("username")
        else:
            username = self.request.POST.get("username")
        ip = self.get_request_ip()
        if is_block_login(username, ip):
            logger.warn('Ip was blocked' + ': ' + username + ':' + ip)
            raise errors.BlockLoginError(username=username, ip=ip)

    def decrypt_passwd(self, raw_passwd):
        # 获取解密密钥，对密码进行解密
        rsa_private_key = self.request.session.get(RSA_PRIVATE_KEY)
        if rsa_private_key is not None:
            try:
                return rsa_decrypt(raw_passwd, rsa_private_key)
            except Exception as e:
                logger.error(e, exc_info=True)
                logger.error(f'Decrypt password faild: password[{raw_passwd}] rsa_private_key[{rsa_private_key}]')
                return None
        return raw_passwd

    def check_user_auth(self, decrypt_passwd=False):
        self.check_is_block()
        request = self.request
        if hasattr(request, 'data'):
            data = request.data
        else:
            data = request.POST
        username = data.get('username', '')
        password = data.get('password', '')
        challenge = data.get('challenge', '')
        public_key = data.get('public_key', '')
        ip = self.get_request_ip()

        CredentialError = partial(errors.CredentialError, username=username, ip=ip, request=request)

        if decrypt_passwd:
            password = self.decrypt_passwd(password)
            if not password:
                raise CredentialError(error=errors.reason_password_decrypt_failed)

        user = authenticate(request,
                            username=username,
                            password=password + challenge.strip(),
                            public_key=public_key)

        if not user:
            raise CredentialError(error=errors.reason_password_failed)
        elif user.is_expired:
            raise CredentialError(error=errors.reason_user_inactive)
        elif not user.is_active:
            raise CredentialError(error=errors.reason_user_inactive)
        elif user.password_has_expired:
            raise CredentialError(error=errors.reason_password_expired)

        self._check_passwd_is_too_simple(user, password)

        clean_failed_count(username, ip)
        request.session['auth_password'] = 1
        request.session['user_id'] = str(user.id)
        auth_backend = getattr(user, 'backend', 'django.contrib.auth.backends.ModelBackend')
        request.session['auth_backend'] = auth_backend
        return user

    @classmethod
    def _check_passwd_is_too_simple(cls, user, password):
        if user.is_superuser and password == 'admin':
            reset_passwd_url = reverse('authentication:reset-password')
            query_str = urlencode({
                'token': user.generate_reset_token()
            })
            reset_passwd_url = f'{reset_passwd_url}?{query_str}'

            flash_page_url = reverse('authentication:passwd-too-simple-flash-msg')
            query_str = urlencode({
                'redirect_url': reset_passwd_url
            })

            raise errors.PasswdTooSimple(f'{flash_page_url}?{query_str}')

    def check_user_auth_if_need(self, decrypt_passwd=False):
        request = self.request
        if request.session.get('auth_password') and \
                request.session.get('user_id'):
            user = self.get_user_from_session()
            if user:
                return user
        return self.check_user_auth(decrypt_passwd=decrypt_passwd)

    def check_user_mfa_if_need(self, user):
        if self.request.session.get('auth_mfa'):
            return
        if not user.mfa_enabled:
            return
        unset, url = user.mfa_enabled_but_not_set()
        if unset:
            raise errors.MFAUnsetError(user, self.request, url)
        raise errors.MFARequiredError()

    def check_user_mfa(self, code):
        user = self.get_user_from_session()
        ok = user.check_mfa(code)
        if ok:
            self.request.session['auth_mfa'] = 1
            self.request.session['auth_mfa_time'] = time.time()
            self.request.session['auth_mfa_type'] = 'otp'
            return
        raise errors.MFAFailedError(username=user.username, request=self.request)

    def get_ticket(self):
        from tickets.models import Ticket
        ticket_id = self.request.session.get("auth_ticket_id")
        logger.debug('Login confirm ticket id: {}'.format(ticket_id))
        if not ticket_id:
            ticket = None
        else:
            ticket = Ticket.origin_objects.get(pk=ticket_id)
        return ticket

    def get_ticket_or_create(self, confirm_setting):
        ticket = self.get_ticket()
        if not ticket or ticket.status == ticket.STATUS.CLOSED:
            ticket = confirm_setting.create_confirm_ticket(self.request)
            self.request.session['auth_ticket_id'] = str(ticket.id)
        return ticket

    def check_user_login_confirm(self):
        ticket = self.get_ticket()
        if not ticket:
            raise errors.LoginConfirmOtherError('', "Not found")
        if ticket.status == ticket.STATUS.OPEN:
            raise errors.LoginConfirmWaitError(ticket.id)
        elif ticket.action == ticket.ACTION.APPROVE:
            self.request.session["auth_confirm"] = "1"
            return
        elif ticket.action == ticket.ACTION.REJECT:
            raise errors.LoginConfirmOtherError(
                ticket.id, ticket.get_action_display()
            )
        else:
            raise errors.LoginConfirmOtherError(
                ticket.id, ticket.get_status_display()
            )

    def check_user_login_confirm_if_need(self, user):
        if not settings.LOGIN_CONFIRM_ENABLE:
            return
        confirm_setting = user.get_login_confirm_setting()
        if self.request.session.get('auth_confirm') or not confirm_setting:
            return
        self.get_ticket_or_create(confirm_setting)
        self.check_user_login_confirm()

    def clear_auth_mark(self):
        self.request.session['auth_password'] = ''
        self.request.session['auth_user_id'] = ''
        self.request.session['auth_mfa'] = ''
        self.request.session['auth_confirm'] = ''
        self.request.session['auth_ticket_id'] = ''

    def send_auth_signal(self, success=True, user=None, username='', reason=''):
        if success:
            post_auth_success.send(
                sender=self.__class__, user=user, request=self.request
            )
        else:
            post_auth_failed.send(
                sender=self.__class__, username=username,
                request=self.request, reason=reason
            )
