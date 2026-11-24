"""视频平台识别。"""

from urllib.parse import urlsplit


PANOPTO_HOST = "polyu.ap.panopto.com"
PLATFORM_DOMAINS = {
    "youtube": ("youtube.com", "youtu.be"),
    "bilibili": ("bilibili.com", "b23.tv"),
}


def identify_platform(url: str) -> str:
    url = url.strip()
    try:
        hostname = urlsplit(url if "://" in url or url.startswith("//") else f"//{url}").hostname or ""
    except ValueError:
        return "unsupported"
    if hostname.rstrip(".") == PANOPTO_HOST:
        return "panopto"
    for platform, domains in PLATFORM_DOMAINS.items():
        if any(hostname == domain or hostname.endswith("." + domain) for domain in domains):
            return platform
    return "unsupported"
