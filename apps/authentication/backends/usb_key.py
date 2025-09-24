# -*- coding: utf-8 -*-
#
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from common.utils import get_logger
from .base import JMSBaseAuthBackend

UserModel = get_user_model()
logger = get_logger(__file__)

__all__ = ['USBKeyAuthBackend']


class USBKeyAuthBackend(JMSBaseAuthBackend):
    """USB Key OTP认证后端"""
    
    @staticmethod
    def is_enabled():
        """检查USB Key认证是否启用"""
        return getattr(settings, 'USB_KEY_AUTH_ENABLED', True)

    def authenticate(self, request, username=None, signature=None, random_data=None, **kwargs):
        """USB Key认证逻辑"""
        if not signature or not random_data:
            return None

        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        
        try:
            user = UserModel._default_manager.get_by_natural_key(username)
        except UserModel.DoesNotExist:
            logger.warning(f"USB Key auth failed: user {username} not found")
            return None

        # 检查用户是否配置了USB Key
        if not user.usb_key_public_key:
            logger.warning(f"USB Key auth failed: user {username} has no USB key configured")
            return None

        # 验证签名
        if self.verify_signature(user, signature, random_data):
            logger.info(f"USB Key auth successful for user {username}")
            return user
        else:
            logger.warning(f"USB Key auth failed: signature verification failed for user {username}")
            return None

    def verify_signature(self, user, signature, random_data):
        """验证USB Key签名"""
        try:
            # 获取用户的USB Key公钥
            public_key = user.usb_key_public_key
            if not public_key:
                return False
            
            # 这里需要根据您的ukeyfunc.js中的SM2签名算法来实现
            # 由于SM2签名验证比较复杂，这里提供一个框架
            # 您可能需要安装相应的加密库，如gmssl或cryptography
            
            # 示例：使用gmssl库进行SM2签名验证
            from gmssl import sm2, func
            
            # 解析公钥（假设公钥是十六进制字符串）
            public_key_bytes = bytes.fromhex(public_key)
            
            # 创建SM2对象
            sm2_crypt = sm2.CryptSM2(
                public_key=public_key_bytes,
                private_key=None  # 验证时不需要私钥
            )
            
            # 验证签名
            random_data_bytes = random_data.encode('utf-8')
            signature_bytes = bytes.fromhex(signature)
            
            # 这里需要根据实际的SM2签名格式进行调整
            is_valid = sm2_crypt.verify(signature_bytes, random_data_bytes)
            
            return is_valid
            
        except Exception as e:
            logger.error(f"USB Key signature verification error: {e}")
            return False

    def get_user(self, user_id):
        try:
            user = UserModel._default_manager.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
        return user if self.user_can_authenticate(user) else None