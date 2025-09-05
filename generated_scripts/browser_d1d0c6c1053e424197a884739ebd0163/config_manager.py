#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=================================================================
配置文件管理器 - PDD自动化系统
=================================================================
职责：提供配置文件的加载、验证和访问功能
避免在主控制器中出现硬编码的文件路径和字典键
=================================================================
"""

import json
import os
from typing import Dict, List, Any, Optional

class ConfigManager:
    """配置管理器类"""

    def __init__(self, config_path: str = "config_api.json"):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config_data: Dict[str, Any] = {}
        self.load_config()

    def load_config(self) -> None:
        """加载配置文件"""
        try:
            if not os.path.exists(self.config_path):
                raise FileNotFoundError(f"配置文件不存在: {self.config_path}")

            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config_data = json.load(f)

            print(f"✅ 配置文件加载成功: {self.config_path}")

        except Exception as e:
            print(f"❌ 配置文件加载失败: {e}")
            raise

    # =================================================================
    # 基础配置获取方法 - 适配现有config_api.json结构
    # =================================================================

    def get_browser_id(self) -> str:
        """获取浏览器ID"""
        if 'browser_info' in self.config_data:
            return self.config_data['browser_info']['browser_id']
        else:
            # 直接从根级别获取
            return self.config_data.get('browser_id', 'a6636f134a7e468abcbd0fc68244c523')

    def get_debug_port(self) -> int:
        """获取调试端口"""
        if 'browser_info' in self.config_data:
            return self.config_data['browser_info'].get('debug_port', 50569)
        else:
            # 直接从根级别获取
            return self.config_data.get('debug_port', 50569)

    def get_config(self) -> Dict[str, Any]:
        """获取完整配置数据"""
        # 🔥 修复：适配server_config到cloud_server的映射
        if 'server_config' in self.config_data and 'cloud_server' not in self.config_data:
            server_config = self.config_data['server_config']
            upload_url = server_config.get('upload_url', 'http://localhost:8888')
            
            # 从upload_url提取基础server_url
            if '/api/upload' in upload_url:
                server_url = upload_url.replace('/api/upload', '')
            else:
                server_url = upload_url.replace('/upload', '')
            
            # 创建cloud_server配置
            self.config_data['cloud_server'] = {
                'server_url': server_url,
                'client_id': 'PDD_CLIENT_001'
            }
            print(f"🔧 已自动适配服务器配置: {server_url}")
            
        return self.config_data

    def get_keywords(self) -> List[str]:
        """获取关键词列表"""
        # 先尝试根级别的search_keywords
        keywords = self.config_data.get('search_keywords', [])
        if not keywords:
            # 再尝试parse_settings下的search_keywords
            keywords = self.config_data.get('parse_settings', {}).get('search_keywords', [])

        # 清理关键词，移除"---已搜索"后缀
        clean_keywords = []
        for keyword in keywords:
            if isinstance(keyword, str):
                clean_keyword = keyword.replace('---已搜索', '').strip()
                if clean_keyword:
                    clean_keywords.append(clean_keyword)

        return clean_keywords

    def get_max_clicks_per_keyword(self) -> int:
        """获取每个关键词最大点击数"""
        if 'parse_settings' in self.config_data:
            return self.config_data['parse_settings'].get('target_count', 33)
        else:
            return self.config_data.get('target_count', 33)

    def get_max_pages_per_keyword(self) -> int:
        """获取每个关键词最大页数"""
        if 'parse_settings' in self.config_data:
            return self.config_data['parse_settings'].get('page_count', 4)
        else:
            return self.config_data.get('page_count', 4)

    def get_wait_after_search(self) -> int:
        """获取搜索后等待时间"""
        if 'parse_settings' in self.config_data:
            return self.config_data['parse_settings'].get('search_page_wait', 11)
        else:
            return self.config_data.get('search_page_wait', 11)

    def get_wait_after_click_to_detail(self) -> int:
        """获取点击到详情页后等待时间"""
        if 'parse_settings' in self.config_data:
            return self.config_data['parse_settings'].get('wait_time', 5)
        else:
            return self.config_data.get('wait_time', 5)

    def get_wait_between_product_clicks(self) -> int:
        """获取商品点击间隔时间"""
        if 'timing_settings' in self.config_data:
            return self.config_data['timing_settings'].get('random_wait_min', 1)
        else:
            return 2

if __name__ == "__main__":
    # 测试配置管理器
    try:
        cm = ConfigManager()
        print("📋 配置信息:")
        print(f"浏览器ID: {cm.get_browser_id()}")
        print(f"关键词数量: {len(cm.get_keywords())}")
        print(f"最大点击数: {cm.get_max_clicks_per_keyword()}")
        print(f"最大页数: {cm.get_max_pages_per_keyword()}")
        print("✅ 配置管理器测试通过")
    except Exception as e:
        print(f"❌ 配置管理器测试失败: {e}")