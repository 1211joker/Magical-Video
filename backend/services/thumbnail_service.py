"""获取受支持的视频平台封面。"""

import httpx

from services.youtube_network import get_youtube_connection

YOUTUBE_CDN = ("ytimg.com", "img.youtube.com")
BILIBILI_CDN = ("hdslb.com", "biliimg.com")
IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/avif"}
MAX_THUMBNAIL_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 4


class ThumbnailError(RuntimeError):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status


def _thumbnail_platform(url: httpx.URL) -> str:
    if (url.scheme != "https" or url.port not in (None, 443)
            or url.username or url.password):
        raise ThumbnailError(400, "封面地址不受支持")
    for platform, domains in (("youtube", YOUTUBE_CDN), ("bilibili", BILIBILI_CDN)):
        if any(url.host == domain or url.host.endswith("." + domain) for domain in domains):
            return platform
    raise ThumbnailError(400, "封面地址不受支持")


async def fetch_thumbnail(image_url: str) -> tuple[bytes, str]:
    try:
        target = httpx.URL(image_url)
        # 兼容 B 站旧封面地址，始终使用 HTTPS 获取图片。
        if target.scheme == "http" and target.port is None:
            target = target.copy_with(scheme="https")
        platform = _thumbnail_platform(target)
        youtube = platform == "youtube"
        connection = await get_youtube_connection() if youtube else None
        headers = {
            "Referer": "https://www.youtube.com/" if youtube else "https://www.bilibili.com/",
            "User-Agent": "Mozilla/5.0",
            "Accept-Encoding": "identity",
        }
        async with httpx.AsyncClient(
            timeout=15, proxy=connection.proxy if connection else None, trust_env=not youtube,
        ) as client:
            for _ in range(MAX_REDIRECTS + 1):
                # 重新校验每次跳转，避免 CDN 跳转到其他服务。
                if _thumbnail_platform(target) != platform:
                    raise ThumbnailError(400, "封面跳转地址不受支持")
                async with client.stream("GET", target, headers=headers, follow_redirects=False) as response:
                    if response.has_redirect_location:
                        target = target.join(response.headers["location"])
                        continue
                    if response.status_code != 200:
                        raise ThumbnailError(404, "封面图获取失败")
                    media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    if media_type not in IMAGE_TYPES:
                        raise ThumbnailError(502, "封面响应不是支持的图片格式")
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(content) + len(chunk) > MAX_THUMBNAIL_BYTES:
                            raise ThumbnailError(502, "封面图过大")
                        content.extend(chunk)
                    return bytes(content), media_type
        raise ThumbnailError(502, "封面图跳转次数过多")
    except httpx.InvalidURL:
        raise ThumbnailError(400, "封面地址无效") from None
    except httpx.TimeoutException:
        raise ThumbnailError(504, "封面图加载超时") from None
    except httpx.RequestError:
        raise ThumbnailError(502, "封面图获取失败") from None
