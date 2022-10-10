# ~*~ coding: utf-8 ~*~
import json
import os
from collections import defaultdict

from django.utils.translation import gettext as _


__all__ = ['JMSInventory']


class JMSInventory:
    def __init__(self, assets, account='', account_policy='smart', host_var_callback=None, host_duplicator=None):
        """
        :param assets:
        :param account: account username name if not set use account_policy
        :param account_policy:
        :param host_var_callback:
        """
        self.assets = self.clean_assets(assets)
        self.account_username = account
        self.account_policy = account_policy
        self.host_var_callback = host_var_callback
        self.host_duplicator = host_duplicator

    @staticmethod
    def clean_assets(assets):
        from assets.models import Asset
        asset_ids = [asset.id for asset in assets]
        assets = Asset.objects.filter(id__in=asset_ids)\
            .prefetch_related('platform', 'domain', 'accounts')
        return assets

    @staticmethod
    def group_by_platform(assets):
        groups = defaultdict(list)
        for asset in assets:
            groups[asset.platform].append(asset)
        return groups

    @staticmethod
    def make_proxy_command(gateway):
        proxy_command_list = [
            "ssh", "-o", "Port={}".format(gateway.port),
            "-o", "StrictHostKeyChecking=no",
            "{}@{}".format(gateway.username, gateway.address),
            "-W", "%h:%p", "-q",
        ]

        if gateway.password:
            proxy_command_list.insert(
                0, "sshpass -p '{}'".format(gateway.password)
            )
        if gateway.private_key:
            proxy_command_list.append("-i {}".format(gateway.private_key_file))

        proxy_command = "'-o ProxyCommand={}'".format(
            " ".join(proxy_command_list)
        )
        return {"ansible_ssh_common_args": proxy_command}

    def asset_to_host(self, asset, account, automation, protocols):
        host = {
            'name': asset.name,
            'asset': {
                'id': str(asset.id), 'name': asset.name, 'address': asset.address,
                'type': asset.type, 'category': asset.category,
                'protocol': asset.protocol, 'port': asset.port,
                'protocols': [{'name': p.name, 'port': p.port} for p in protocols],
            },
            'exclude': ''
        }
        ansible_connection = automation.ansible_config.get('ansible_connection', 'ssh')
        gateway = None
        if asset.domain:
            gateway = asset.domain.select_gateway()

        ssh_protocol_matched = list(filter(lambda x: x.name == 'ssh', protocols))
        ssh_protocol = ssh_protocol_matched[0] if ssh_protocol_matched else None
        if ansible_connection == 'local':
            if gateway:
                host['ansible_host'] = gateway.address
                host['ansible_port'] = gateway.port
                host['ansible_user'] = gateway.username
                host['ansible_password'] = gateway.password
                host['ansible_connection'] = 'smart'
            else:
                host['ansible_connection'] = 'local'
        else:
            host['ansible_host'] = asset.address
            host['ansible_port'] = ssh_protocol.port if ssh_protocol else 22
            if account:
                host['ansible_user'] = account.username

                if account.secret_type == 'password' and account.secret:
                    host['ansible_password'] = account.secret
                elif account.secret_type == 'private_key' and account.secret:
                    host['ssh_private_key'] = account.private_key_file
            else:
                host['exclude'] = _("No account found")

            if gateway:
                host.update(self.make_proxy_command(gateway))

        if self.host_var_callback:
            callback_var = self.host_var_callback(asset)
            if isinstance(callback_var, dict):
                host.update(callback_var)
        return host

    def select_account(self, asset):
        accounts = list(asset.accounts.all())
        account_selected = None
        account_username = self.account_username

        if isinstance(self.account_username, str):
            account_username = [self.account_username]

        if account_username:
            for username in account_username:
                account_matched = list(filter(lambda account: account.username == username, accounts))
                if account_matched:
                    account_selected = account_matched[0]
                    break

        if not account_selected:
            if self.account_policy in ['privileged_must', 'privileged_first']:
                account_matched = list(filter(lambda account: account.privileged, accounts))
                account_selected = account_matched[0] if account_matched else None

        if not account_selected and self.account_policy == 'privileged_first':
            account_selected = accounts[0] if accounts else None
        return account_selected

    def generate(self):
        hosts = []
        platform_assets = self.group_by_platform(self.assets)
        for platform, assets in platform_assets.items():
            automation = platform.automation
            protocols = platform.protocols.all()

            for asset in self.assets:
                account = self.select_account(asset)
                host = self.asset_to_host(asset, account, automation, protocols)
                if not automation.ansible_enabled:
                    host['exclude'] = _('Ansible disabled')
                if self.host_duplicator:
                    hosts.extend(self.host_duplicator(host, asset=asset, account=account, platform=platform))
                else:
                    hosts.append(host)

        exclude_hosts = list(filter(lambda x: x.get('exclude'), hosts))
        if exclude_hosts:
            print(_("Skip hosts below:"))
            for i, host in enumerate(exclude_hosts, start=1):
                print("{}: [{}] \t{}".format(i, host['name'], host['exclude']))

        hosts = list(filter(lambda x: not x.get('exclude'), hosts))
        data = {'all': {'hosts': {}}}
        for host in hosts:
            name = host.pop('name')
            data['all']['hosts'][name] = host
        return data

    def write_to_file(self, path):
        data = self.generate()
        path_dir = os.path.dirname(path)
        if not os.path.exists(path_dir):
            os.makedirs(path_dir, 0o700, True)
        with open(path, 'w') as f:
            f.write(json.dumps(data, indent=4))
