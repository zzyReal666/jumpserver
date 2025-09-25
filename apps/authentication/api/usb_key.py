# -*- coding: utf-8 -*-
#
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.contrib.auth import login as auth_login
from django.utils.translation import gettext as _

from common.utils import get_logger
from authentication.backends.usb_key import USBKeyAuthBackend

logger = get_logger(__file__)


@api_view(['POST'])
@permission_classes([AllowAny])
def usb_key_authenticate(request):
    """USB Key API认证接口"""
    try:
        signature = request.data.get('signature')
        random_data = request.data.get('random_data')
        username = request.data.get('username')
        
        if not signature or not random_data:
            return Response({
                'error': _('Missing signature or random data')
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 使用USB Key认证后端进行认证
        backend = USBKeyAuthBackend()
        
        user = backend.authenticate(
            request=request,
            username=username,
            signature=signature,
            random_data=random_data
        )
        
        if user:
            auth_login(request, user, backend='authentication.backends.usb_key.USBKeyAuthBackend')
            logger.info(f"USB Key API authentication successful for user {user.username}")
            return Response({
                'success': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'name': user.name,
                    'email': user.email,
                }
            })
        else:
            logger.warning("USB Key API authentication failed: invalid signature or user not found")
            return Response({
                'error': _('USB Key authentication failed. Please check your USB Key and PIN.')
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"USB Key API authentication error: {e}")
        return Response({
            'error': _('USB Key authentication error. Please try again.')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def usb_key_status(request):
    """检查USB Key认证状态"""
    try:
        # 检查USB Key认证是否启用
        backend = USBKeyAuthBackend()
        is_enabled = backend.is_enabled()
        
        return Response({
            'enabled': is_enabled,
            'message': _('USB Key authentication is enabled') if is_enabled else _('USB Key authentication is disabled')
        })
        
    except Exception as e:
        logger.error(f"USB Key status check error: {e}")
        return Response({
            'enabled': False,
            'error': _('Failed to check USB Key authentication status')
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
