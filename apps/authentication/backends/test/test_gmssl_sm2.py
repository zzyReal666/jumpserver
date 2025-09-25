from gmssl import sm2, func
import os
from Cryptodome.Util.asn1 import DerSequence

def sm2_demo():
    # 1. 生成密钥对 (32字节私钥, 64字节公钥)
    private_key = os.urandom(32).hex()   # 随机私钥
    
    # 先创建一个临时实例来生成公钥
    temp_sm2 = sm2.CryptSM2(public_key="", private_key=private_key)
    public_key = temp_sm2._kg(int(private_key, 16), temp_sm2.ecc_table['g'])
    
    print("私钥:", private_key)
    print("公钥:", public_key)
    
    # 创建用于签名的实例
    sm2_crypt = sm2.CryptSM2(public_key=public_key, private_key=private_key)

    # 2. 要签名的消息
    msg = b"Hello SM2 with gmssl!"
    print("消息:", msg)
    print("消息(字符串):", msg.decode('utf-8'))

    # 3. 生成签名
    # 使用SM3哈希的签名方法
    random_hex_str = os.urandom(32).hex()
    signature = sm2_crypt.sign_with_sm3(msg, random_hex_str)
    print("随机数K:", random_hex_str)
    print("签名(SM3):", signature)
    
    # 3.1 转换为DER格式签名，并生成04前缀公钥
    r = int(signature[:64], 16)
    s = int(signature[64:], 16)
    der_seq = DerSequence()
    der_seq.append(r)
    der_seq.append(s)
    der_signature = der_seq.encode().hex()
    public_key_04 = public_key if public_key.startswith('04') else ('04' + public_key)
    
    # 打印验签前的详细信息
    print()
    print("=== 验签前详细信息 ===")
    print(f"public_key: {public_key}")
    print(f"signature(raw r||s): {signature}")
    print(f"msg: {msg}")
    print()

    # 4. 验签
    sm2_crypt_verify = sm2.CryptSM2(public_key=public_key, private_key=None)
    is_valid = sm2_crypt_verify.verify_with_sm3(signature, msg)
    print("验签结果(SM3):", is_valid)


if __name__ == "__main__":
    sm2_demo()