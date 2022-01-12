from django.http.response import HttpResponseRedirect
from django.utils.translation import ugettext_lazy as _
from urllib.parse import urlencode
from django.views import View
from django.conf import settings
from django.http.request import HttpRequest
from django.db.utils import IntegrityError
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import APIException

from users.views import UserVerifyPasswordView
from users.utils import is_auth_password_time_valid
from users.models import User
from common.utils import get_logger, FlashMessageUtil
from common.utils.random import random_string
from common.utils.django import reverse, get_object_or_none
from common.sdk.im.dingtalk import URL
from common.mixins.views import PermissionsMixin
from authentication import errors
from authentication.mixins import AuthMixin
from common.sdk.im.dingtalk import DingTalk
from common.utils.common import get_request_ip
from authentication.notifications import OAuthBindMessage

logger = get_logger(__file__)


DINGTALK_STATE_SESSION_KEY = '_dingtalk_state'


class DingTalkQRMixin(PermissionsMixin, View):
    def dispatch(self, request, *args, **kwargs):
        try:
            return super().dispatch(request, *args, **kwargs)
        except APIException as e:
            try:
                msg = e.detail['errmsg']
            except Exception:
                msg = _('DingTalk Error, Please contact your system administrator')
            return self.get_failed_response(
                '/',
                _('DingTalk Error'),
                msg
            )

    def verify_state(self):
        state = self.request.GET.get('state')
        session_state = self.request.session.get(DINGTALK_STATE_SESSION_KEY)
        if state != session_state:
            return False
        return True

    def get_verify_state_failed_response(self, redirect_uri):
        msg = _("The system configuration is incorrect. Please contact your administrator")
        return self.get_failed_response(redirect_uri, msg, msg)

    def get_qr_url(self, redirect_uri):
        state = random_string(16)
        self.request.session[DINGTALK_STATE_SESSION_KEY] = state

        params = {
            'appid': settings.DINGTALK_APPKEY,
            'response_type': 'code',
            'scope': 'snsapi_login',
            'state': state,
            'redirect_uri': redirect_uri,
        }
        url = URL.QR_CONNECT + '?' + urlencode(params)
        return url

    @staticmethod
    def get_success_response(redirect_url, title, msg):
        message_data = {
            'title': title,
            'message': msg,
            'interval': 5,
            'redirect_url': redirect_url,
        }
        return FlashMessageUtil.gen_and_redirect_to(message_data)

    @staticmethod
    def get_failed_response(redirect_url, title, msg):
        message_data = {
            'title': title,
            'error': msg,
            'interval': 5,
            'redirect_url': redirect_url,
        }
        return FlashMessageUtil.gen_and_redirect_to(message_data)

    def get_already_bound_response(self, redirect_url):
        msg = _('DingTalk is already bound')
        response = self.get_failed_response(redirect_url, msg, msg)
        return response


class DingTalkQRBindView(DingTalkQRMixin, View):
    permission_classes = (IsAuthenticated,)

    def get(self, request: HttpRequest):
        user = request.user
        redirect_url = request.GET.get('redirect_url')

        if not is_auth_password_time_valid(request.session):
            msg = _('Please verify your password first')
            response = self.get_failed_response(redirect_url, msg, msg)
            return response

        redirect_uri = reverse('authentication:dingtalk-qr-bind-callback', kwargs={'user_id': user.id}, external=True)
        redirect_uri += '?' + urlencode({'redirect_url': redirect_url})

        url = self.get_qr_url(redirect_uri)
        return HttpResponseRedirect(url)


class DingTalkQRBindCallbackView(DingTalkQRMixin, View):
    permission_classes = (IsAuthenticated,)

    def get(self, request: HttpRequest, user_id):
        code = request.GET.get('code')
        redirect_url = request.GET.get('redirect_url')

        if not self.verify_state():
            return self.get_verify_state_failed_response(redirect_url)

        user = get_object_or_none(User, id=user_id)
        if user is None:
            logger.error(f'DingTalkQR bind callback error, user_id invalid: user_id={user_id}')
            msg = _('Invalid user_id')
            response = self.get_failed_response(redirect_url, msg, msg)
            return response

        if user.dingtalk_id:
            response = self.get_already_bound_response(redirect_url)
            return response

        dingtalk = DingTalk(
            appid=settings.DINGTALK_APPKEY,
            appsecret=settings.DINGTALK_APPSECRET,
            agentid=settings.DINGTALK_AGENTID
        )
        userid = dingtalk.get_userid_by_code(code)

        if not userid:
            msg = _('DingTalk query user failed')
            response = self.get_failed_response(redirect_url, msg, msg)
            return response

        try:
            user.dingtalk_id = userid
            user.save()
        except IntegrityError as e:
            if e.args[0] == 1062:
                msg = _('The DingTalk is already bound to another user')
                response = self.get_failed_response(redirect_url, msg, msg)
                return response
            raise e

        ip = get_request_ip(request)
        OAuthBindMessage(user, ip, _('DingTalk'), user_id).publish_async()
        msg = _('Binding DingTalk successfully')
        response = self.get_success_response(redirect_url, msg, msg)
        return response


class DingTalkEnableStartView(UserVerifyPasswordView):

    def get_success_url(self):
        referer = self.request.META.get('HTTP_REFERER')
        redirect_url = self.request.GET.get("redirect_url")

        success_url = reverse('authentication:dingtalk-qr-bind')

        success_url += '?' + urlencode({
            'redirect_url': redirect_url or referer
        })

        return success_url


class DingTalkQRLoginView(DingTalkQRMixin, View):
    permission_classes = (AllowAny,)

    def get(self,  request: HttpRequest):
        redirect_url = request.GET.get('redirect_url')

        redirect_uri = reverse('authentication:dingtalk-qr-login-callback', external=True)
        redirect_uri += '?' + urlencode({'redirect_url': redirect_url})

        url = self.get_qr_url(redirect_uri)
        return HttpResponseRedirect(url)


class DingTalkQRLoginCallbackView(AuthMixin, DingTalkQRMixin, View):
    permission_classes = (AllowAny,)

    def get(self, request: HttpRequest):
        code = request.GET.get('code')
        redirect_url = request.GET.get('redirect_url')
        login_url = reverse('authentication:login')

        if not self.verify_state():
            return self.get_verify_state_failed_response(redirect_url)

        dingtalk = DingTalk(
            appid=settings.DINGTALK_APPKEY,
            appsecret=settings.DINGTALK_APPSECRET,
            agentid=settings.DINGTALK_AGENTID
        )
        userid = dingtalk.get_userid_by_code(code)
        if not userid:
            # 正常流程不会出这个错误，hack 行为
            msg = _('Failed to get user from DingTalk')
            response = self.get_failed_response(login_url, title=msg, msg=msg)
            return response

        user = get_object_or_none(User, dingtalk_id=userid)
        if user is None:
            title = _('DingTalk is not bound')
            msg = _('Please login with a password and then bind the DingTalk')
            response = self.get_failed_response(login_url, title=title, msg=msg)
            return response

        try:
            self.check_oauth2_auth(user, settings.AUTH_BACKEND_DINGTALK)
        except errors.AuthFailedError as e:
            self.set_login_failed_mark()
            msg = e.msg
            response = self.get_failed_response(login_url, title=msg, msg=msg)
            return response

        return self.redirect_to_guard_view()
