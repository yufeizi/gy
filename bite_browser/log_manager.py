"""
日志管理模块
提供统一的日志记录功能
"""

import logging
import logging.handlers
import os
from datetime import datetime
from typing import Optional


class Logger:
    """日志管理器"""
    
    def __init__(self, name: str = "BrowserControl", log_file: str = "browser_control.log", 
                 level: str = "INFO", max_size: int = 10*1024*1024, backup_count: int = 5):
        """
        初始化日志器
        
        Args:
            name: 日志器名称
            log_file: 日志文件路径
            level: 日志级别
            max_size: 日志文件最大大小
            backup_count: 备份文件数量
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # 避免重复添加处理器
        if not self.logger.handlers:
            self._setup_handlers(log_file, max_size, backup_count)
    
    def _setup_handlers(self, log_file: str, max_size: int, backup_count: int):
        """设置日志处理器"""
        # 创建日志目录
        log_dir = os.path.dirname(log_file) if os.path.dirname(log_file) else "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # 文件处理器（轮转）
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_size, backupCount=backup_count, encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def debug(self, message: str):
        """记录调试信息"""
        self.logger.debug(message)
    
    def info(self, message: str):
        """记录一般信息"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """记录警告信息"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """记录错误信息"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """记录严重错误信息"""
        self.logger.critical(message)
    
    def log_browser_action(self, action: str, profile: str, success: bool = True, details: str = ""):
        """记录浏览器操作"""
        status = "成功" if success else "失败"
        message = f"浏览器操作 - {action} | 配置: {profile} | 状态: {status}"
        if details:
            message += f" | 详情: {details}"
        
        if success:
            self.info(message)
        else:
            self.error(message)
    
    def log_playwright_action(self, action: str, success: bool = True, details: str = ""):
        """记录Playwright操作"""
        status = "成功" if success else "失败"
        message = f"Playwright操作 - {action} | 状态: {status}"
        if details:
            message += f" | 详情: {details}"
        
        if success:
            self.info(message)
        else:
            self.error(message)


# 全局日志实例
_global_logger: Optional[Logger] = None


def setup_logging(name: str = "BrowserControl", log_file: str = "browser_control.log",
                 level: str = "INFO") -> None:
    """
    设置全局日志配置

    Args:
        name: 日志器名称
        log_file: 日志文件路径
        level: 日志级别
    """
    global _global_logger
    _global_logger = Logger(name, log_file, level)


def get_logger() -> Logger:
    """获取全局日志实例"""
    global _global_logger
    if _global_logger is None:
        _global_logger = Logger()
    return _global_logger


def init_logger(config: dict) -> Logger:
    """根据配置初始化日志器"""
    global _global_logger
    log_config = config.get('logging', {})
    
    _global_logger = Logger(
        name="BrowserControl",
        log_file=os.path.join("..", "logs", log_config.get('log_file', 'browser_control.log')),
        level=log_config.get('level', 'INFO'),
        max_size=log_config.get('max_log_size', 10*1024*1024),
        backup_count=log_config.get('backup_count', 5)
    )
    
    return _global_logger
