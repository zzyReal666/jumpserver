from django.db.models import QuerySet

from accounts.const import AutomationTypes, Connectivity
from common.utils import get_logger
from ..base.manager import VerifyHostCallbackMixin, AccountBasePlaybookManager

logger = get_logger(__name__)


class VerifyAccountManager(VerifyHostCallbackMixin, AccountBasePlaybookManager):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.host_account_mapper = {}

    @classmethod
    def method_type(cls):
        return AutomationTypes.verify_account

    def get_accounts(self, privilege_account, accounts: QuerySet):
        snapshot_account_usernames = self.execution.snapshot['accounts']
        if '*' not in snapshot_account_usernames:
            accounts = accounts.filter(username__in=snapshot_account_usernames)
        return accounts

    def on_host_success(self, host, result):
        account = self.host_account_mapper.get(host)
        account.set_connectivity(Connectivity.OK)

    def on_host_error(self, host, error, result):
        account = self.host_account_mapper.get(host)
        account.set_connectivity(Connectivity.ERR)
