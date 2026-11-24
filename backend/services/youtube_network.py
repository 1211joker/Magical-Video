"""为服务端的 YouTube 请求检测并选择可用网络路径。"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Literal, Optional
from urllib.parse import urlsplit
from urllib.request import getproxies

import httpx

from config import YTDLP_PROXY

PROBE_URL = "https://www.youtube.com/generate_204"
PROBE_TIMEOUT = 12
CONNECTION_CACHE_SECONDS = 20


@dataclass(frozen=True)
class YouTubeConnection:
    proxy: Optional[str] = field(default=None, repr=False)

    @property
    def mode(self) -> Literal["direct", "proxy"]:
        return "proxy" if self.proxy else "direct"


class YouTubeNetworkUnavailable(Exception):
    def __init__(self, has_proxy_settings: bool):
        if has_proxy_settings:
            self.code = "youtube_proxy_unavailable"
            message = "当前网络无法访问 YouTube，已检测到的代理也未能连接。"
        else:
            self.code = "youtube_network_unavailable"
            message = "当前网络无法访问 YouTube，服务端没有检测到可用的代理配置。"
        super().__init__(message)


_connection_cache: Optional[tuple[float, YouTubeConnection]] = None


def _proxy_url(address: str, default_scheme: str = "http") -> Optional[str]:
    if not address:
        return None
    if "://" not in address:
        address = f"{default_scheme}://{address}"
    try:
        parsed = urlsplit(address)
        if not parsed.hostname or parsed.scheme not in ("http", "https", "socks5", "socks5h"):
            return None
    except ValueError:
        return None
    # 由 SOCKS 代理解析 YouTube 域名，沿用同一个地址供各网络客户端使用。
    return parsed._replace(scheme="socks5h").geturl() if parsed.scheme == "socks5" else address


async def _youtube_is_reachable(proxy: Optional[str]) -> bool:
    try:
        async with httpx.AsyncClient(proxy=proxy, trust_env=False, timeout=PROBE_TIMEOUT) as client:
            response = await asyncio.wait_for(client.get(PROBE_URL), timeout=PROBE_TIMEOUT)
        return response.status_code == 204
    except (httpx.HTTPError, asyncio.TimeoutError, ValueError, ImportError):
        return False


async def get_youtube_connection() -> YouTubeConnection:
    global _connection_cache
    if _connection_cache and _connection_cache[0] > time.monotonic():
        return _connection_cache[1]

    configured = YTDLP_PROXY.strip()
    proxy = _proxy_url(configured)
    direct = YouTubeConnection()
    candidates = [YouTubeConnection(proxy), direct] if proxy else [direct]

    settings = getproxies()
    has_proxy_settings = bool(configured)
    for key in ("https", "all", "http", "socks"):
        address = settings.get(key, "").strip()
        has_proxy_settings |= bool(address)
        proxy = _proxy_url(address, "socks5h" if key == "socks" else "http")
        if proxy:
            candidates.append(YouTubeConnection(proxy))

    for connection in dict.fromkeys(candidates):
        if await _youtube_is_reachable(connection.proxy):
            _connection_cache = (time.monotonic() + CONNECTION_CACHE_SECONDS, connection)
            return connection

    # 失败时重新检测，让用户打开代理后可以立即重试。
    raise YouTubeNetworkUnavailable(has_proxy_settings)
