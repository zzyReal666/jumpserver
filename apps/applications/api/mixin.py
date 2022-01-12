from urllib.parse import urlencode, parse_qsl

from django.utils.translation import ugettext as _
from rest_framework.generics import get_object_or_404

from common.tree import TreeNode
from orgs.models import Organization
from assets.models import SystemUser
from applications.utils import KubernetesClient, KubernetesTree
from perms.utils.application.permission import get_application_system_user_ids

from ..models import Application

__all__ = ['SerializeApplicationToTreeNodeMixin']


class SerializeApplicationToTreeNodeMixin:

    @staticmethod
    def filter_organizations(applications):
        organization_ids = set(applications.values_list('org_id', flat=True))
        organizations = [Organization.get_instance(org_id) for org_id in organization_ids]
        organizations.sort(key=lambda x: x.name)
        return organizations

    @staticmethod
    def create_root_node():
        name = _('My applications')
        node = TreeNode(**{
            'id': 'applications',
            'name': name,
            'title': name,
            'pId': '',
            'open': True,
            'isParent': True,
            'meta': {
                'type': 'root'
            }
        })
        return node

    def serialize_applications_with_org(self, applications, tree_id, parent_info, user):
        tree_nodes = []
        if not applications:
            return tree_nodes

        if not tree_id:
            root_node = self.create_root_node()
            tree_nodes.append(root_node)
            organizations = self.filter_organizations(applications)
            for i, org in enumerate(organizations):
                tree_id = urlencode({'org_id': str(org.id)})
                apps = applications.filter(org_id=org.id)
                # 组织节点
                org_node = org.as_tree_node(oid=tree_id, pid=root_node.id)
                org_node.name += '({})'.format(apps.count())
                tree_nodes.append(org_node)
                category_type_nodes = Application.create_category_type_tree_nodes(
                    apps, tree_id, show_empty=False
                )
                tree_nodes += category_type_nodes

                for app in apps:
                    app_node = app.as_tree_node(tree_id, is_luna=True)
                    tree_nodes.append(app_node)
            return tree_nodes

        parent_info = dict(parse_qsl(parent_info))
        pod_name = parent_info.get('pod')
        app_id = parent_info.get('app_id')
        namespace = parent_info.get('namespace')
        system_user_id = parent_info.get('system_user_id')
        if app_id and not any([pod_name, namespace, system_user_id]):
            app = get_object_or_404(Application, id=app_id)
            system_user_ids = get_application_system_user_ids(user, app)
            system_users = SystemUser.objects.filter(id__in=system_user_ids).order_by('priority')
            for system_user in system_users:
                system_user_node = KubernetesTree(tree_id).as_system_user_tree_node(
                    system_user, parent_info
                )
                tree_nodes.append(system_user_node)
            return tree_nodes

        tree_nodes = KubernetesTree(tree_id).async_tree_node(parent_info)
        return tree_nodes
