from collections import defaultdict
from typing import List, Tuple
import time

from django.core.cache import cache
from django.conf import settings
from django.db.models import Q, QuerySet

from common.db.models import output_as_string, UnionQuerySet
from common.utils.common import lazyproperty, timeit
from assets.utils import NodeAssetsUtil
from common.utils import get_logger
from common.decorator import on_transaction_commit
from orgs.utils import tmp_to_org, current_org, ensure_in_real_or_default_org, tmp_to_root_org
from assets.models import (
    Asset, FavoriteAsset, AssetQuerySet, NodeQuerySet
)
from orgs.models import Organization
from perms.models import (
    AssetPermission, PermNode, UserAssetGrantedTreeNodeRelation,
)
from users.models import User
from perms.locks import UserGrantedTreeRebuildLock

NodeFrom = UserAssetGrantedTreeNodeRelation.NodeFrom
NODE_ONLY_FIELDS = ('id', 'key', 'parent_key', 'org_id')

logger = get_logger(__name__)


def get_user_all_asset_perm_ids(user) -> set:
    asset_perm_ids = set()
    user_perm_id = AssetPermission.users.through.objects \
        .filter(user_id=user.id) \
        .values_list('assetpermission_id', flat=True) \
        .distinct()
    asset_perm_ids.update(user_perm_id)

    group_ids = user.groups.through.objects \
        .filter(user_id=user.id) \
        .values_list('usergroup_id', flat=True) \
        .distinct()
    group_ids = list(group_ids)
    groups_perm_id = AssetPermission.user_groups.through.objects \
        .filter(usergroup_id__in=group_ids) \
        .values_list('assetpermission_id', flat=True) \
        .distinct()
    asset_perm_ids.update(groups_perm_id)

    asset_perm_ids = AssetPermission.objects.filter(
        id__in=asset_perm_ids).valid().values_list('id', flat=True)
    asset_perm_ids = set(asset_perm_ids)
    return asset_perm_ids


