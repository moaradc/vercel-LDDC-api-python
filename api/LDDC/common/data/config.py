# SPDX-FileCopyrightText: Copyright (C) 2024-2025 沉默の金 <cmzj@cmzj.org>
# SPDX-License-Identifier: GPL-3.0-only

"""Web环境配置管理模块

这个模块提供了Web环境下的配置管理，不依赖PySide6
"""

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional
import tempfile


# Web环境路径处理
def get_web_paths():
    """获取Web环境的路径"""
    # 在Web环境中使用临时目录
    temp_base = Path(tempfile.gettempdir()) / "LDDC"
    config_dir = temp_base / "config"
    default_save_lyrics_dir = temp_base / "lyrics"
    
    # 确保目录存在
    config_dir.mkdir(parents=True, exist_ok=True)
    default_save_lyrics_dir.mkdir(parents=True, exist_ok=True)
    
    return config_dir, default_save_lyrics_dir


config_dir, default_save_lyrics_dir = get_web_paths()


class ConfigSignal:
    """Web环境的信号模拟类（不依赖PySide6）"""
    def __init__(self):
        self._callbacks = []
    
    def connect(self, callback):
        """连接回调函数"""
        self._callbacks.append(callback)
    
    def emit(self, *args, **kwargs):
        """触发信号"""
        for callback in self._callbacks:
            try:
                callback(*args, **kwargs)
            except Exception as e:
                print(f"ConfigSignal error: {e}")


class ConfigSigal:
    """Web环境的配置信号容器"""
    def __init__(self):
        self.lyrics_changed = ConfigSignal()
        self.desktop_lyrics_changed = ConfigSignal()


