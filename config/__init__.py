"""
配置管理模块
"""

from .config_manager import (
    get_config_path, save_config, load_config, 
    update_thickness_history
)

__all__ = [
    'get_config_path', 'save_config', 'load_config', 
    'update_thickness_history'
]