class UserGrantedTreeRefreshController:
    key_template = 'perms.user.node_tree.built_orgs.user_id:{user_id}'

    def __init__(self, user):
        self.user = user
        self.key = self.key_template.format(user_id=user.id)
        self.client = self.get_redis_client()

    @classmethod
    def clean_all_user_tree_built_mark(cls):
        """ 清除所有用户已构建树的标记 """
        client = cls.get_redis_client()
        key_match = cls.key_template.format(user_id='*')
        keys = client.keys(key_match)
        with client.pipeline() as p:
            for key in keys:
                p.delete(key)
            p.execute()

    @classmethod
    def get_redis_client(cls):
        return cache.client.get_client(write=True)

    def get_need_refresh_org_ids(self):
        org_ids = self.client.smembers(self.key)
        return {org_id.decode() for org_id in org_ids}

    def set_all_orgs_as_built(self):
        self.client.sadd(self.key, *self.org_ids)

    def have_need_refresh_orgs(self):
        built_org_ids = self.client.smembers(self.key)
        built_org_ids = {org_id.decode() for org_id in built_org_ids}
        have = self.org_ids - built_org_ids
        return have

    def get_need_refresh_orgs_and_fill_up(self):
        org_ids = self.org_ids

        with self.client.pipeline() as p:
            p.smembers(self.key)
            p.sadd(self.key, *org_ids)
            ret = p.execute()
            built_org_ids = {org_id.decode() for org_id in ret[0]}
            ids = org_ids - built_org_ids
            orgs = {*Organization.objects.filter(id__in=ids)}
            logger.info(
                f'Need rebuild orgs are {orgs}, built orgs are {ret[0]}, '
                f'all orgs are {org_ids}'
            )
            return orgs

    @classmethod
    @on_transaction_commit
    def remove_built_orgs_from_users(cls, org_ids, user_ids):
        client = cls.get_redis_client()
        org_ids = [str(org_id) for org_id in org_ids]

        with client.pipeline() as p:
            for user_id in user_ids:
                key = cls.key_template.format(user_id=user_id)
                p.srem(key, *org_ids)
            p.execute()
        logger.info(f'Remove orgs from users built tree: users:{user_ids} '
                    f'orgs:{org_ids}')

    @classmethod
    def add_need_refresh_orgs_for_users(cls, org_ids, user_ids):
        cls.remove_built_orgs_from_users(org_ids, user_ids)

    @classmethod
    @ensure_in_real_or_default_org
    def add_need_refresh_on_nodes_assets_relate_change(cls, node_ids, asset_ids):
        """
        1，计算与这些资产有关的授权
        2，计算与这些节点以及祖先节点有关的授权
        """

        node_ids = set(node_ids)
        ancestor_node_keys = set()
        asset_perm_ids = set()

        nodes = PermNode.objects.filter(id__in=node_ids).only('id', 'key')
        for node in nodes:
            ancestor_node_keys.update(node.get_ancestor_keys())

        ancestor_id = PermNode.objects.filter(key__in=ancestor_node_keys).values_list('id', flat=True)
        node_ids.update(ancestor_id)

        assets_related_perm_ids = AssetPermission.nodes.through.objects.filter(
            node_id__in=node_ids
        ).values_list('assetpermission_id', flat=True)
        asset_perm_ids.update(assets_related_perm_ids)

        nodes_related_perm_ids = AssetPermission.assets.through.objects.filter(
            asset_id__in=asset_ids
        ).values_list('assetpermission_id', flat=True)
        asset_perm_ids.update(nodes_related_perm_ids)

        cls.add_need_refresh_by_asset_perm_ids(asset_perm_ids)

    @classmethod
    def add_need_refresh_by_asset_perm_ids_cross_orgs(cls, asset_perm_ids):
        org_id_perm_ids_mapper = defaultdict(set)
        pairs = AssetPermission.objects.filter(id__in=asset_perm_ids).values_list('org_id', 'id')
        for org_id, perm_id in pairs:
            org_id_perm_ids_mapper[org_id].add(perm_id)
        for org_id, perm_ids in org_id_perm_ids_mapper.items():
            with tmp_to_org(org_id):
                cls.add_need_refresh_by_asset_perm_ids(perm_ids)

    @classmethod
    @ensure_in_real_or_default_org
    def add_need_refresh_by_asset_perm_ids(cls, asset_perm_ids):

        group_ids = AssetPermission.user_groups.through.objects.filter(
            assetpermission_id__in=asset_perm_ids
        ).values_list('usergroup_id', flat=True)

        user_ids = set()
        direct_user_id = AssetPermission.users.through.objects.filter(
            assetpermission_id__in=asset_perm_ids
        ).values_list('user_id', flat=True)
        user_ids.update(direct_user_id)

        group_user_ids = User.groups.through.objects.filter(
            usergroup_id__in=group_ids
        ).values_list('user_id', flat=True)
        user_ids.update(group_user_ids)

        cls.remove_built_orgs_from_users(
            [current_org.id], user_ids
        )

    @lazyproperty
    def org_ids(self):
        ret = {str(org.id) for org in self.orgs}
        return ret

    @lazyproperty
    def orgs(self):
        orgs = {*self.user.orgs.all().distinct()}
        return orgs

    @timeit
    def refresh_if_need(self, force=False):
        user = self.user

        with tmp_to_root_org():
            UserAssetGrantedTreeNodeRelation.objects.filter(user=user).exclude(org_id__in=self.org_ids).delete()

        if force or self.have_need_refresh_orgs():
            with UserGrantedTreeRebuildLock(user_id=user.id):
                if force:
                    orgs = self.orgs
                    self.set_all_orgs_as_built()
                else:
                    orgs = self.get_need_refresh_orgs_and_fill_up()

                for org in orgs:
                    with tmp_to_org(org):
                        t_start = time.time()
                        logger.info(f'Rebuild user tree: user={self.user} org={current_org}')
                        utils = UserGrantedTreeBuildUtils(user)
                        utils.rebuild_user_granted_tree()
                        logger.info(
                            f'Rebuild user tree ok: cost={time.time() - t_start} user={self.user} org={current_org}')


