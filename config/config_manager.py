import os
import sys
import json


def get_config_path():
    """获取配置文件的路径"""
    try:
        # 使用_MEIPASS获取临时解压目录
        if hasattr(sys, '_MEIPASS'):
            base_path = os.path.dirname(sys.executable)
        else:
            # 使用当前脚本目录
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, 'thz_config.json')
    except Exception:
        # 如果出错，回退到当前工作目录
        return os.path.join(os.getcwd(), 'thz_config.json')


def save_config(config_data):
    """保存配置到文件"""
    try:
        with open(get_config_path(), 'w') as f:
            json.dump(config_data, f)
        return True
    except Exception as e:
        print(f"保存配置时出错: {e}")
        return False


def load_config():
    """从文件读取配置"""
    config_path = get_config_path()
    default_config = {
        "thickness": 0.5,
        "thickness_history": [0.5],  # 历史厚度值
        "last_open_dir": "",         # 上次打开文件的路径
        "last_save_dir": "",         # 上次保存文件的路径
        "start_row": 1,              # 数据起始行，默认1
        "use_window": False,         # 是否使用Tukey窗函数
        "window_t_start": 0.0,       # Tukey窗起始时间
        "window_t_end": 30.0,        # Tukey窗结束时间
        "window_alpha": 0.5          # Tukey窗alpha参数
    }
    
    if not os.path.exists(config_path):
        return default_config
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            # 兼容老配置
            if "start_row" not in config:
                config["start_row"] = 1
            if "use_window" not in config:
                config["use_window"] = False
            if "window_t_start" not in config:
                config["window_t_start"] = 0.0
            if "window_t_end" not in config:
                config["window_t_end"] = 30.0
            if "window_alpha" not in config:
                config["window_alpha"] = 0.5
            return config
    except Exception as e:
        print(f"读取配置时出错: {e}")
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
