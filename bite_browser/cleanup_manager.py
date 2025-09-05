"""
清理管理模块
负责程序退出时的资源清理工作
"""

import atexit
import signal
import sys
import os
from typing import Optional, List, Callable
from log_manager import get_logger


class CleanupManager:
    """清理管理器"""
    
    def __init__(self):
        """初始化清理管理器"""
        self.logger = get_logger()
        self.cleanup_functions: List[Callable] = []
        self.is_cleaning = False
        
        # 注册清理函数
        atexit.register(self.cleanup)
        
        # 注册信号处理器
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, self._signal_handler)
        if hasattr(signal, 'SIGINT'):
            signal.signal(signal.SIGINT, self._signal_handler)
        if os.name == 'nt':  # Windows
            if hasattr(signal, 'SIGBREAK'):
                signal.signal(signal.SIGBREAK, self._signal_handler)
    
    def register_cleanup_function(self, func: Callable):
        """注册清理函数"""
        if func not in self.cleanup_functions:
            self.cleanup_functions.append(func)
            self.logger.debug(f"注册清理函数: {func.__name__}")
    
    def unregister_cleanup_function(self, func: Callable):
        """取消注册清理函数"""
        if func in self.cleanup_functions:
            self.cleanup_functions.remove(func)
            self.logger.debug(f"取消注册清理函数: {func.__name__}")
    
    def cleanup(self):
        """执行清理工作"""
        if self.is_cleaning:
            return
        
        self.is_cleaning = True
        self.logger.info("开始执行程序清理...")
        
        # 执行所有注册的清理函数
        for func in self.cleanup_functions:
            try:
                func()
            except Exception as e:
                self.logger.error(f"清理函数执行失败 {func.__name__}: {e}")
        
        self.logger.info("程序清理完成")
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        self.logger.info(f"接收到信号 {signum}，开始清理...")
        self.cleanup()
        sys.exit(0)


# 全局清理管理器实例
_cleanup_manager: Optional[CleanupManager] = None


def get_cleanup_manager() -> CleanupManager:
    """获取全局清理管理器实例"""
    global _cleanup_manager
    if _cleanup_manager is None:
        _cleanup_manager = CleanupManager()
    return _cleanup_manager


def register_cleanup(func: Callable):
    """注册清理函数的便捷方法"""
    get_cleanup_manager().register_cleanup_function(func)


def unregister_cleanup(func: Callable):
    """取消注册清理函数的便捷方法"""
    get_cleanup_manager().unregister_cleanup_function(func)


def setup_cleanup():
    """设置清理管理器"""
    # 初始化清理管理器
    cleanup_manager = get_cleanup_manager()
    return cleanup_manager
