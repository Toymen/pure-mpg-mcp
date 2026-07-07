import json
import importlib.util
from pathlib import Path


PUBLIC_OPENAPI = Path("openapi/pure-public.openapi.json")
GENERATOR = Path("scripts/generate_public_openapi.py")


def _spec() -> dict:
    return json.loads(PUBLIC_OPENAPI.read_text(encoding="utf-8"))


def test_public_openapi_file_exists_and_is_openapi_31():
    spec = _spec()
    assert spec["openapi"] == "3.1.0"
    assert spec["servers"] == [{"url": "https://pure.mpg.de/rest"}]
    assert spec["security"] == []


def test_public_openapi_covers_critical_read_surface():
    paths = _spec()["paths"]
    expected = {
        ("post", "/items/search"),
        ("get", "/items/{itemId}"),
        ("get", "/items/{itemId}/export"),
        ("get", "/items/{itemId}/component/{componentId}/metadata"),
        ("post", "/ous/search"),
        ("get", "/ous/{ouId}"),
        ("get", "/ous/{ouId}/idPath"),
        ("post", "/contexts/search"),
        ("get", "/contexts/{ctxId}"),
        ("get", "/feed/recent"),
        ("get", "/feed/oa"),
        ("get", "/feed/organization/{ouId}"),
        ("get", "/miscellaneous/serviceInfo"),
    }
    for method, path in expected:
        assert method in paths[path]
        assert paths[path][method]["x-liveProbe"]["anonymous"] is True


def test_public_openapi_documents_real_live_limitations():
    paths = _spec()["paths"]
    assert paths["/ous/{ouId}/idPath"]["get"]["x-liveProbe"]["accept"] == "text/plain"
    assert "406" in paths["/feed/recent"]["get"]["x-liveProbe"]["limitation"]
    assert paths["/feed/search"]["get"]["x-liveProbe"]["confirmedPublic"] is False
    assert paths["/feed/search"]["get"]["x-liveProbe"]["observedStatus"] == 500
    assert "429" in paths["/items/search"]["post"]["responses"]


def test_public_openapi_matches_generator_output():
    spec = importlib.util.spec_from_file_location("generate_public_openapi", GENERATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert _spec() == module.build_openapi()