class Config(dict):
    """Web环境的配置管理类

    1. 使用Lock保证线程安全
    2. 使用方法类似字典
    3. 使用json格式存储配置文件
    注意: 用于Lock导致这个类并不高效,不应该在需要高性能的地方使用
    """

    def __init__(self) -> None:
        self.lock = None
        self.config_path = config_dir / "config.json"
        self.__singal = ConfigSigal()
        self.lyrics_changed = self.__singal.lyrics_changed  # 在歌词相关配置改变时发出信号
        self.desktop_lyrics_changed = self.__singal.desktop_lyrics_changed  # 在桌面歌词相关配置改变时发出信号

        self.default_cfg = {
            # Web环境专用配置
            "lyrics_file_name_fmt": "%<artist> - %<title> (%<id>)",
            "default_save_path": str(default_save_lyrics_dir),
            
            # 歌词搜索配置
            "multi_search_sources": ["QM", "KG", "NE"],
            "langs_order": ["roma", "orig", "ts"],
            "skip_inst_lyrics": True,
            "auto_select": True,
            "add_end_timestamp_line": False,
            "lrc_ms_digit_count": 3,
            "last_ref_line_time_sty": 0,  # 0: 与当前原文起始时间相同 1: 与下一行原文起始时间接近
            "lrc_tag_info_src": 0,  # 0: 从歌词源获取 1: 从歌曲文件获取
            
            # API配置
            "translate_source": "BING",
            "translate_target_lang": "SIMPLIFIED_CHINESE",
            "openai_base_url": "",
            "openai_api_key": "",
            "openai_model": "",
            
            # 日志和系统配置
            "language": "auto",
            "log_level": "INFO",
            "auto_check_update": False,  # Web环境通常不检查更新
            
            # Web API特有配置
            "api_timeout": 30,
            "cache_enabled": True,
            "cache_ttl": 3600,  # 1小时
            "rate_limit_per_minute": 60,
            "enable_cors": True,
            "debug_mode": False,
            
            # 桌面歌词相关配置（Web环境可能不需要，但保持兼容）
            "desktop_lyrics_played_colors": [(0, 255, 255), (0, 128, 255)],
            "desktop_lyrics_unplayed_colors": [(255, 0, 0), (255, 128, 128)],
            "desktop_lyrics_default_langs": ["orig", "ts"],
            "desktop_lyrics_langs_order": ["roma", "orig", "ts"],
            "desktop_lyrics_sources": ["QM", "KG", "NE"],
            "desktop_lyrics_font_family": "",
            "desktop_lyrics_refresh_rate": -1,
            "desktop_lyrics_rect": (),
            "desktop_lyrics_font_size": 30.0,
            
            # 保留但不使用的配置（为了兼容性）
            "ID3_version": "v2.3",
            "color_scheme": "auto",
        }
        
        # 从环境变量覆盖配置
        self._update_from_env()

        self.reset()
        self.read_config()
        self.lock = Lock()

    def _update_from_env(self):
        """从环境变量更新默认配置"""
        env_mapping = {
            "LDDC_LOG_LEVEL": "log_level",
            "LDDC_DEFAULT_SOURCES": "multi_search_sources",
            "LDDC_API_TIMEOUT": "api_timeout",
            "LDDC_CACHE_ENABLED": "cache_enabled",
            "LDDC_CACHE_TTL": "cache_ttl",
            "LDDC_RATE_LIMIT": "rate_limit_per_minute",
            "LDDC_DEBUG_MODE": "debug_mode",
        }
        
        for env_var, config_key in env_mapping.items():
            if value := os.environ.get(env_var):
                # 处理不同类型的数据
                if config_key in ["multi_search_sources"]:
                    # 逗号分隔的列表
                    self.default_cfg[config_key] = [s.strip() for s in value.split(",")]
                elif config_key in ["cache_enabled", "debug_mode", "enable_cors"]:
                    # 布尔值
                    self.default_cfg[config_key] = value.lower() in ("true", "1", "yes")
                elif config_key in ["api_timeout", "cache_ttl", "rate_limit_per_minute"]:
                    # 整数值
                    try:
                        self.default_cfg[config_key] = int(value)
                    except ValueError:
                        pass  # 保持默认值
                else:
                    # 字符串值
                    self.default_cfg[config_key] = value

    def reset(self) -> None:
        for key, value in self.default_cfg.items():
            self[key] = value

    def write_config(self) -> None:
        """写入配置文件"""
        try:
            with self.config_path.open("w", encoding="utf-8") as f:
                json.dump(dict(self), f, ensure_ascii=False, indent=4)
        except (IOError, OSError) as e:
            # Web环境可能无法写入文件，使用内存配置
            print(f"Warning: Cannot write config file in web environment: {e}")

    def read_config(self) -> None:
        """读取配置文件"""
        if self.config_path.is_file():
            try:
                with self.config_path.open(encoding="utf-8") as f:
                    cfg = json.load(f)
                if isinstance(cfg, dict):
                    for key, value in cfg.items():
                        if key in self and type(value) is type(self[key]):
                            self[key] = value
                        elif isinstance(value, list) and isinstance(self[key], tuple):
                            self[key] = tuple(value)
                        elif isinstance(value, float) and isinstance(self[key], int):
                            self[key] = int(value)
                        elif isinstance(value, int) and isinstance(self[key], float):
                            self[key] = float(value)
                        # Web环境：允许动态添加新配置项
                        elif key not in self:
                            self[key] = value
            except Exception as e:
                print(f"Warning: Cannot read config file: {e}")
                self.write_config()

    def setitem(self, key: Any, value: Any) -> None:
        self[key] = value

    def __getitem__(self, key: Any) -> Any:
        if self.lock is None:
            return super().__getitem__(key)
        with self.lock:
            return super().__getitem__(key)

    def __setitem__(self, key: Any, value: Any) -> None:
        if self.lock is None:
            super().__setitem__(key, value)
            return
        with self.lock:
            super().__setitem__(key, value)
            self.write_config()

        # 触发信号（如果有监听器）
        if key in ("langs_order", "lrc_ms_digit_count", "add_end_timestamp_line", "last_ref_line_time_sty", "lrc_tag_info_src"):
            self.lyrics_changed.emit((key, value))
        elif key in (
            "desktop_lyrics_font_family",
            "desktop_lyrics_played_colors",
            "desktop_lyrics_unplayed_colors",
            "desktop_lyrics_default_langs",
            "desktop_lyrics_refresh_rate",
            "desktop_lyrics_langs_order",
        ):
            self.desktop_lyrics_changed.emit((key, value))

    def __delitem__(self, key: Any) -> None:
        if self.lock is None:
            super().__delitem__(key)
            return
        with self.lock:
            super().__delitem__(key)
            self.write_config()

    def get_web_api_config(self) -> Dict[str, Any]:
        """获取Web API专用的配置"""
        return {
            "timeout": self["api_timeout"],
            "cache_enabled": self["cache_enabled"],
            "cache_ttl": self["cache_ttl"],
            "rate_limit": self["rate_limit_per_minute"],
            "enable_cors": self["enable_cors"],
            "debug": self["debug_mode"],
            "default_sources": self["multi_search_sources"],
        }


# 全局配置实例
cfg = Config()


# 可选：创建环境检测函数
def is_web_environment() -> bool:
    """检测是否是Web环境"""
    return bool(os.environ.get('VERCEL') or 
                os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or 
                os.environ.get('LDDC_WEB_MODE'))


# 可选：创建简化配置获取函数
def get_api_config(key: str, default: Any = None) -> Any:
    """获取API配置的简化函数"""
    return cfg.get(key, default)


# 可选：设置环境变量以启用Web模式
if is_web_environment():
    # 确保在Web环境中使用合适的配置
    cfg["auto_check_update"] = False
    cfg["enable_cors"] = True
    cfg["cache_enabled"] = True
