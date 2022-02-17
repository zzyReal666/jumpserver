from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.generics import RetrieveDestroyAPIView

from common.utils import lazyproperty
from orgs.utils import tmp_to_root_org
from ..models import Ticket


__all__ = ['GenericTicketStatusRetrieveCloseAPI']


class GenericTicketStatusRetrieveCloseAPI(RetrieveDestroyAPIView):
    queryset = Ticket.objects.all()

    def retrieve(self, request, *args, **kwargs):
        if self.ticket.state_open:
            status = 'await'
        elif self.ticket.state_approve:
            status = 'approved'
        else:
            status = 'rejected'
        data = {
            'status': status,
            'action': self.ticket.state,
            'processor': str(self.ticket.processor)
        }
        return Response(data=data, status=200)

    def destroy(self, request, *args, **kwargs):
        if self.ticket.status_open:
            self.ticket.close(processor=self.ticket.applicant)
        data = {
            'action': self.ticket.state,
            'status': self.ticket.status,
            'processor': str(self.ticket.processor)
        }
        return Response(data=data, status=200)

    @lazyproperty
    def ticket(self):
        with tmp_to_root_org():
            return get_object_or_404(Ticket, pk=self.kwargs['pk'])
