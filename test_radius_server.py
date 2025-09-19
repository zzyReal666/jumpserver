#!/usr/bin/env python3
import socket
import struct
import hashlib
import random

def create_radius_packet(code, identifier, authenticator, attributes, secret):
    """创建RADIUS数据包"""
    # RADIUS包头：Code(1) + Identifier(1) + Length(2) + Authenticator(16)
    header = struct.pack('!BBH', code, identifier, 20 + len(attributes))
    header += authenticator
    
    # 添加属性
    packet = header + attributes
    
    # 计算长度
    length = len(packet)
    packet = struct.pack('!BBH', code, identifier, length) + authenticator + attributes
    
    return packet

def create_access_accept(identifier, request_authenticator, secret):
    """创建Access-Accept响应"""
    # 创建响应认证器
    response_authenticator = hashlib.md5(
        struct.pack('!BBH', 2, identifier, 20) +  # Access-Accept header
        request_authenticator +
        secret.encode()
    ).digest()
    
    # 创建属性（可选）
    attributes = b''
    
    return create_radius_packet(2, identifier, response_authenticator, attributes, secret)

def create_access_reject(identifier, request_authenticator, secret):
    """创建Access-Reject响应"""
    response_authenticator = hashlib.md5(
        struct.pack('!BBH', 3, identifier, 20) +  # Access-Reject header
        request_authenticator +
        secret.encode()
    ).digest()
    
    return create_radius_packet(3, identifier, response_authenticator, b'', secret)

def handle_radius_request(data, client_address, secret):
    """处理RADIUS请求"""
    if len(data) < 20:
        return None
    
    # 解析包头
    code, identifier, length = struct.unpack('!BBH', data[:4])
    request_authenticator = data[4:20]
    
    print(f"收到RADIUS请求: Code={code}, ID={identifier}, Length={length}")
    print(f"客户端: {client_address}")
    
    # 简单的用户验证（这里总是接受）
    if code == 1:  # Access-Request
        print("发送Access-Accept")
        return create_access_accept(identifier, request_authenticator, secret)
    else:
        print("发送Access-Reject")
        return create_access_reject(identifier, request_authenticator, secret)

def main():
    secret = 'testing123'
    port = 1812
    
    # 创建UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('localhost', port))
    
    print(f"RADIUS测试服务器启动在端口 {port}")
    print(f"共享密钥: {secret}")
    print("等待连接...")
    
    try:
        while True:
            data, client_address = sock.recvfrom(1024)
            print(f"\n收到来自 {client_address} 的数据")
            
            response = handle_radius_request(data, client_address, secret)
            if response:
                sock.sendto(response, client_address)
                print("响应已发送")
                
    except KeyboardInterrupt:
        print("\n服务器停止")
    finally:
        sock.close()

if __name__ == '__main__':
    main()
