# -*- coding: utf-8 -*-
#
import inspect
from functools import partial
import time
from typing import Callable

from django.utils.http import urlencode
from django.core.cache import cache
from django.conf import settings
from django.contrib import auth
from django.utils.translation import ugettext as _
from rest_framework.request import Request
from django.contrib.auth import (
    BACKEND_SESSION_KEY, _get_backends,
    PermissionDenied, user_login_failed, _clean_credentials
)
from django.shortcuts import reverse, redirect, get_object_or_404

from common.utils import get_request_ip, get_logger, bulk_get, FlashMessageUtil
from acls.models import LoginACL
from users.models import User
from users.utils import LoginBlockUtil, MFABlockUtils, LoginIpBlockUtil
from . import errors
from .utils import rsa_decrypt, gen_key_pair
from .signals import post_auth_success, post_auth_failed
from .const import RSA_PRIVATE_KEY, RSA_PUBLIC_KEY

logger = get_logger(__name__)


def check_backend_can_auth(username, backend_path, allowed_auth_backends):
    if allowed_auth_backends is not None and backend_path not in allowed_auth_backends:
        logger.debug('Skip user auth backend: {}, {} not in'.format(
            username, backend_path, ','.join(allowed_auth_backends)
        ))
        return False
    return True


def authenticate(request=None, **credentials):
    """
    If the given credentials are valid, return a User object.
    """
    username = credentials.get('username')
    allowed_auth_backends = User.get_user_allowed_auth_backends(username)

    for backend, backend_path in _get_backends(return_tuples=True):
        # 预先检查，不浪费认证时间
        if not check_backend_can_auth(username, backend_path, allowed_auth_backends):
            continue

        backend_signature = inspect.signature(backend.authenticate)
        try:
            backend_signature.bind(request, **credentials)
        except TypeError:
            # This backend doesn't accept these credentials as arguments. Try the next one.
            continue
        try:
            user = backend.authenticate(request, **credentials)
        except PermissionDenied:
            # This backend says to stop in our tracks - this user should not be allowed in at all.
            break
        if user is None:
            continue
        # 如果是 None, 证明没有检查过, 需要再次检查
        if allowed_auth_backends is None:
            # 有些 authentication 参数中不带 username, 之后还要再检查
            allowed_auth_backends = user.get_allowed_auth_backends()
            if not check_backend_can_auth(user.username, backend_path, allowed_auth_backends):
                continue

        # Annotate the user object with the path of the backend.
        user.backend = backend_path
        return user

    # The credentials supplied are invalid to all backends, fire signal
    user_login_failed.send(
        sender=__name__, credentials=_clean_credentials(credentials), request=request
    )


auth.authenticate = authenticate


class PasswordEncryptionViewMixin:
    request = None

    def get_decrypted_password(self, password=None, username=None):
        request = self.request
        if hasattr(request, 'data'):
            data = request.data
        else:
            data = request.POST

        username = username or data.get('username')
        password = password or data.get('password')

        password = self.decrypt_passwd(password)
        if not password:
            self.raise_password_decrypt_failed(username=username)
        return password

    def raise_password_decrypt_failed(self, username):
        ip = self.get_request_ip()
        raise errors.CredentialError(
            error=errors.reason_password_decrypt_failed,
            username=username, ip=ip, request=self.request
        )

    def decrypt_passwd(self, raw_passwd):
        # 获取解密密钥，对密码进行解密
        rsa_private_key = self.request.session.get(RSA_PRIVATE_KEY)
        if rsa_private_key is None:
            return raw_passwd

        try:
            return rsa_decrypt(raw_passwd, rsa_private_key)
        except Exception as e:
            logger.error(e, exc_info=True)
            logger.error(
                f'Decrypt password failed: password[{raw_passwd}] '
                f'rsa_private_key[{rsa_private_key}]'
            )
            return None

    def get_request_ip(self):
        ip = ''
        if hasattr(self.request, 'data'):
            ip = self.request.data.get('remote_addr', '')
        ip = ip or get_request_ip(self.request)
        return ip

    def get_context_data(self, **kwargs):
        # 生成加解密密钥对，public_key传递给前端，private_key存入session中供解密使用
        rsa_public_key = self.request.session.get(RSA_PUBLIC_KEY)
        rsa_private_key = self.request.session.get(RSA_PRIVATE_KEY)
        if not all([rsa_private_key, rsa_public_key]):
            rsa_private_key, rsa_public_key = gen_key_pair()
            rsa_public_key = rsa_public_key.replace('\n', '\\n')
            self.request.session[RSA_PRIVATE_KEY] = rsa_private_key
            self.request.session[RSA_PUBLIC_KEY] = rsa_public_key

        kwargs.update({
            'rsa_public_key': rsa_public_key,
        })
        return super().get_context_data(**kwargs)


