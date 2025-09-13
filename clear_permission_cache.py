#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JumpServer 权限缓存清除脚本
使用方法: python3 clear_permission_cache.py [选项]
"""

import os
import sys
import django

# 添加apps目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'apps'))

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'jumpserver.settings')
django.setup()

from django.core.cache import cache

from users.models import User
from perms.utils.user_perm_tree import UserPermTreeExpireUtil
from perms.utils.user_perm import UserPermAssetUtil


def clear_rbac_permissions_cache():
    """清除RBAC权限缓存"""
    print("正在清除RBAC权限缓存...")
    User.expire_users_rbac_perms_cache()
    print("✓ RBAC权限缓存已清除")


def clear_asset_permissions_cache():
    """清除资产权限树缓存"""
    print("正在清除资产权限树缓存...")
    user_ids = User.objects.all().values_list('id', flat=True)
    UserPermTreeExpireUtil().expire_perm_tree_for_users_orgs(user_ids, ['*'])
    print("✓ 资产权限树缓存已清除")


def clear_type_nodes_cache():
    """清除类型节点树缓存"""
    print("正在清除类型节点树缓存...")
    user_ids = User.objects.all().values_list('id', flat=True)
    UserPermAssetUtil.refresh_type_nodes_tree_cache(user_ids)
    print("✓ 类型节点树缓存已清除")


def clear_all_cache():
    """清除所有缓存"""
    print("正在清除所有缓存...")
    cache.clear()
    print("✓ 所有缓存已清除")


def clear_user_specific_cache(username):
    """清除特定用户的权限缓存"""
    try:
        user = User.objects.get(username=username)
        print(f"正在清除用户 {username} 的权限缓存...")
        
        # 清除用户RBAC权限缓存
        user.expire_rbac_perms_cache()
        
        # 清除用户权限树缓存
        UserPermTreeExpireUtil().expire_perm_tree_for_users_orgs([user.id], ['*'])
        
        # 清除用户类型节点缓存
        UserPermAssetUtil.refresh_type_nodes_tree_cache([user.id])
        
        print(f"✓ 用户 {username} 的权限缓存已清除")
    except User.DoesNotExist:
        print(f"✗ 用户 {username} 不存在")


def main():
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python3 clear_permission_cache.py rbac          # 清除RBAC权限缓存")
        print("  python3 clear_permission_cache.py asset         # 清除资产权限缓存")
        print("  python3 clear_permission_cache.py type          # 清除类型节点缓存")
        print("  python3 clear_permission_cache.py all           # 清除所有缓存")
        print("  python3 clear_permission_cache.py user <username> # 清除特定用户缓存")
        sys.exit(1)
    
    action = sys.argv[1]
    
    if action == 'rbac':
        clear_rbac_permissions_cache()
    elif action == 'asset':
        clear_asset_permissions_cache()
    elif action == 'type':
        clear_type_nodes_cache()
    elif action == 'all':
        clear_all_cache()
    elif action == 'user':
        if len(sys.argv) < 3:
            print("请指定用户名: python3 clear_permission_cache.py user <username>")
            sys.exit(1)
        username = sys.argv[2]
        clear_user_specific_cache(username)
    else:
        print(f"未知操作: {action}")
        sys.exit(1)
    
    print("\n权限缓存清除完成！")


if __name__ == '__main__':
    main()