class UserGrantedUtilsBase:
    user: User

    def __init__(self, user, asset_perm_ids=None):
        self.user = user
        self._asset_perm_ids = asset_perm_ids and set(asset_perm_ids)

    @lazyproperty
    def asset_perm_ids(self) -> set:
        if self._asset_perm_ids:
            return self._asset_perm_ids

        asset_perm_ids = get_user_all_asset_perm_ids(self.user)
        return asset_perm_ids


class UserGrantedTreeBuildUtils(UserGrantedUtilsBase):

    def get_direct_granted_nodes(self) -> NodeQuerySet:
        # 查询直接授权节点
        nodes = PermNode.objects.filter(
            granted_by_permissions__id__in=self.asset_perm_ids
        ).distinct()
        return nodes

    @lazyproperty
    def direct_granted_asset_ids(self) -> list:
        # 3.15
        asset_ids = AssetPermission.assets.through.objects.filter(
            assetpermission_id__in=self.asset_perm_ids
        ).annotate(
            asset_id_str=output_as_string('asset_id')
        ).values_list(
            'asset_id_str', flat=True
        ).distinct()

        asset_ids = list(asset_ids)
        return asset_ids

    @ensure_in_real_or_default_org
    def rebuild_user_granted_tree(self):
        """
        注意：调用该方法一定要被 `UserGrantedTreeRebuildLock` 锁住
        """
        user = self.user

        # 先删除旧的授权树🌲
        UserAssetGrantedTreeNodeRelation.objects.filter(user=user).delete()

        if not self.asset_perm_ids:
            # 没有授权直接返回
            return

        nodes = self.compute_perm_nodes_tree()
        self.compute_node_assets_amount(nodes)
        if not nodes:
            return
        self.create_mapping_nodes(nodes)

    @timeit
    def compute_perm_nodes_tree(self, node_only_fields=NODE_ONLY_FIELDS) -> list:

        # 查询直接授权节点
        nodes = self.get_direct_granted_nodes().only(*node_only_fields)
        nodes = list(nodes)

        # 授权的节点 key 集合
        granted_key_set = {_node.key for _node in nodes}

        def _has_ancestor_granted(node: PermNode):
            """
            判断一个节点是否有授权过的祖先节点
            """
            ancestor_keys = set(node.get_ancestor_keys())
            return ancestor_keys & granted_key_set

        key2leaf_nodes_mapper = {}

        # 给授权节点设置 granted 标识，同时去重
        for node in nodes:
            node: PermNode
            if _has_ancestor_granted(node):
                continue
            node.node_from = NodeFrom.granted
            key2leaf_nodes_mapper[node.key] = node

        # 查询授权资产关联的节点设置
        def process_direct_granted_assets():
            # 查询直接授权资产
            node_ids = {node_id_str for node_id_str, _ in self.direct_granted_asset_id_node_id_str_pairs}
            # 查询授权资产关联的节点设置 2.80
            granted_asset_nodes = PermNode.objects.filter(
                id__in=node_ids
            ).distinct().only(*node_only_fields)
            granted_asset_nodes = list(granted_asset_nodes)

            # 给资产授权关联的节点设置 is_asset_granted 标识，同时去重
            for node in granted_asset_nodes:
                if _has_ancestor_granted(node):
                    continue
                if node.key in key2leaf_nodes_mapper:
                    continue
                node.node_from = NodeFrom.asset
                key2leaf_nodes_mapper[node.key] = node

        if not settings.PERM_SINGLE_ASSET_TO_UNGROUP_NODE:
            process_direct_granted_assets()

        leaf_nodes = key2leaf_nodes_mapper.values()

        # 计算所有祖先节点
        ancestor_keys = set()
        for node in leaf_nodes:
            ancestor_keys.update(node.get_ancestor_keys())

        # 从祖先节点 key 中去掉同时也是叶子节点的 key
        ancestor_keys -= key2leaf_nodes_mapper.keys()
        # 查出祖先节点
        ancestors = PermNode.objects.filter(key__in=ancestor_keys).only(*node_only_fields)
        ancestors = list(ancestors)
        for node in ancestors:
            node.node_from = NodeFrom.child
        result = [*leaf_nodes, *ancestors]
        return result

    @timeit
    def create_mapping_nodes(self, nodes):
        user = self.user
        to_create = []

        for node in nodes:
            to_create.append(UserAssetGrantedTreeNodeRelation(
                user=user,
                node=node,
                node_key=node.key,
                node_parent_key=node.parent_key,
                node_from=node.node_from,
                node_assets_amount=node.assets_amount,
                org_id=node.org_id
            ))

        UserAssetGrantedTreeNodeRelation.objects.bulk_create(to_create)

    @timeit
    def _fill_direct_granted_node_asset_ids_from_mem(self, nodes_key, mapper):
        org_id = current_org.id
        for key in nodes_key:
            asset_ids = PermNode.get_all_asset_ids_by_node_key(org_id, key)
            mapper[key].update(asset_ids)

    @lazyproperty
    def direct_granted_asset_id_node_id_str_pairs(self):
        node_asset_pairs = Asset.nodes.through.objects.filter(
            asset_id__in=self.direct_granted_asset_ids
        ).annotate(
            asset_id_str=output_as_string('asset_id'),
            node_id_str=output_as_string('node_id')
        ).values_list(
            'node_id_str', 'asset_id_str'
        )
        node_asset_pairs = list(node_asset_pairs)
        return node_asset_pairs

    @timeit
    def compute_node_assets_amount(self, nodes: List[PermNode]):
        """
        这里计算的是一个组织的
        """
        # 直接授权了根节点，直接计算
        if len(nodes) == 1:
            node = nodes[0]
            if node.node_from == NodeFrom.granted and node.key.isdigit():
                with tmp_to_org(node.org):
                    node.granted_assets_amount = len(node.get_all_asset_ids())
                    return

        direct_granted_nodes_key = []
        node_id_key_mapper = {}
        for node in nodes:
            if node.node_from == NodeFrom.granted:
                direct_granted_nodes_key.append(node.key)
            node_id_key_mapper[node.id.hex] = node.key

        # 授权的节点和直接资产的映射
        nodekey_assetsid_mapper = defaultdict(set)
        # 直接授权的节点，资产从完整树过来
        self._fill_direct_granted_node_asset_ids_from_mem(
            direct_granted_nodes_key, nodekey_assetsid_mapper
        )

        # 处理直接授权资产
        # 直接授权资产，取节点与资产的关系
        node_asset_pairs = self.direct_granted_asset_id_node_id_str_pairs
        node_asset_pairs = list(node_asset_pairs)

        for node_id, asset_id in node_asset_pairs:
            if node_id not in node_id_key_mapper:
                continue
            nkey = node_id_key_mapper[node_id]
            nodekey_assetsid_mapper[nkey].add(asset_id)

        util = NodeAssetsUtil(nodes, nodekey_assetsid_mapper)
        util.generate()

        for node in nodes:
            assets_amount = util.get_assets_amount(node.key)
            node.assets_amount = assets_amount

    def get_whole_tree_nodes(self) -> list:
        node_only_fields = NODE_ONLY_FIELDS + ('value', 'full_value')
        nodes = self.compute_perm_nodes_tree(node_only_fields=node_only_fields)
        self.compute_node_assets_amount(nodes)

        # 查询直接授权节点的子节点
        q = Q()
        for node in self.get_direct_granted_nodes().only('key'):
            q |= Q(key__startswith=f'{node.key}:')

        if q:
            descendant_nodes = PermNode.objects.filter(q).distinct()
        else:
            descendant_nodes = PermNode.objects.none()

        nodes.extend(descendant_nodes)
        return nodes


