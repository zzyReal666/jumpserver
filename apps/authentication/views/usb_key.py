# -*- coding: utf-8 -*-
#
from django.contrib.auth import login as auth_login
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.contrib.auth import get_user_model

from common.utils import get_logger

UserModel = get_user_model()
logger = get_logger(__file__)


@csrf_protect
@require_http_methods(["GET", "POST"])
def usb_key_login_view(request):
    """USB Key登录视图"""
    if request.method == 'GET':
        # 获取用户名和next参数
        username = request.GET.get('username', '')
        next_url = request.GET.get('next', '/')
        
        # 如果URL中没有用户名，记录警告
        if not username:
            logger.warning("USB Key login page accessed without username parameter")
        
        # 生成服务器端随机数
        import random
        import time
        server_random = str(int(time.time() * 1000)) + str(random.randint(100000, 999999))
        
        context = {
            'username': username,
            'next_url': next_url,
            'server_random': server_random
        }
        return render(request, 'authentication/login_usbkey.html', context)
    
    # POST请求处理USB Key认证
    signature = request.POST.get('sign_value')
    random_data = request.POST.get('random')
    username = request.POST.get('username', '')
    next_url = request.POST.get('next', '/')
    server_random = request.POST.get('server_random', '')
    
    # 调试日志
    logger.info(f"USB Key login attempt - Username: {username}")
    logger.info(f"Server random: {server_random}")
    logger.info(f"Random data length: {len(random_data) if random_data else 0}")
    logger.info(f"Signature length: {len(signature) if signature else 0}")
    logger.info(f"Random data preview: {random_data if random_data else 'None'}")
    
    if not signature or not random_data:
        logger.warning("USB Key login failed: missing signature or random data")
        return JsonResponse({'error': _('Missing signature or random data')}, status=400)
    
    # 验证随机数是否包含服务器随机数
    if server_random and server_random not in random_data:
        logger.warning(f"USB Key login failed: server random {server_random} not found in random data")
        return JsonResponse({'error': _('Invalid random data: server random not found')}, status=400)
    
    try:
        # 使用USB Key认证后端进行认证
        from authentication.backends.usb_key import USBKeyAuthBackend
        backend = USBKeyAuthBackend()
        
        user = backend.authenticate(
            request=request,
            username=username,
            signature=signature,
            random_data=random_data,
            server_random=server_random
        )
        
        if user:
            # 先登录用户
            auth_login(request, user, backend='authentication.backends.usb_key.USBKeyAuthBackend')
            logger.info(f"USB Key login successful for user {user.username}")
            
            # 使用与普通登录相同的重定向流程
            from authentication.views.utils import redirect_to_guard_view
            # 确保 next_url 被正确编码
            from urllib.parse import quote
            encoded_next = quote(next_url)
            return redirect_to_guard_view(query_string=f'next={encoded_next}')
        else:
            logger.warning("USB Key authentication failed: invalid signature or user not found")
            return JsonResponse({'error': _('USB Key authentication failed. Please check your USB Key and PIN.')}, status=400)
            
    except Exception as e:
        logger.error(f"USB Key login error: {e}")
        return JsonResponse({'error': _('USB Key authentication error. Please try again.')}, status=500)