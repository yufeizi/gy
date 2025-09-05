#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
session_counter.py - 本次运行会话计数器
功能：
1. 记录本次软件运行的已点击商品数量
2. 提供给主程序显示框的接口
3. 程序启动时重置计数，运行期间累加
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path


class SessionCounter:
    """本次运行会话计数器"""
    
    def __init__(self):
        """初始化计数器"""
        # 创建logs目录
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # 会话计数文件
        self.session_file = self.logs_dir / "session_counter.json"
        
        # 初始化会话数据
        self.session_data = {
            'session_start_time': datetime.now().isoformat(),
            'clicked_count': 0,
            'filtered_count': 0,
            'scraped_count': 0,
            'last_updated': datetime.now().isoformat()
        }
        
        # 保存初始会话数据
        self._save_session_data()
        print(f"✅ 会话计数器初始化完成")
    
    def _save_session_data(self):
        """保存会话数据"""
        try:
            self.session_data['last_updated'] = datetime.now().isoformat()
            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(self.session_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 保存会话数据失败: {e}")
    
    def add_clicked_count(self, count: int = 1):
        """增加已点击商品计数"""
        self.session_data['clicked_count'] += count
        self._save_session_data()
        print(f"📊 本次运行已点击: {self.session_data['clicked_count']} 个")
    
    def add_filtered_count(self, count: int = 1):
        """增加已过滤商品计数"""
        self.session_data['filtered_count'] += count
        self._save_session_data()
    
    def add_scraped_count(self, count: int = 1):
        """增加已抓取商品计数"""
        self.session_data['scraped_count'] += count
        self._save_session_data()
    
    def get_clicked_count(self) -> int:
        """获取本次运行已点击数量"""
        return self.session_data['clicked_count']
    
    def get_filtered_count(self) -> int:
        """获取本次运行已过滤数量"""
        return self.session_data['filtered_count']
    
    def get_scraped_count(self) -> int:
        """获取本次运行已抓取数量"""
        return self.session_data['scraped_count']
    
    def get_session_summary(self) -> dict:
        """获取会话摘要"""
        return {
            'clicked': self.session_data['clicked_count'],
            'filtered': self.session_data['filtered_count'],
            'scraped': self.session_data['scraped_count'],
            'start_time': self.session_data['session_start_time'],
            'last_updated': self.session_data['last_updated']
        }


# 全局会话计数器实例
_session_counter = None


def get_session_counter():
    """获取全局会话计数器实例"""
    global _session_counter
    if _session_counter is None:
        _session_counter = SessionCounter()
    return _session_counter


def add_clicked_count(count: int = 1):
    """增加已点击商品计数（全局接口）"""
    counter = get_session_counter()
    counter.add_clicked_count(count)


def add_filtered_count(count: int = 1):
    """增加已过滤商品计数（全局接口）"""
    counter = get_session_counter()
    counter.add_filtered_count(count)


def add_scraped_count(count: int = 1):
    """增加已抓取商品计数（全局接口）"""
    counter = get_session_counter()
    counter.add_scraped_count(count)


def get_clicked_count() -> int:
    """获取本次运行已点击数量（全局接口）"""
    counter = get_session_counter()
    return counter.get_clicked_count()


def get_session_summary() -> dict:
    """获取会话摘要（全局接口）"""
    counter = get_session_counter()
    return counter.get_session_summary()


def reset_session():
    """重置会话计数（程序启动时调用）"""
    global _session_counter
    _session_counter = SessionCounter()
    print("🔄 会话计数器已重置")


if __name__ == "__main__":
    # 测试代码
    print("🧪 测试会话计数器")
    
    # 重置会话
    reset_session()
    
    # 模拟添加计数
    add_clicked_count(5)
    add_filtered_count(10)
    add_scraped_count(3)
    
    # 获取摘要
    summary = get_session_summary()
    print(f"📊 会话摘要: {summary}")
    
    print("✅ 测试完成")