class CommonMixin(PasswordEncryptionViewMixin):
    request: Request
    get_request_ip: Callable

    def raise_credential_error(self, error):
        raise self.partial_credential_error(error=error)

    def _set_partial_credential_error(self, username, ip, request):
        self.partial_credential_error = partial(
            errors.CredentialError, username=username,
            ip=ip, request=request
        )

    def get_user_from_session(self):
        if self.request.session.is_empty():
            raise errors.SessionEmptyError()

        if all([
            self.request.user,
            not self.request.user.is_anonymous,
            BACKEND_SESSION_KEY in self.request.session
        ]):
            user = self.request.user
            user.backend = self.request.session[BACKEND_SESSION_KEY]
            return user

        user_id = self.request.session.get('user_id')
        auth_password = self.request.session.get('auth_password')
        auth_expired_at = self.request.session.get('auth_password_expired_at')
        auth_expired = auth_expired_at < time.time() if auth_expired_at else False

        if not user_id or not auth_password or auth_expired:
            raise errors.SessionEmptyError()

        user = get_object_or_404(User, pk=user_id)
        user.backend = self.request.session.get("auth_backend")
        return user

    def get_auth_data(self, decrypt_passwd=False):
        request = self.request
        if hasattr(request, 'data'):
            data = request.data
        else:
            data = request.POST

        items = ['username', 'password', 'challenge', 'public_key', 'auto_login']
        username, password, challenge, public_key, auto_login = bulk_get(data, items, default='')
        ip = self.get_request_ip()
        self._set_partial_credential_error(username=username, ip=ip, request=request)

        if decrypt_passwd:
            password = self.get_decrypted_password()
        password = password + challenge.strip()
        return username, password, public_key, ip, auto_login


class AuthPreCheckMixin:
    request: Request
    get_request_ip: Callable
    raise_credential_error: Callable

    def _check_is_block(self, username, raise_exception=True):
        ip = self.get_request_ip()

        if LoginIpBlockUtil(ip).is_block():
            raise errors.BlockGlobalIpLoginError(username=username, ip=ip)

        is_block = LoginBlockUtil(username, ip).is_block()
        if not is_block:
            return
        logger.warn('Ip was blocked' + ': ' + username + ':' + ip)
        exception = errors.BlockLoginError(username=username, ip=ip)
        if raise_exception:
            raise errors.BlockLoginError(username=username, ip=ip)
        else:
            return exception

    def check_is_block(self, raise_exception=True):
        if hasattr(self.request, 'data'):
            username = self.request.data.get("username")
        else:
            username = self.request.POST.get("username")

        self._check_is_block(username, raise_exception)

    def _check_only_allow_exists_user_auth(self, username):
        # 仅允许预先存在的用户认证
        if not settings.ONLY_ALLOW_EXIST_USER_AUTH:
            return

        exist = User.objects.filter(username=username).exists()
        if not exist:
            logger.error(f"Only allow exist user auth, login failed: {username}")
            self.raise_credential_error(errors.reason_user_not_exist)


