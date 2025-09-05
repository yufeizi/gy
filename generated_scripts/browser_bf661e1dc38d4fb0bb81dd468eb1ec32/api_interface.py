#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
api_interface.py - 主程序接口
功能：
1. 提供给主程序的API接口
2. 获取本次运行的各种计数数据
3. 获取系统状态信息
"""

import json
import os
from pathlib import Path
from datetime import datetime
from session_counter import get_session_summary, get_clicked_count


class MainProgramAPI:
    """主程序API接口"""
    
    def __init__(self):
        """初始化API接口"""
        self.logs_dir = Path("logs")
        self.logs_dir.mkdir(exist_ok=True)
        
        # API状态文件
        self.api_status_file = self.logs_dir / "api_status.json"
        
    def get_session_counts(self) -> dict:
        """获取本次运行的计数数据"""
        try:
            summary = get_session_summary()
            return {
                'success': True,
                'data': {
                    'clicked_count': summary['clicked'],
                    'filtered_count': summary['filtered'],
                    'scraped_count': summary['scraped'],
                    'session_start': summary['start_time'],
                    'last_updated': summary['last_updated']
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'data': {
                    'clicked_count': 0,
                    'filtered_count': 0,
                    'scraped_count': 0
                }
            }
    
    def get_clicked_count_only(self) -> int:
        """只获取已点击数量（供主程序显示框使用）"""
        try:
            return get_clicked_count()
        except Exception as e:
            print(f"❌ 获取点击计数失败: {e}")
            return 0
    
    def get_system_status(self) -> dict:
        """获取系统运行状态"""
        try:
            # 检查各个组件的状态
            status = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'components': {}
            }
            
            # 检查会话计数器
            try:
                clicked = get_clicked_count()
                status['components']['session_counter'] = {
                    'status': 'running',
                    'clicked_count': clicked
                }
            except:
                status['components']['session_counter'] = {
                    'status': 'error',
                    'clicked_count': 0
                }
            
            # 检查任务状态文件
            task_status_file = self.logs_dir / "task_status.json"
            if task_status_file.exists():
                try:
                    with open(task_status_file, 'r', encoding='utf-8') as f:
                        task_status = json.load(f)
                    status['components']['task_queue'] = {
                        'status': 'running',
                        'tasks': task_status
                    }
                except:
                    status['components']['task_queue'] = {
                        'status': 'error',
                        'tasks': {}
                    }
            else:
                status['components']['task_queue'] = {
                    'status': 'idle',
                    'tasks': {}
                }
            
            # 检查监听程序状态（通过进程或文件检查）
            # 这里可以添加更多的状态检查逻辑
            
            return status
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'components': {}
            }
    
    def save_api_status(self, status_data: dict):
        """保存API状态到文件"""
        try:
            with open(self.api_status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ 保存API状态失败: {e}")


# 全局API实例
_api_instance = None


def get_api_instance():
    """获取全局API实例"""
    global _api_instance
    if _api_instance is None:
        _api_instance = MainProgramAPI()
    return _api_instance


def get_clicked_count_for_main() -> int:
    """供主程序调用的点击计数接口"""
    api = get_api_instance()
    return api.get_clicked_count_only()


def get_session_data_for_main() -> dict:
    """供主程序调用的会话数据接口"""
    api = get_api_instance()
    return api.get_session_counts()


def get_system_status_for_main() -> dict:
    """供主程序调用的系统状态接口"""
    api = get_api_instance()
    return api.get_system_status()


if __name__ == "__main__":
    # 测试代码
    print("🧪 测试主程序API接口")
    
    # 测试获取点击计数
    clicked = get_clicked_count_for_main()
    print(f"📊 本次运行已点击: {clicked} 个")
    
    # 测试获取会话数据
    session_data = get_session_data_for_main()
    print(f"📋 会话数据: {session_data}")
    
    # 测试获取系统状态
    system_status = get_system_status_for_main()
    print(f"🔧 系统状态: {system_status}")
    
    print("✅ 测试完成")
