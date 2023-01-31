from rest_framework.generics import CreateAPIView
from rest_framework.response import Response

from common.utils import reverse, lazyproperty
from orgs.utils import tmp_to_org
from .. import serializers
from ..models import LoginAssetACL

__all__ = ['LoginAssetCheckAPI']


class LoginAssetCheckAPI(CreateAPIView):
    serializer_class = serializers.LoginAssetCheckSerializer
    model = LoginAssetACL
    rbac_perms = {
        'POST': 'tickets.add_superticket'
    }

    def get_queryset(self):
        return LoginAssetACL.objects.all()

    def create(self, request, *args, **kwargs):
        data = self.check_review()
        return Response(data=data, status=200)

    @lazyproperty
    def serializer(self):
        serializer = self.get_serializer(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        return serializer

    def check_review(self):
        with tmp_to_org(self.serializer.asset.org):
            kwargs = {
                'user': self.serializer.user,
                'asset': self.serializer.asset,
                'account_username': self.serializer.validated_data.get('account_username'),
                'action': LoginAssetACL.ActionChoices.review
            }
            acl = LoginAssetACL.filter_queryset(**kwargs).valid().first()
        if acl:
            need_review = True
            response_data = self._get_response_data_of_need_review(acl)
        else:
            need_review = False
            response_data = {}
        response_data['need_review'] = need_review
        return response_data

    def _get_response_data_of_need_review(self, acl) -> dict:
        ticket = LoginAssetACL.create_login_asset_review_ticket(
            user=self.serializer.user,
            asset=self.serializer.asset,
            account_username=self.serializer.validated_data.get('account_username'),
            assignees=acl.reviewers.all(),
            org_id=self.serializer.asset.org.id,
        )
        review_status_url = reverse(
            view_name='api-tickets:super-ticket-status',
            kwargs={'pk': str(ticket.id)}
        )
        ticket_detail_url = reverse(
            view_name='api-tickets:ticket-detail',
            kwargs={'pk': str(ticket.id)},
            external=True, api_to_ui=True
        )
        ticket_detail_url = '{url}?type={type}'.format(url=ticket_detail_url, type=ticket.type)
        ticket_assignees = ticket.current_step.ticket_assignees.all()
        data = {
            'check_review_status': {'method': 'GET', 'url': review_status_url},
            'close_review': {'method': 'DELETE', 'url': review_status_url},
            'ticket_detail_url': ticket_detail_url,
            'reviewers': [str(ticket_assignee.assignee) for ticket_assignee in ticket_assignees],
            'ticket_id': str(ticket.id)
        }
        return data
