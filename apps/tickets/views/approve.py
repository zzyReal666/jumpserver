# -*- coding: utf-8 -*-
#

from __future__ import unicode_literals
from django.views.generic.base import TemplateView
from django.shortcuts import redirect, reverse
from django.core.cache import cache
from django.utils.translation import ugettext as _

from tickets.models import Ticket
from tickets.errors import AlreadyClosed
from common.utils import get_logger, FlashMessageUtil

logger = get_logger(__name__)
__all__ = ['TicketDirectApproveView']


class TicketDirectApproveView(TemplateView):
    template_name = 'tickets/approve_check_password.html'
    redirect_field_name = 'next'

    @property
    def message_data(self):
        return {
            'title': _('Ticket direct approval'),
            'error': _("This ticket does not exist, "
                       "the process has ended, or this link has expired"),
            'redirect_url': self.login_url,
            'auto_redirect': False
        }

    @property
    def login_url(self):
        return reverse('authentication:login') + '?admin=1'

    def redirect_message_response(self, **kwargs):
        message_data = self.message_data
        for key, value in kwargs.items():
            if isinstance(value, str):
                message_data[key] = value
        if message_data.get('message'):
            message_data.pop('error')
        redirect_url = FlashMessageUtil.gen_message_url(message_data)
        return redirect(redirect_url)

    @staticmethod
    def clear(token):
        cache.delete(token)

    def get_context_data(self, **kwargs):
        # 放入工单信息
        token = kwargs.get('token')
        ticket_info = cache.get(token, {}).get('body', '')
        if self.request.user.is_authenticated:
            prompt_msg = _('Click the button to approve directly')
        else:
            prompt_msg = _('After successful authentication, this ticket can be approved directly')
        kwargs.update({
            'ticket_info': ticket_info, 'prompt_msg': prompt_msg,
            'login_url': '%s&next=%s' % (
                self.login_url,
                reverse('tickets:direct-approve', kwargs={'token': token})
            ),
        })
        return super().get_context_data(**kwargs)

    def get(self, request, *args, **kwargs):
        token = kwargs.get('token')
        ticket_info = cache.get(token)
        if not ticket_info:
            return self.redirect_message_response(redirect_url=self.login_url)
        return super().get(request, *args, **kwargs)

    def post(self, request, **kwargs):
        user = request.user
        token = kwargs.get('token')
        ticket_info = cache.get(token)
        if not ticket_info:
            return self.redirect_message_response(redirect_url=self.login_url)
        try:
            ticket_id = ticket_info.get('ticket_id')
            ticket = Ticket.all().get(id=ticket_id)
            if not ticket.has_current_assignee(user):
                raise Exception(_("This user is not authorized to approve this ticket"))
            ticket.approve(user)
        except AlreadyClosed as e:
            self.clear(token)
            return self.redirect_message_response(error=str(e), redirect_url=self.login_url)
        except Exception as e:
            return self.redirect_message_response(error=str(e), redirect_url=self.login_url)

        self.clear(token)
        return self.redirect_message_response(message=_("Success"), redirect_url=self.login_url)
