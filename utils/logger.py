#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日志系统模块

提供统一的日志记录功能，支持控制台和文件输出
"""

import os
import sys
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional


class THzLogger:
    """THz光学参数分析系统的日志管理类"""
    
    _instance: Optional['THzLogger'] = None
    _initialized: bool = False
    
    def __new__(cls) -> 'THzLogger':
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化日志系统"""
        if THzLogger._initialized:
            return
        
        THzLogger._initialized = True
        
        # 创建日志目录
        self.log_dir = self._get_log_directory()
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 创建主日志器
        self.logger = logging.getLogger('THzAnalyzer')
        self.logger.setLevel(logging.DEBUG)
        
        # 清除可能存在的处理器
        self.logger.handlers.clear()
        
        # 创建格式化器
        self.console_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        self.file_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(module)s:%(lineno)d] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 添加控制台处理器
        self._add_console_handler()
        
        # 添加文件处理器
        self._add_file_handler()
        
        self.logger.info("日志系统初始化完成")
    
    def _get_log_directory(self) -> str:
        """获取日志文件目录"""
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller 打包环境
            base_path = os.path.dirname(sys.executable)
        else:
            # 开发环境
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        return os.path.join(base_path, 'logs')
    
    def _add_console_handler(self):
        """添加控制台日志处理器"""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(self.console_formatter)
        self.logger.addHandler(console_handler)
    
    def _add_file_handler(self):
        """添加文件日志处理器（带日志轮转）"""
        log_file = os.path.join(
            self.log_dir, 
            f'thz_analyzer_{datetime.now().strftime("%Y%m%d")}.log'
        )
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(self.file_formatter)
        self.logger.addHandler(file_handler)
    
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
    
    def exception(self, message: str):
        """记录异常信息（包含堆栈跟踪）"""
        self.logger.exception(message)


# 全局日志实例
_logger: Optional[THzLogger] = None


def get_logger() -> THzLogger:
    """获取全局日志实例"""
    global _logger
    if _logger is None:
        _logger = THzLogger()
    return _logger


# 便捷函数
def debug(message: str):
    """记录调试信息"""
    get_logger().debug(message)


def info(message: str):
    """记录一般信息"""
    get_logger().info(message)


def warning(message: str):
    """记录警告信息"""
    get_logger().warning(message)


def error(message: str):
    """记录错误信息"""
    get_logger().error(message)


def critical(message: str):
    """记录严重错误信息"""
    get_logger().critical(message)


def exception(message: str):
    """记录异常信息（包含堆栈跟踪）"""
    get_logger().exception(message)
