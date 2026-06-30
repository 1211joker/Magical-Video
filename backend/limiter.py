"""
共享的 slowapi Limiter 实例 — 避免 main.py ↔ routers 循环导入。
所有路由模块导入此实例来添加限流装饰器。
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
