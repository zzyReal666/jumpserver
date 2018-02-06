# coding: utf-8

from __future__ import absolute_import, unicode_literals
import collections
from django.utils import timezone

from common.utils import setattr_bulk, get_logger
import copy
from .tasks import push_users
from .hands import AssetGroup

logger = get_logger(__file__)


class NodePermissionUtil:

    @staticmethod
    def get_user_group_permissions(user_group):
        return user_group.nodepermission_set.all() \
            .filter(is_active=True) \
            .filter(date_expired__gt=timezone.now())

    @classmethod
    def get_user_group_nodes(cls, user_group):
        """
        获取用户组授权的node和系统用户
        :param user_group:
        :return: {"node": set(systemuser1, systemuser2), ..}
        """
        permissions = cls.get_user_group_permissions(user_group)
        nodes_directed = collections.defaultdict(set)

        for perm in permissions:
            nodes_directed[perm.node].add(perm.system_user)

        nodes = copy.deepcopy(nodes_directed)
        for node, system_users in nodes_directed.items():
            for child in node.get_all_children():
                nodes[child].update(system_users)
        return nodes

    @classmethod
    def get_user_group(cls):
        pass


def get_user_group_granted_asset_groups(user_group):
    """Return asset groups granted of the user group

    :param user_group: Instance of :class: ``UserGroup``
    :return: {asset_group1: {system_user1, },
              asset_group2: {system_user1, system_user2}}
    """
    asset_groups = {}
    asset_permissions = user_group.asset_permissions.all()

    for asset_permission in asset_permissions:
        if not asset_permission.is_valid:
            continue
        for asset_group in asset_permission.asset_groups.all():
            if asset_group in asset_groups:
                asset_groups[asset_group] |= set(asset_permission.system_users.all())
            else:
                asset_groups[asset_group] = set(asset_permission.system_users.all())
    return asset_groups


def get_user_group_granted_assets(user_group):
    """Return assets granted of the user group

    :param user_group: Instance of :class: ``UserGroup``
    :return: {asset1: {system_user1, }, asset1: {system_user1, system_user2]}
    """
    assets = {}
    asset_permissions = user_group.asset_permissions.all()

    for asset_permission in asset_permissions:
        if not asset_permission.is_valid:
            continue
        for asset in asset_permission.get_granted_assets():
            if not asset.is_active:
                continue
            if asset in assets:
                assets[asset] |= set(asset_permission.system_users.all())
            else:
                assets[asset] = set(asset_permission.system_users.all())
    return assets


def get_user_granted_assets_direct(user):
    """Return assets granted of the user directly

     :param user: Instance of :class: ``User``
     :return: {asset1: {system_user1, system_user2}, asset2: {...}}
    """
    assets = {}
    asset_permissions_direct = user.asset_permissions.all()

    for asset_permission in asset_permissions_direct:
        if not asset_permission.is_valid:
            continue
        for asset in asset_permission.get_granted_assets():
            if not asset.is_active:
                continue
            if asset in assets:
                assets[asset] |= set(asset_permission.system_users.all())
            else:
                setattr(asset, 'inherited', False)
                assets[asset] = set(asset_permission.system_users.all())
    return assets


def get_user_granted_assets_inherit_from_user_groups(user):
    """Return assets granted of the user inherit from user groups

    :param user: Instance of :class: ``User``
    :return: {asset1: {system_user1, system_user2}, asset2: {...}}
    """
    assets = {}
    user_groups = user.groups.all()

    for user_group in user_groups:
        assets_inherited = get_user_group_granted_assets(user_group)
        for asset in assets_inherited:
            if not asset.is_active:
                continue
            if asset in assets:
                assets[asset] |= assets_inherited[asset]
            else:
                setattr(asset, 'inherited', True)
                assets[asset] = assets_inherited[asset]
    return assets


def get_user_granted_assets(user):
    """Return assets granted of the user inherit from user groups

    :param user: Instance of :class: ``User``
    :return: {asset1: {system_user1, system_user2}, asset2: {...}}
    """
    assets_direct = get_user_granted_assets_direct(user)
    assets_inherited = get_user_granted_assets_inherit_from_user_groups(user)
    assets = assets_inherited

    for asset in assets_direct:
        if not asset.is_active:
            continue
        if asset in assets:
            assets[asset] |= assets_direct[asset]
        else:
            assets[asset] = assets_direct[asset]
    return assets


def get_user_granted_asset_groups(user):
    """Return asset groups with assets and system users, it's not the asset
    group direct permed in rules. We get all asset and then get it asset group

    :param user: Instance of :class: ``User``
    :return: {asset_group1: [asset1, asset2], asset_group2: []}
    """
    asset_groups = collections.defaultdict(list)
    ungroups = [AssetGroup(name="UnGrouped")]
    for asset, system_users in get_user_granted_assets(user).items():
        groups = asset.groups.all()
        if not groups:
            groups = ungroups
        for asset_group in groups:
            asset_groups[asset_group].append((asset, system_users))
    return asset_groups


def get_user_group_asset_permissions(user_group):
    permissions = user_group.asset_permissions.all()
    return permissions


def get_user_asset_permissions(user):
    user_group_permissions = set()
    direct_permissions = set(setattr_bulk(user.asset_permissions.all(), 'inherited', 0))

    for user_group in user.groups.all():
        permissions = get_user_group_asset_permissions(user_group)
        user_group_permissions |= set(permissions)
    user_group_permissions = set(setattr_bulk(user_group_permissions, 'inherited', 1))
    return direct_permissions | user_group_permissions


def get_user_granted_system_users(user):
    """
    :param user: the user
    :return: {"system_user": ["asset", "asset1"], "system_user": []}
    """
    assets = get_user_granted_assets(user)
    system_users_dict = {}
    for asset, system_users in assets.items():
        for system_user in system_users:
            if system_user in system_users_dict:
                system_users_dict[system_user].append(asset)
            else:
                system_users_dict[system_user] = [asset]
    return system_users_dict


def push_system_user(assets, system_user):
    logger.info('Push system user %s' % system_user.name)
    for asset in assets:
        logger.info('\tAsset: %s' % asset.ip)
    if not assets:
        return None

    assets = [asset._to_secret_json() for asset in assets]
    system_user = system_user._to_secret_json()
    task = push_users.delay(assets, system_user)
    return task.id