class MFAMixin:
    request: Request
    get_user_from_session: Callable
    get_request_ip: Callable

    def _check_if_no_active_mfa(self, user):
        active_mfa_mapper = user.active_mfa_backends_mapper
        if not active_mfa_mapper:
            url = reverse('authentication:user-otp-enable-start')
            raise errors.MFAUnsetError(user, self.request, url)

    def _check_login_page_mfa_if_need(self, user):
        if not settings.SECURITY_MFA_IN_LOGIN_PAGE:
            return
        if not user.active_mfa_backends:
            return

        request = self.request
        data = request.data if hasattr(request, 'data') else request.POST
        code = data.get('code')
        mfa_type = data.get('mfa_type', 'otp')

        if not code:
            return
        self._do_check_user_mfa(code, mfa_type, user=user)

    def check_user_mfa_if_need(self, user):
        if self.request.session.get('auth_mfa'):
            return
        if not user.mfa_enabled:
            return

        active_mfa_names = user.active_mfa_backends_mapper.keys()
        raise errors.MFARequiredError(mfa_types=tuple(active_mfa_names))

    def mark_mfa_ok(self, mfa_type):
        self.request.session['auth_mfa'] = 1
        self.request.session['auth_mfa_time'] = time.time()
        self.request.session['auth_mfa_required'] = 0
        self.request.session['auth_mfa_type'] = mfa_type

    def clean_mfa_mark(self):
        keys = ['auth_mfa', 'auth_mfa_time', 'auth_mfa_required', 'auth_mfa_type']
        for k in keys:
            self.request.session.pop(k, '')

    def check_mfa_is_block(self, username, ip, raise_exception=True):
        blocked = MFABlockUtils(username, ip).is_block()
        if not blocked:
            return
        logger.warn('Ip was blocked' + ': ' + username + ':' + ip)
        exception = errors.BlockMFAError(username=username, request=self.request, ip=ip)
        if raise_exception:
            raise exception
        else:
            return exception

    def _do_check_user_mfa(self, code, mfa_type, user=None):
        user = user if user else self.get_user_from_session()
        if not user.mfa_enabled:
            return

        # 监测 MFA 是不是屏蔽了
        ip = self.get_request_ip()
        self.check_mfa_is_block(user.username, ip)

        ok = False
        mfa_backend = user.get_mfa_backend_by_type(mfa_type)
        backend_error = _('The MFA type ({}) is not enabled')
        if not mfa_backend:
            msg = backend_error.format(mfa_type)
        elif not mfa_backend.is_active():
            msg = backend_error.format(mfa_backend.display_name)
        else:
            ok, msg = mfa_backend.check_code(code)

        if ok:
            self.mark_mfa_ok(mfa_type)
            return

        raise errors.MFAFailedError(
            username=user.username,
            request=self.request,
            ip=ip, mfa_type=mfa_type,
            error=msg
        )

    @staticmethod
    def get_user_mfa_context(user=None):
        mfa_backends = User.get_user_mfa_backends(user)
        return {'mfa_backends': mfa_backends}

    @staticmethod
    def incr_mfa_failed_time(username, ip):
        util = MFABlockUtils(username, ip)
        util.incr_failed_count()


class AuthPostCheckMixin:
    @classmethod
    def generate_reset_password_url_with_flash_msg(cls, user, message):
        reset_passwd_url = reverse('authentication:reset-password')
        query_str = urlencode({
            'token': user.generate_reset_token()
        })
        reset_passwd_url = f'{reset_passwd_url}?{query_str}'

        message_data = {
            'title': _('Please change your password'),
            'message': message,
            'interval': 3,
            'redirect_url': reset_passwd_url,
        }
        return FlashMessageUtil.gen_message_url(message_data)

    @classmethod
    def _check_passwd_is_too_simple(cls, user: User, password):
        if user.is_superuser and password == 'admin':
            message = _('Your password is too simple, please change it for security')
            url = cls.generate_reset_password_url_with_flash_msg(user, message=message)
            raise errors.PasswordTooSimple(url)

    @classmethod
    def _check_passwd_need_update(cls, user: User):
        if user.need_update_password:
            message = _('You should to change your password before login')
            url = cls.generate_reset_password_url_with_flash_msg(user, message)
            raise errors.PasswordNeedUpdate(url)

    @classmethod
    def _check_password_require_reset_or_not(cls, user: User):
        if user.password_has_expired:
            message = _('Your password has expired, please reset before logging in')
            url = cls.generate_reset_password_url_with_flash_msg(user, message)
            raise errors.PasswordRequireResetError(url)


class AuthACLMixin:
    request: Request
    get_request_ip: Callable

    def _check_login_acl(self, user, ip):
        # ACL 限制用户登录
        is_allowed, limit_type = LoginACL.allow_user_to_login(user, ip)
        if is_allowed:
            return
        if limit_type == 'ip':
            raise errors.LoginIPNotAllowed(username=user.username, request=self.request)
        elif limit_type == 'time':
            raise errors.TimePeriodNotAllowed(username=user.username, request=self.request)

    def get_ticket(self):
        from tickets.models import Ticket
        ticket_id = self.request.session.get("auth_ticket_id")
        logger.debug('Login confirm ticket id: {}'.format(ticket_id))
        if not ticket_id:
            ticket = None
        else:
            ticket = Ticket.all().filter(id=ticket_id).first()
        return ticket

    def get_ticket_or_create(self, confirm_setting):
        ticket = self.get_ticket()
        if not ticket or ticket.status_closed:
            ticket = confirm_setting.create_confirm_ticket(self.request)
            self.request.session['auth_ticket_id'] = str(ticket.id)
        return ticket

    def check_user_login_confirm(self):
        ticket = self.get_ticket()
        if not ticket:
            raise errors.LoginConfirmOtherError('', "Not found")
        if ticket.status_open:
            raise errors.LoginConfirmWaitError(ticket.id)
        elif ticket.state_approve:
            self.request.session["auth_confirm"] = "1"
            return
        elif ticket.state_reject:
            raise errors.LoginConfirmOtherError(
                ticket.id, ticket.get_state_display()
            )
        elif ticket.state_close:
            raise errors.LoginConfirmOtherError(
                ticket.id, ticket.get_state_display()
            )
        else:
            raise errors.LoginConfirmOtherError(
                ticket.id, ticket.get_status_display()
            )

    def check_user_login_confirm_if_need(self, user):
        ip = self.get_request_ip()
        is_allowed, confirm_setting = LoginACL.allow_user_confirm_if_need(user, ip)
        if self.request.session.get('auth_confirm') or not is_allowed:
            return
        self.get_ticket_or_create(confirm_setting)
        self.check_user_login_confirm()