class UserGrantedAssetsQueryUtils(UserGrantedUtilsBase):

    def get_favorite_assets(self) -> QuerySet:
        favorite_asset_ids = FavoriteAsset.objects.filter(
            user=self.user
        ).values_list('asset_id', flat=True)
        favorite_asset_ids = list(favorite_asset_ids)
        assets = self.get_all_granted_assets()
        assets = assets.filter(id__in=favorite_asset_ids)
        return assets

    def get_ungroup_assets(self) -> AssetQuerySet:
        return self.get_direct_granted_assets()

    def get_direct_granted_assets(self) -> AssetQuerySet:
        queryset = Asset.objects.order_by().filter(
            granted_by_permissions__id__in=self.asset_perm_ids
        ).distinct()
        return queryset

    def get_direct_granted_nodes_assets(self) -> AssetQuerySet:
        granted_node_ids = AssetPermission.nodes.through.objects.filter(
            assetpermission_id__in=self.asset_perm_ids
        ).values_list('node_id', flat=True).distinct()
        granted_node_ids = list(granted_node_ids)
        granted_nodes = PermNode.objects.filter(id__in=granted_node_ids).only('id', 'key')
        queryset = PermNode.get_nodes_all_assets(*granted_nodes)
        return queryset

    def get_all_granted_assets(self) -> QuerySet:
        nodes_assets = self.get_direct_granted_nodes_assets()
        assets = self.get_direct_granted_assets()
        queryset = UnionQuerySet(nodes_assets, assets)
        return queryset

    def get_node_all_assets(self, id) -> Tuple[PermNode, QuerySet]:
        node = PermNode.objects.get(id=id)
        granted_status = node.get_granted_status(self.user)
        if granted_status == NodeFrom.granted:
            assets = PermNode.get_nodes_all_assets(node)
            return node, assets
        elif granted_status in (NodeFrom.asset, NodeFrom.child):
            node.use_granted_assets_amount()
            assets = self._get_indirect_granted_node_all_assets(node)
            return node, assets
        else:
            node.assets_amount = 0
            return node, Asset.objects.none()

    def get_node_assets(self, key) -> AssetQuerySet:
        node = PermNode.objects.get(key=key)
        granted_status = node.get_granted_status(self.user)

        if granted_status == NodeFrom.granted:
            assets = Asset.objects.order_by().filter(nodes__id=node.id)
        elif granted_status == NodeFrom.asset:
            assets = self._get_indirect_granted_node_assets(node.id)
        else:
            assets = Asset.objects.none()
        assets = assets.order_by('hostname')
        return assets

    def _get_indirect_granted_node_assets(self, id) -> AssetQuerySet:
        assets = Asset.objects.order_by().filter(nodes__id=id).distinct() & self.get_direct_granted_assets()
        return assets

    def _get_indirect_granted_node_all_assets(self, node) -> QuerySet:
        """
        此算法依据 `UserAssetGrantedTreeNodeRelation` 的数据查询
        1. 查询该节点下的直接授权节点
        2. 查询该节点下授权资产关联的节点
        """
        user = self.user

        # 查询该节点下的授权节点
        granted_nodes = UserAssetGrantedTreeNodeRelation.objects.filter(
            user=user, node_from=NodeFrom.granted
        ).filter(
            Q(node_key__startswith=f'{node.key}:')
        ).only('node_id', 'node_key')

        for n in granted_nodes:
            n.id = n.node_id

        node_assets = PermNode.get_nodes_all_assets(*granted_nodes)

        # 查询该节点下的资产授权节点
        only_asset_granted_node_ids = UserAssetGrantedTreeNodeRelation.objects.filter(
            user=user, node_from=NodeFrom.asset
        ).filter(
            Q(node_key__startswith=f'{node.key}:')
        ).values_list('node_id', flat=True)

        only_asset_granted_node_ids = list(only_asset_granted_node_ids)
        if node.node_from == NodeFrom.asset:
            only_asset_granted_node_ids.append(node.id)

        assets = Asset.objects.filter(
            nodes__id__in=only_asset_granted_node_ids,
            granted_by_permissions__id__in=self.asset_perm_ids
        ).distinct().order_by()
        granted_assets = UnionQuerySet(node_assets, assets)
        return granted_assets


