# -*- coding: utf-8 -*-
"""统一日志工具：按模块获取带命名的 logger。"""
import logging


def get_logger(name: str) -> logging.Logger:
    """获取指定模块的 logger（由 main.py 统一配置级别与格式）。"""
    return logging.getLogger(name)
