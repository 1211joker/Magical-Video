"""视频平台识别。"""

from urllib.parse import SplitResult, urlsplit


PANOPTO_HOST = "polyu.ap.panopto.com"
PLATFORM_DOMAINS = {
    "youtube": ("youtube.com", "youtu.be"),
    "bilibili": ("bilibili.com", "b23.tv"),
}


def split_video_url(url: str) -> SplitResult:
    """将无协议链接同样解析为包含主机名的 URL。"""
    url = url.strip()
    return urlsplit(url if "://" in url or url.startswith("//") else f"//{url}")


def identify_platform(url: str) -> str:
    try:
        hostname = split_video_url(url).hostname or ""
    except ValueError:
        return "unsupported"
    if hostname.rstrip(".") == PANOPTO_HOST:
        return "panopto"
    for platform, domains in PLATFORM_DOMAINS.items():
        if any(hostname == domain or hostname.endswith("." + domain) for domain in domains):
            return platform
    return "unsupported"
