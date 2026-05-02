"""Pexels source tests with respx-mocked HTTP."""

from __future__ import annotations

import httpx
import pytest
import respx

from shortstack_worker.sources.pexels import (
    PEXELS_SEARCH_URL,
    PexelsPhoto,
    download_photo,
    search_photos,
)


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    """Force the Pexels settings used by the source under test."""
    monkeypatch.setenv("PEXELS_API_KEY", "test-pexels-key")
    import shortstack_core.settings as st

    st._settings = None
    yield
    st._settings = None


SAMPLE_SEARCH = {
    "page": 1,
    "per_page": 5,
    "photos": [
        {
            "id": 1234,
            "url": "https://www.pexels.com/photo/hand-on-phone-1234/",
            "alt": "person holding a phone in their hand",
            "src": {
                "original": "https://images.pexels.com/photos/1234/orig.jpg",
                "portrait": "https://images.pexels.com/photos/1234/portrait.jpg",
            },
        },
        {
            "id": 5678,
            "url": "https://www.pexels.com/photo/desk-5678/",
            "alt": "messy desk with notebook",
            "src": {
                "portrait": "https://images.pexels.com/photos/5678/portrait.jpg",
            },
        },
    ],
}


@respx.mock
def test_search_photos_normalises_entries():
    respx.get(PEXELS_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=SAMPLE_SEARCH)
    )
    photos = search_photos("hand on phone")

    assert len(photos) == 2
    assert isinstance(photos[0], PexelsPhoto)
    assert photos[0].id == 1234
    assert photos[0].page_url.endswith("/hand-on-phone-1234/")
    assert photos[0].src_portrait.endswith("/1234/portrait.jpg")
    assert photos[0].alt == "person holding a phone in their hand"


@respx.mock
def test_search_photos_sends_correct_url_headers_params():
    seen: list[httpx.Request] = []

    def _capture(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"photos": []})

    respx.get(PEXELS_SEARCH_URL).mock(side_effect=_capture)
    search_photos("delete app icon", per_page=7)

    assert len(seen) == 1
    req = seen[0]
    assert req.url.path == "/v1/search"
    assert req.url.params["query"] == "delete app icon"
    assert req.url.params["per_page"] == "7"
    assert req.url.params["orientation"] == "portrait"
    assert req.headers["authorization"] == "test-pexels-key"


@respx.mock
def test_search_photos_skips_entries_missing_required_fields():
    payload = {
        "photos": [
            {"id": 1, "url": "https://example.com/a", "src": {"portrait": "x"}, "alt": "ok"},
            # Missing id
            {"url": "https://example.com/b", "src": {"portrait": "x"}, "alt": ""},
            # Missing src.portrait
            {"id": 3, "url": "https://example.com/c", "src": {}, "alt": ""},
            # Missing url
            {"id": 4, "src": {"portrait": "x"}, "alt": ""},
            # Missing src entirely
            {"id": 5, "url": "https://example.com/e", "alt": ""},
        ]
    }
    respx.get(PEXELS_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=payload)
    )
    photos = search_photos("anything")
    assert [p.id for p in photos] == [1]


@respx.mock
def test_search_photos_returns_empty_on_no_hits():
    respx.get(PEXELS_SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"photos": []})
    )
    assert search_photos("nothing-here") == []


@respx.mock
def test_search_photos_handles_missing_photos_key():
    respx.get(PEXELS_SEARCH_URL).mock(
        return_value=httpx.Response(200, json={"page": 1})
    )
    assert search_photos("ghost") == []


@respx.mock
def test_search_photos_raises_on_4xx():
    respx.get(PEXELS_SEARCH_URL).mock(
        return_value=httpx.Response(401, json={"error": "bad key"})
    )
    with pytest.raises(httpx.HTTPStatusError):
        search_photos("oops")


@respx.mock
def test_search_photos_raises_on_5xx():
    respx.get(PEXELS_SEARCH_URL).mock(
        return_value=httpx.Response(503, json={})
    )
    with pytest.raises(httpx.HTTPStatusError):
        search_photos("down")


@respx.mock
def test_download_photo_returns_bytes():
    fake_jpg = b"\xff\xd8\xff\xe0fake-jpg"
    url = "https://images.pexels.com/photos/1234/portrait.jpg"
    respx.get(url).mock(return_value=httpx.Response(200, content=fake_jpg))

    out = download_photo(url)
    assert out == fake_jpg


@respx.mock
def test_download_photo_raises_on_error():
    url = "https://images.pexels.com/photos/dead/portrait.jpg"
    respx.get(url).mock(return_value=httpx.Response(404, content=b""))
    with pytest.raises(httpx.HTTPStatusError):
        download_photo(url)