class UserGrantedNodesQueryUtils(UserGrantedUtilsBase):
    def sort(self, nodes):
        nodes = sorted(nodes, key=lambda x: x.value)
        return nodes

    def get_node_children(self, key):
        if not key:
            return self.get_top_level_nodes()

        nodes = PermNode.objects.none()
        if key in [PermNode.FAVORITE_NODE_KEY, PermNode.UNGROUPED_NODE_KEY]:
            return nodes

        node = PermNode.objects.get(key=key)
        granted_status = node.get_granted_status(self.user)
        if granted_status == NodeFrom.granted:
            nodes = PermNode.objects.filter(parent_key=key)
        elif granted_status in (NodeFrom.asset, NodeFrom.child):
            nodes = self.get_indirect_granted_node_children(key)
        nodes = self.sort(nodes)
        return nodes

    def get_indirect_granted_node_children(self, key):
        """
        获取用户授权树中未授权节点的子节点
        只匹配在 `UserAssetGrantedTreeNodeRelation` 中存在的节点
        """
        user = self.user
        nodes = PermNode.objects.filter(
            granted_node_rels__user=user,
            parent_key=key
        ).annotate(
            **PermNode.annotate_granted_node_rel_fields
        ).distinct()

        # 设置节点授权资产数量
        for node in nodes:
            node.use_granted_assets_amount()
        return nodes

    def get_top_level_nodes(self):
        nodes = self.get_special_nodes()
        real_nodes = self.get_indirect_granted_node_children('')
        nodes.extend(self.sort(real_nodes))
        return nodes

    def get_ungrouped_node(self):
        assets_util = UserGrantedAssetsQueryUtils(self.user, self.asset_perm_ids)
        assets_amount = assets_util.get_direct_granted_assets().count()
        return PermNode.get_ungrouped_node(assets_amount)

    def get_favorite_node(self):
        assets_query_utils = UserGrantedAssetsQueryUtils(self.user, self.asset_perm_ids)
        assets_amount = assets_query_utils.get_favorite_assets().values_list('id').count()
        return PermNode.get_favorite_node(assets_amount)

    def get_special_nodes(self):
        nodes = []
        if settings.PERM_SINGLE_ASSET_TO_UNGROUP_NODE:
            ungrouped_node = self.get_ungrouped_node()
            nodes.append(ungrouped_node)
        favorite_node = self.get_favorite_node()
        nodes.append(favorite_node)
        return nodes

    @timeit
    def get_whole_tree_nodes(self, with_special=True):
        """
        这里的 granted nodes, 是整棵树需要的node，推算出来的也算
        :param user:
        :return:
        """
        nodes = PermNode.objects.filter(
            granted_node_rels__user=self.user
        ).annotate(
            **PermNode.annotate_granted_node_rel_fields
        ).distinct()

        key_to_node_mapper = {}
        nodes_descendant_q = Q()

        for node in nodes:
            node.use_granted_assets_amount()
            key_to_node_mapper[node.key] = node

            if node.node_from == NodeFrom.granted:
                # 直接授权的节点
                # 增加查询后代节点的过滤条件
                nodes_descendant_q |= Q(key__startswith=f'{node.key}:')

        if nodes_descendant_q:
            descendant_nodes = PermNode.objects.filter(
                nodes_descendant_q
            )
            for node in descendant_nodes:
                key_to_node_mapper[node.key] = node

        all_nodes = []
        if with_special:
            special_nodes = self.get_special_nodes()
            all_nodes.extend(special_nodes)
        all_nodes.extend(key_to_node_mapper.values())
        return all_nodes
