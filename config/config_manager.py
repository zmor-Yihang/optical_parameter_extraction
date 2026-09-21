import os
import json

from utils import info, warning, error
from utils.app_paths import get_app_base_dir
from core.version import UPDATE_URL


def get_config_path():
    """获取配置文件的路径"""
    try:
        # 打包环境(exe 所在目录)或开发环境(项目根目录)
        return os.path.join(get_app_base_dir(), 'thz_config.json')
    except Exception:
        # 如果出错，回退到当前工作目录
        return os.path.join(os.getcwd(), 'thz_config.json')


def save_config(config_data):
    """保存配置到文件"""
    try:
        with open(get_config_path(), 'w') as f:
            json.dump(config_data, f)
        info("配置已保存")
        return True
    except Exception as e:
        error(f"保存配置时出错: {e}")
        return False


def load_config():
    """从文件读取配置"""
    config_path = get_config_path()
    default_config = {
        "thickness": 0.5,
        "thickness_history": [0.5],  # 历史厚度值
        "last_open_dir": "",         # 上次打开文件的路径
        "last_save_dir": "",         # 上次保存文件的路径
        "use_window": False,         # 是否使用Tukey窗函数
        "window_t_start": 0.0,       # Tukey窗起始时间
        "window_t_end": 30.0,        # Tukey窗结束时间
        "window_alpha": 0.5,         # Tukey窗alpha参数
        "standardized_dir": "",      # 阶段一标准 txt 输出目录
        "scan_mode": "each",         # 多扫描文件处理方式: each / average
        "auto_check_update": True,   # 启动时自动检查更新
        "last_update_check": "",     # 上次检查更新时间（ISO 格式，用于控制检查频率）
        "update_source": UPDATE_URL  # 更新源地址（version.json）
    }
    
    if not os.path.exists(config_path):
        return default_config
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            # 兼容老配置：缺失的键用默认值补齐
            for key, value in default_config.items():
                config.setdefault(key, value)
            info("配置已加载")
            return config
    except Exception as e:
        warning(f"读取配置时出错: {e}")
        return default_config


def update_thickness_history(config, new_thickness):
    """更新厚度历史记录，保留最近3个值"""
    if "thickness_history" not in config:
        config["thickness_history"] = []
    
    # 转换为float确保比较正确
    new_thickness = float(new_thickness)
    
    # 如果新值已在历史记录中，将其移到最前面
    if new_thickness in config["thickness_history"]:
        config["thickness_history"].remove(new_thickness)
    
    # 添加新值到列表开头
    config["thickness_history"].insert(0, new_thickness)
    
    # 保持最多3个记录
    config["thickness_history"] = config["thickness_history"][:3]
    
    return config
