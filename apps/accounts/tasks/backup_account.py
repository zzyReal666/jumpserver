# -*- coding: utf-8 -*-
#
from celery import shared_task
from django.utils.translation import gettext_lazy as _

from accounts.models import AccountBackupAutomation
from common.utils import get_object_or_none, get_logger
from orgs.utils import tmp_to_org, tmp_to_root_org

logger = get_logger(__file__)


@shared_task(verbose_name=_('Execute account backup plan'))
def execute_account_backup_plan(pid, trigger):
    with tmp_to_root_org():
        plan = get_object_or_none(AccountBackupAutomation, pk=pid)
    if not plan:
        logger.error("No account backup route plan found: {}".format(pid))
        return
    with tmp_to_org(plan.org):
        plan.execute(trigger)
