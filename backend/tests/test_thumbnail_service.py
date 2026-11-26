import unittest
from unittest.mock import patch

import httpx

from services.thumbnail_service import ThumbnailError, fetch_thumbnail


class ThumbnailTests(unittest.IsolatedAsyncioTestCase):
    async def test_supported_cover_can_follow_same_platform_redirect(self):
        visited = []

        def upstream(request):
            visited.append(request.url)
            if len(visited) == 1:
                return httpx.Response(302, headers={"Location": "https://i2.hdslb.com/next.jpg"})
            return httpx.Response(200, headers={"Content-Type": "image/jpeg"}, content=b"fixture image")

        make_client = httpx.AsyncClient
        with patch("services.thumbnail_service.httpx.AsyncClient",
                   side_effect=lambda **kwargs: make_client(transport=httpx.MockTransport(upstream), **kwargs)):
            content, kind = await fetch_thumbnail("http://i0.hdslb.com/cover.jpg")
        self.assertEqual((content, kind), (b"fixture image", "image/jpeg"))
        self.assertEqual([(url.scheme, url.host) for url in visited],
                         [("https", "i0.hdslb.com"), ("https", "i2.hdslb.com")])

    async def test_disallowed_destinations_are_never_requested(self):
        visited = []

        def upstream(request):
            visited.append(request.url.host)
            return httpx.Response(302, headers={"Location": "https://example.invalid/cover.jpg"})

        make_client = httpx.AsyncClient
        with patch("services.thumbnail_service.httpx.AsyncClient",
                   side_effect=lambda **kwargs: make_client(transport=httpx.MockTransport(upstream), **kwargs)):
            with self.assertRaises(ThumbnailError):
                await fetch_thumbnail("https://example.invalid/cover.jpg")
            with self.assertRaises(ThumbnailError):
                await fetch_thumbnail("https://i0.hdslb.com/cover.jpg")
        self.assertEqual(visited, ["i0.hdslb.com"])

    async def test_cover_rejects_active_content(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, headers={"Content-Type": "text/html"}, content=b"<p>content</p>"),
        )
        make_client = httpx.AsyncClient
        with patch("services.thumbnail_service.httpx.AsyncClient",
                   side_effect=lambda **kwargs: make_client(transport=transport, **kwargs)):
            with self.assertRaises(ThumbnailError) as caught:
                await fetch_thumbnail("https://i0.hdslb.com/cover.jpg")
        self.assertEqual(caught.exception.status, 502)