class AuthMixin(CommonMixin, AuthPreCheckMixin, AuthACLMixin, MFAMixin, AuthPostCheckMixin):
    request = None
    partial_credential_error = None

    key_prefix_captcha = "_LOGIN_INVALID_{}"

    def _check_auth_user_is_valid(self, username, password, public_key):
        user = authenticate(
            self.request, username=username,
            password=password, public_key=public_key
        )
        if not user:
            self.raise_credential_error(errors.reason_password_failed)

        self.request.session['auth_backend'] = getattr(user, 'backend', settings.AUTH_BACKEND_MODEL)

        if user.is_expired:
            self.raise_credential_error(errors.reason_user_expired)
        elif not user.is_active:
            self.raise_credential_error(errors.reason_user_inactive)
        return user

    def set_login_failed_mark(self):
        ip = self.get_request_ip()
        cache.set(self.key_prefix_captcha.format(ip), 1, 3600)

    def check_is_need_captcha(self):
        # 最近有登录失败时需要填写验证码
        ip = get_request_ip(self.request)
        need = cache.get(self.key_prefix_captcha.format(ip))
        return need

    def check_user_auth(self, decrypt_passwd=False):
        # pre check
        self.check_is_block()
        username, password, public_key, ip, auto_login = self.get_auth_data(decrypt_passwd)
        self._check_only_allow_exists_user_auth(username)

        # check auth
        user = self._check_auth_user_is_valid(username, password, public_key)

        # 校验login-acl规则
        self._check_login_acl(user, ip)

        # post check
        self._check_password_require_reset_or_not(user)
        self._check_passwd_is_too_simple(user, password)
        self._check_passwd_need_update(user)

        # 校验login-mfa, 如果登录页面上显示 mfa 的话
        self._check_login_page_mfa_if_need(user)

        # 标记密码验证成功
        self.mark_password_ok(user=user, auto_login=auto_login)
        LoginBlockUtil(user.username, ip).clean_failed_count()
        LoginIpBlockUtil(ip).clean_block_if_need()
        return user

    def mark_password_ok(self, user, auto_login=False):
        request = self.request
        request.session['auth_password'] = 1
        request.session['auth_password_expired_at'] = time.time() + settings.AUTH_EXPIRED_SECONDS
        request.session['user_id'] = str(user.id)
        request.session['auto_login'] = auto_login
        request.session['auth_backend'] = getattr(user, 'backend', settings.AUTH_BACKEND_MODEL)

    def check_oauth2_auth(self, user: User, auth_backend):
        ip = self.get_request_ip()
        request = self.request

        self._set_partial_credential_error(user.username, ip, request)

        if user.is_expired:
            self.raise_credential_error(errors.reason_user_expired)
        elif not user.is_active:
            self.raise_credential_error(errors.reason_user_inactive)

        self._check_is_block(user.username)
        self._check_login_acl(user, ip)

        LoginBlockUtil(user.username, ip).clean_failed_count()
        LoginIpBlockUtil(ip).clean_block_if_need()
        MFABlockUtils(user.username, ip).clean_failed_count()

        self.mark_password_ok(user, False)
        return user

    def check_user_auth_if_need(self, decrypt_passwd=False):
        request = self.request
        if not request.session.get('auth_password'):
            return self.check_user_auth(decrypt_passwd=decrypt_passwd)
        return self.get_user_from_session()

    def clear_auth_mark(self):
        keys = ['auth_password', 'user_id', 'auth_confirm', 'auth_ticket_id']
        for k in keys:
            self.request.session.pop(k, '')

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

    def redirect_to_guard_view(self):
        guard_url = reverse('authentication:login-guard')
        args = self.request.META.get('QUERY_STRING', '')
        if args:
            guard_url = "%s?%s" % (guard_url, args)
        return redirect(guard_url)
