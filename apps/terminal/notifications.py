from typing import Callable

from django.utils.translation import gettext_lazy as _
from django.conf import settings

from users.models import User
from common.utils import get_logger, reverse
from notifications.notifications import SystemMessage
from terminal.models import Session, Command
from notifications.models import SystemMsgSubscription
from notifications.backends import BACKEND
from common.utils import lazyproperty

logger = get_logger(__name__)

__all__ = ('CommandAlertMessage', 'CommandExecutionAlert')

CATEGORY = 'terminal'
CATEGORY_LABEL = _('Sessions')


class CommandAlertMixin:
    command: dict
    _get_message: Callable
    message_type_label: str

    @lazyproperty
    def subject(self):
        _input = self.command['input']
        if isinstance(_input, str):
            _input = _input.replace('\r\n', ' ').replace('\r', ' ').replace('\n', ' ')

        subject = self.message_type_label + "%(cmd)s" % {
            'cmd': _input
        }
        return subject

    @classmethod
    def post_insert_to_db(cls, subscription: SystemMsgSubscription):
        """
        兼容操作，试图用 `settings.SECURITY_INSECURE_COMMAND_EMAIL_RECEIVER` 的邮件地址
        assets_systemuser_assets找到用户，把用户设置为默认接收者
        """
        from settings.models import Setting
        db_setting = Setting.objects.filter(
            name='SECURITY_INSECURE_COMMAND_EMAIL_RECEIVER'
        ).first()
        if db_setting:
            emails = db_setting.value
        else:
            emails = settings.SECURITY_INSECURE_COMMAND_EMAIL_RECEIVER
        emails = emails.split(',')
        emails = [email.strip().strip('"') for email in emails]

        users = User.objects.filter(email__in=emails)
        if users:
            subscription.users.add(*users)
            subscription.receive_backends = [BACKEND.EMAIL]
            subscription.save()


class CommandAlertMessage(CommandAlertMixin, SystemMessage):
    category = CATEGORY
    category_label = CATEGORY_LABEL
    message_type_label = _('Danger command alert')

    def __init__(self, command):
        self.command = command

    def get_text_msg(self) -> dict:
        command = self.command
        session = Session.objects.get(id=command['session'])
        session_detail_url = reverse(
            'api-terminal:session-detail', kwargs={'pk': command['session']},
            external=True, api_to_ui=True
        )

        message = _("""
Command: %(command)s
Asset: %(hostname)s (%(host_ip)s)
User: %(user)s
Level: %(risk_level)s
Session: %(session_detail_url)s?oid=%(oid)s
        """) % {
            'command': command['input'],
            'hostname': command['asset'],
            'host_ip': session.asset_obj.ip,
            'user': command['user'],
            'risk_level': Command.get_risk_level_str(command['risk_level']),
            'session_detail_url': session_detail_url,
            'oid': session.org_id
        }
        return {
            'subject': self.subject,
            'message': message
        }

    def get_html_msg(self) -> dict:
        command = self.command
        session = Session.objects.get(id=command['session'])
        session_detail_url = reverse(
            'api-terminal:session-detail', kwargs={'pk': command['session']},
            external=True, api_to_ui=True
        )

        message = _("""
            Command: %(command)s
            <br>
            Asset: %(hostname)s (%(host_ip)s)
            <br>
            User: %(user)s
            <br>
            Level: %(risk_level)s
            <br>
            Session: <a href="%(session_detail_url)s?oid=%(oid)s">session detail</a>
            <br>
        """) % {
            'command': command['input'],
            'hostname': command['asset'],
            'host_ip': session.asset_obj.ip,
            'user': command['user'],
            'risk_level': Command.get_risk_level_str(command['risk_level']),
            'session_detail_url': session_detail_url,
            'oid': session.org_id
        }
        return {
            'subject': self.subject,
            'message': message
        }


class CommandExecutionAlert(CommandAlertMixin, SystemMessage):
    category = CATEGORY
    category_label = CATEGORY_LABEL
    message_type_label = _('Batch danger command alert')

    def __init__(self, command):
        self.command = command

    def get_html_msg(self) -> dict:
        command = self.command
        _input = command['input']
        _input = _input.replace('\n', '<br>')

        assets = ', '.join([str(asset) for asset in command['assets']])
        message = _("""
                            Assets: %(assets)s
                            <br>
                            User: %(user)s
                            <br>
                            Level: %(risk_level)s
                            <br>

                            ----------------- Commands ---------------- <br>
                            %(command)s <br>
                            ----------------- Commands ---------------- <br>
                            """) % {
            'command': _input,
            'assets': assets,
            'user': command['user'],
            'risk_level': Command.get_risk_level_str(command['risk_level'])
        }
        return {
            'subject': self.subject,
            'message': message
        }

    def get_text_msg(self) -> dict:
        command = self.command
        _input = command['input']

        assets = ', '.join([str(asset) for asset in command['assets']])
        message = _("""
Assets: %(assets)s
User: %(user)s
Level: %(risk_level)s

Commands 👇 ------------
%(command)s
------------------------
                            """) % {
            'command': _input,
            'assets': assets,
            'user': command['user'],
            'risk_level': Command.get_risk_level_str(command['risk_level'])
        }
        return {
            'subject': self.subject,
            'message': message
        }
