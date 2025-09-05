#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔒 安全管理器 - 4级安全防护系统
📱 Level 1: 基础安全 (环境变量 + 输入验证) - 5分钟
🔒 Level 2: HTTPS (SSL/TLS 加密传输) - 10分钟
🛡️ Level 3: 访问控制 (API密钥验证) - 15分钟
📊 Level 4: 审计日志 (操作记录) - 5分钟
"""

import os
import json
import logging
import re
import ipaddress
from pathlib import Path
from typing import Dict, Tuple, List
from datetime import datetime


class SecurityManager:
    """🔒 安全管理器"""
    
    def __init__(self):
        self.security_level = 1  # 默认基础安全
        self.audit_logger = self._setup_audit_logger()
        
    def _setup_audit_logger(self) -> logging.Logger:
        """设置审计日志"""
        logger = logging.getLogger('security_audit')
        logger.setLevel(logging.INFO)
        
        # 创建日志目录
        log_dir = Path("logs/security")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件处理器
        handler = logging.FileHandler(
            log_dir / f"security_audit_{datetime.now().strftime('%Y%m%d')}.log",
            encoding='utf-8'
        )
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    # 📱 Level 1: 基础安全
    def validate_server_url(self, url: str) -> Tuple[bool, str]:
        """验证服务器URL格式"""
        try:
            # URL格式验证
            url_pattern = re.compile(
                r'^https?://'  # http:// 或 https://
                r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # 域名
                r'localhost|'  # localhost
                r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP地址
                r'(?::\d+)?'  # 端口
                r'(?:/?|[/?]\S+)$', re.IGNORECASE)
            
            if not url_pattern.match(url):
                return False, "URL格式无效"
            
            # 安全检查
            if url.startswith('http://') and 'localhost' not in url and '127.0.0.1' not in url:
                return False, "生产环境必须使用HTTPS"
            
            return True, "URL验证通过"
            
        except Exception as e:
            return False, f"URL验证失败: {e}"
    
    def validate_encryption_key(self, key: str) -> Tuple[bool, str]:
        """验证加密密钥强度"""
        try:
            if len(key) < 16:
                return False, "密钥长度至少16位"
            
            if key in ["default_password_change_me", "your_secret_password_2025"]:
                return False, "不能使用默认密钥"
            
            # 密钥强度检查
            has_upper = any(c.isupper() for c in key)
            has_lower = any(c.islower() for c in key)
            has_digit = any(c.isdigit() for c in key)
            has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in key)
            
            strength_score = sum([has_upper, has_lower, has_digit, has_special])
            
            if strength_score < 3:
                return False, "密钥强度不足，需要包含大小写字母、数字和特殊字符"
            
            return True, f"密钥强度: {'强' if strength_score == 4 else '中等'}"
            
        except Exception as e:
            return False, f"密钥验证失败: {e}"
    
    def sanitize_input(self, data: str) -> str:
        """输入数据清理"""
        try:
            # 移除潜在的恶意字符
            dangerous_chars = ['<', '>', '"', "'", '&', '\x00', '\r', '\n']
            for char in dangerous_chars:
                data = data.replace(char, '')
            
            # 限制长度
            if len(data) > 1000:
                data = data[:1000]
            
            return data.strip()
            
        except Exception:
            return ""

    def mask_url(self, url: str) -> str:
        """脱敏URL中的IP地址和敏感信息"""
        try:
            if not url:
                return ""

            import re

            # 匹配IPv4地址
            ipv4_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'

            # 脱敏IP地址：保留第一段和最后一段，中间用*替代
            def mask_ip(match):
                ip = match.group(0)
                parts = ip.split('.')
                if len(parts) == 4:
                    return f"{parts[0]}.*.*.{parts[3]}"
                return "***"

            masked_url = re.sub(ipv4_pattern, mask_ip, url)

            # 脱敏域名（如果不是本地地址）
            domain_pattern = r'://([^/]+)'
            domain_match = re.search(domain_pattern, masked_url)
            if domain_match:
                domain = domain_match.group(1)
                if not any(keyword in domain.lower() for keyword in ['*', '127.0.0.1', 'localhost']):
                    # 脱敏域名，只保留协议和路径
                    masked_url = masked_url.replace(domain, "***")

            return masked_url

        except Exception:
            return "***"

    # 🔒 Level 2: HTTPS
    def check_https_config(self, server_url: str) -> Tuple[bool, str]:
        """检查HTTPS配置"""
        try:
            if server_url.startswith('https://'):
                return True, "HTTPS配置正确"
            elif 'localhost' in server_url or '127.0.0.1' in server_url:
                return True, "本地开发环境，HTTP可接受"
            else:
                return False, "生产环境必须使用HTTPS"
                
        except Exception as e:
            return False, f"HTTPS检查失败: {e}"
    
    # 🛡️ Level 3: 访问控制
    def validate_ip_whitelist(self, client_ip: str, whitelist: List[str]) -> Tuple[bool, str]:
        """验证IP白名单"""
        try:
            if not whitelist:  # 空白名单表示允许所有
                return True, "无IP限制"
            
            client_addr = ipaddress.ip_address(client_ip)
            
            for allowed_ip in whitelist:
                try:
                    if '/' in allowed_ip:  # CIDR格式
                        network = ipaddress.ip_network(allowed_ip, strict=False)
                        if client_addr in network:
                            return True, f"IP {client_ip} 在允许的网段 {allowed_ip} 中"
                    else:  # 单个IP
                        if client_addr == ipaddress.ip_address(allowed_ip):
                            return True, f"IP {client_ip} 在白名单中"
                except ValueError:
                    continue
            
            return False, f"IP {client_ip} 不在白名单中"
            
        except Exception as e:
            return False, f"IP验证失败: {e}"
    
    def validate_api_key(self, provided_key: str, expected_key: str) -> Tuple[bool, str]:
        """验证API密钥"""
        try:
            if not expected_key:
                return True, "未配置API密钥验证"
            
            # 使用安全的字符串比较
            if len(provided_key) != len(expected_key):
                return False, "API密钥无效"
            
            # 防止时序攻击
            result = 0
            for x, y in zip(provided_key, expected_key):
                result |= ord(x) ^ ord(y)
            
            if result == 0:
                return True, "API密钥验证通过"
            else:
                return False, "API密钥无效"
                
        except Exception as e:
            return False, f"API密钥验证失败: {e}"
    
    # 📊 Level 4: 审计日志
    def log_security_event(self, event_type: str, details: Dict, level: str = "INFO"):
        """记录安全事件"""
        try:
            event_data = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "details": details,
                "level": level
            }
            
            log_message = f"{event_type}: {json.dumps(details, ensure_ascii=False)}"
            
            if level == "ERROR":
                self.audit_logger.error(log_message)
            elif level == "WARNING":
                self.audit_logger.warning(log_message)
            else:
                self.audit_logger.info(log_message)
                
        except Exception as e:
            print(f"⚠️ 审计日志记录失败: {e}")
    
    def get_security_status(self) -> Dict:
        """获取安全状态报告"""
        try:
            # 检查环境变量
            env_vars = {
                "PDD_SERVER_URL": os.getenv('PDD_SERVER_URL'),
                "PDD_ENCRYPTION_KEY": os.getenv('PDD_ENCRYPTION_KEY'),
                "PDD_API_KEY": os.getenv('PDD_API_KEY'),
                "PDD_ALLOWED_IPS": os.getenv('PDD_ALLOWED_IPS')
            }
            
            status = {
                "security_level": self.security_level,
                "timestamp": datetime.now().isoformat(),
                "checks": {
                    "environment_variables": bool(env_vars["PDD_SERVER_URL"]),
                    "https_enabled": bool(env_vars["PDD_SERVER_URL"] and env_vars["PDD_SERVER_URL"].startswith('https://')),
                    "api_key_configured": bool(env_vars["PDD_API_KEY"]),
                    "ip_whitelist_configured": bool(env_vars["PDD_ALLOWED_IPS"])
                },
                "recommendations": []
            }
            
            # 生成建议
            if not status["checks"]["environment_variables"]:
                status["recommendations"].append("配置环境变量 PDD_SERVER_URL 和 PDD_ENCRYPTION_KEY")
            
            if not status["checks"]["https_enabled"]:
                status["recommendations"].append("生产环境启用HTTPS")
            
            if not status["checks"]["api_key_configured"]:
                status["recommendations"].append("配置API密钥增强安全性")
            
            return status
            
        except Exception as e:
            return {"error": f"安全状态检查失败: {e}"}


# 全局安全管理器实例
security_manager = SecurityManager()
