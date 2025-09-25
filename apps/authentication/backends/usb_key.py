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

    def authenticate(self, request, username=None, signature=None, random_data=None, server_random=None, **kwargs):
        """USB Key认证逻辑"""
        if not signature or not random_data:
            logger.warning("USB Key auth failed: missing signature or random data")
            return None

        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        
        try:
            user = UserModel._default_manager.get_by_natural_key(username)
        except UserModel.DoesNotExist:
            logger.warning(f"USB Key auth failed: user {username} not found")
            return None

        # 检查用户是否配置了USB Key
        if not user.usb_key_enabled or not user.usb_key_public_key:
            logger.warning(f"USB Key auth failed: user {username} has no USB key configured or disabled")
            return None

        # 验证签名
        if self.verify_signature(user, signature, random_data, server_random):
            logger.info(f"USB Key auth successful for user {username}")
            return user
        else:
            logger.warning(f"USB Key auth failed: signature verification failed for user {username}")
            return None

    def verify_signature(self, user, signature, random_data, server_random=None):
        """验证USB Key签名"""
        try:
            # 获取用户的USB Key公钥
            public_key = user.usb_key_public_key
            if not public_key:
                logger.warning(f"USB Key auth failed: user {user.username} has no public key")
                return False
            
            # 记录认证信息用于调试
            logger.info(f"USB Key auth attempt for user {user.username}, serial: {user.usb_key_serial_number}")
            logger.info(f"Random data received: {random_data}")
            
            # 验证随机数是否包含服务器随机数
            if server_random and server_random not in random_data:
                logger.warning(f"USB Key auth failed: server random {server_random} not found in random data")
                return False
            
            # 使用gmssl库进行SM2签名验证
            try:
                from gmssl import sm2
                import base64
                
                # 解析X.509格式的Base64公钥
                public_key_str = self._parse_public_key(public_key)
                if not public_key_str:
                    logger.error("Failed to parse X.509 Base64 public key")
                    return False
                
                # 解析Base64格式的签名
                signature_str = self._parse_signature(signature)
                if not signature_str:
                    logger.error("Failed to parse Base64 signature")
                    return False
                
                # 准备验证数据
                random_data_bytes = random_data.encode('utf-8')
                
                # 创建SM2实例
                sm2_crypt = sm2.CryptSM2(public_key=public_key_str, private_key=None)
                
                logger.info("=== USB Key验签参数信息 ===")
                logger.info(f"公钥: {public_key_str}")
                logger.info(f"签名: {signature_str}")
                logger.info(f"数据: {random_data}")
            
                
                logger.info("=== 开始SM2签名验证 ===")
                logger.info("使用gmssl库进行SM3签名验证")
                
                # 使用gmssl库验证Base64转换后的签名（使用SM3哈希）
                is_valid = sm2_crypt.verify_with_sm3(signature_str, random_data_bytes)
                logger.info(f"gmssl SM3验证结果: {is_valid}")
                logger.info(f"=== 最终验证结果: {is_valid} ===")
                
                return is_valid
                
            except ImportError:
                logger.error("gmssl library not available, USB Key verification cannot proceed")
                return False
            except Exception as e:
                logger.error(f"SM2 verification failed: {e}")
                return False
            
        except Exception as e:
            logger.error(f"USB Key signature verification error: {e}")
            return False
    
    def _parse_public_key(self, public_key):
        """解析X.509格式的Base64公钥，base64编码的x509格式公钥，需要转换为HEX编码的不带04前缀的ECC公钥"""
        try:
            import base64
            
            # 解析Base64格式的公钥
            public_key_bytes = base64.b64decode(public_key)
            public_key_str = public_key_bytes.hex()
            logger.info("Public key parsed as Base64 format")
            
            # 检查是否为X.509格式，需要转换为SM2格式
            if public_key_str.startswith('00010000'):
                logger.info("Detected X.509 format public key, converting to SM2 format")
                if len(public_key_str) >= 136:  # 00010000(8) + 128(64字节*2)
                    # 跳过00010000，添加04前缀，取标准64字节数据
                    sm2_public_key =  public_key_str[8:136]
                    logger.info(f"Converted to SM2 format: {sm2_public_key[:10]}...")
                    return sm2_public_key
                else:
                    logger.warning("X.509 format public key too short")
                    return None
            elif public_key_str.startswith('04'):
                logger.info("Public key already in SM2 format")
                return public_key_str
            else:
                logger.warning(f"Unknown public key format, starts with: {public_key_str[:8]}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to parse X.509 Base64 public key: {e}")
            return None
    
    def _parse_signature(self, signature):
        """解析Base64格式的签名，base64编码的x509格式签名，需要转换为HEX编码的r||s格式"""
        try:
            import base64
            from Cryptodome.Util.asn1 import DerSequence
            
            # 解析Base64格式的签名
            signature_bytes = base64.b64decode(signature)
            signature_str = signature_bytes.hex()
            
            # 检查是否为DER格式（以30开头）
            if signature_str.startswith('30'):
                logger.info("Detected DER format signature, converting to r||s format")
                try:
                    # 解析DER格式
                    der_seq = DerSequence()
                    der_seq.decode(signature_bytes)
                    r = der_seq[0]
                    s = der_seq[1]
                    
                    # 转换为r||s格式（每个值32字节，64个十六进制字符）
                    r_hex = format(r, '064x')
                    s_hex = format(s, '064x')
                    r_s_signature = r_hex + s_hex
                    
                    logger.info(f"DER signature converted to r||s format: {r_s_signature[:16]}...")
                    return r_s_signature
                    
                except Exception as e:
                    logger.warning(f"Failed to parse DER signature, using raw format: {e}")
                    return signature_str
            else:
                # 直接使用原始格式
                logger.info("Signature parsed as raw r||s format")
                return signature_str
            
        except Exception as e:
            logger.error(f"Failed to parse signature: {e}")
            return None

    def get_user(self, user_id):
        try:
            user = UserModel._default_manager.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
        return user if self.user_can_authenticate(user) else None