# -*- coding: utf-8 -*-
#
from django.db.models.signals import m2m_changed, pre_delete, pre_save
from django.dispatch import receiver

from perms.tasks import create_rebuild_user_tree_task, \
    create_rebuild_user_tree_task_by_related_nodes_or_assets
from users.models import User, UserGroup
from assets.models import Asset
from common.utils import get_logger
from common.exceptions import M2MReverseNotAllowed
from common.const.signals import POST_ADD, POST_REMOVE, POST_CLEAR
from .models import AssetPermission, RemoteAppPermission


logger = get_logger(__file__)


@receiver([pre_save], sender=AssetPermission)
def on_asset_perm_deactive(instance: AssetPermission, **kwargs):
    try:
        old = AssetPermission.objects.only('is_active').get(id=instance.id)
        if instance.is_active != old.is_active:
            create_rebuild_user_tree_task_by_asset_perm(instance)
    except AssetPermission.DoesNotExist:
        pass


@receiver([pre_delete], sender=AssetPermission)
def on_asset_permission_delete(instance, **kwargs):
    # 授权删除之前，查出所有相关用户
    create_rebuild_user_tree_task_by_asset_perm(instance)


def create_rebuild_user_tree_task_by_asset_perm(asset_perm: AssetPermission):
    user_ids = set()
    user_ids.update(
        UserGroup.objects.filter(
            assetpermissions=asset_perm, users__id__isnull=False
        ).distinct().values_list('users__id', flat=True)
    )
    user_ids.update(
        User.objects.filter(assetpermissions=asset_perm).distinct().values_list('id', flat=True)
    )
    create_rebuild_user_tree_task(user_ids)


def need_rebuild_mapping_node(action):
    return action in (POST_REMOVE, POST_ADD, POST_CLEAR)


@receiver(m2m_changed, sender=AssetPermission.nodes.through)
def on_permission_nodes_changed(instance, action, reverse, pk_set, model, **kwargs):
    if reverse:
        raise M2MReverseNotAllowed

    if need_rebuild_mapping_node(action):
        create_rebuild_user_tree_task_by_asset_perm(instance)

    if action != POST_ADD:
        return
    logger.debug("Asset permission nodes change signal received")
    nodes = model.objects.filter(pk__in=pk_set)
    system_users = instance.system_users.all()

    # TODO 待优化
    for system_user in system_users:
        system_user.nodes.add(*nodes)


@receiver(m2m_changed, sender=AssetPermission.assets.through)
def on_permission_assets_changed(instance, action, reverse, pk_set, model, **kwargs):
    if reverse:
        raise M2MReverseNotAllowed

    if need_rebuild_mapping_node(action):
        create_rebuild_user_tree_task_by_asset_perm(instance)

    if action != POST_ADD:
        return
    logger.debug("Asset permission assets change signal received")
    assets = model.objects.filter(pk__in=pk_set)

    # TODO 待优化
    system_users = instance.system_users.all()
    for system_user in system_users:
        system_user.assets.add(*tuple(assets))


@receiver(m2m_changed, sender=AssetPermission.system_users.through)
def on_asset_permission_system_users_changed(instance, action, reverse, **kwargs):
    if reverse:
        raise M2MReverseNotAllowed

    if action != POST_ADD:
        return
    logger.debug("Asset permission system_users change signal received")
    system_users = kwargs['model'].objects.filter(pk__in=kwargs['pk_set'])
    assets = instance.assets.all().values_list('id', flat=True)
    nodes = instance.nodes.all().values_list('id', flat=True)
    users = instance.users.all().values_list('id', flat=True)
    groups = instance.user_groups.all().values_list('id', flat=True)
    for system_user in system_users:
        system_user.nodes.add(*tuple(nodes))
        system_user.assets.add(*tuple(assets))
        if system_user.username_same_with_user:
            system_user.groups.add(*tuple(groups))
            system_user.users.add(*tuple(users))


@receiver(m2m_changed, sender=AssetPermission.users.through)
def on_asset_permission_users_changed(instance, action, reverse, pk_set, model, **kwargs):
    if reverse:
        raise M2MReverseNotAllowed

    if need_rebuild_mapping_node(action):
        create_rebuild_user_tree_task(pk_set)

    if action != POST_ADD:
        return
    logger.debug("Asset permission users change signal received")
    users = model.objects.filter(pk__in=pk_set)
    system_users = instance.system_users.all()

    # TODO 待优化
    for system_user in system_users:
        if system_user.username_same_with_user:
            system_user.users.add(*tuple(users))


@receiver(m2m_changed, sender=AssetPermission.user_groups.through)
def on_asset_permission_user_groups_changed(instance, action, pk_set, model,
                                            reverse, **kwargs):
    if reverse:
        raise M2MReverseNotAllowed

    if need_rebuild_mapping_node(action):
        user_ids = User.objects.filter(groups__id__in=pk_set).distinct().values_list('id', flat=True)
        create_rebuild_user_tree_task(user_ids)

    if action != POST_ADD:
        return
    logger.debug("Asset permission user groups change signal received")
    groups = model.objects.filter(pk__in=pk_set)
    system_users = instance.system_users.all()

    # TODO 待优化
    for system_user in system_users:
        if system_user.username_same_with_user:
            system_user.groups.add(*tuple(groups))


@receiver(m2m_changed, sender=RemoteAppPermission.system_users.through)
def on_remote_app_permission_system_users_changed(sender, instance=None,
                                                  action='', reverse=False, **kwargs):
    if action != POST_ADD or reverse:
        return
    system_users = kwargs['model'].objects.filter(pk__in=kwargs['pk_set'])
    logger.debug("Remote app permission system_users change signal received")
    assets = instance.remote_apps.all().values_list('asset__id', flat=True)
    users = instance.users.all().values_list('id', flat=True)
    groups = instance.user_groups.all().values_list('id', flat=True)
    for system_user in system_users:
        system_user.assets.add(*tuple(assets))
        if system_user.username_same_with_user:
            system_user.groups.add(*tuple(groups))
            system_user.users.add(*tuple(users))


@receiver(m2m_changed, sender=RemoteAppPermission.users.through)
def on_remoteapps_permission_users_changed(sender, instance=None, action='',
                                      reverse=False, **kwargs):
    if action != POST_ADD and reverse:
        return
    logger.debug("Asset permission users change signal received")
    users = kwargs['model'].objects.filter(pk__in=kwargs['pk_set'])
    system_users = instance.system_users.all()

    for system_user in system_users:
        if system_user.username_same_with_user:
            system_user.users.add(*tuple(users))


@receiver(m2m_changed, sender=RemoteAppPermission.user_groups.through)
def on_remoteapps_permission_user_groups_changed(sender, instance=None, action='',
                                            reverse=False, **kwargs):
    if action != POST_ADD and reverse:
        return
    logger.debug("Asset permission user groups change signal received")
    groups = kwargs['model'].objects.filter(pk__in=kwargs['pk_set'])
    system_users = instance.system_users.all()

    for system_user in system_users:
        if system_user.username_same_with_user:
            system_user.groups.add(*tuple(groups))


@receiver(m2m_changed, sender=Asset.nodes.through)
def on_node_asset_change(action, instance, reverse, pk_set, **kwargs):
    if not need_rebuild_mapping_node(action):
        return

    if reverse:
        asset_pk_set = pk_set
        node_pk_set = [instance.id]
    else:
        asset_pk_set = [instance.id]
        node_pk_set = pk_set

    create_rebuild_user_tree_task_by_related_nodes_or_assets.delay(node_pk_set, asset_pk_set)
