"""Offline checks of the optional cache age limit and retry count of the outbound gateway."""
import json

import pytest

from src import sources
from src.sources import QuakeNetError, http_get
from tests.test_sources import URL, FakeResponse, net  # noqa: F401  (net is a fixture)


def _age_cache(url, seconds):
    """Pretend the cached copy of url was retrieved `seconds` ago."""
    from datetime import datetime, timedelta, timezone
    _, meta_path = sources.cache_paths(url)
    meta = json.loads(meta_path.read_text())
    then = datetime.now(timezone.utc) - timedelta(seconds=seconds)
    meta["retrieved_utc"] = then.strftime("%Y-%m-%dT%H:%M:%SZ")
    meta_path.write_text(json.dumps(meta))


def test_default_cache_never_expires(net):
    net["script"] = [FakeResponse(b"old")]
    http_get(URL)
    _age_cache(URL, 10 * 365 * 86400)
    assert http_get(URL) == b"old" and len(net["calls"]) == 1


def test_fresh_copy_is_served_within_max_age(net):
    net["script"] = [FakeResponse(b"old")]
    http_get(URL)
    _age_cache(URL, 30)
    assert http_get(URL, max_age_s=600) == b"old" and len(net["calls"]) == 1
    assert 25 <= sources.cache_age_s(URL) <= 90


def test_stale_copy_is_fetched_again_and_replaced(net):
    net["script"] = [FakeResponse(b"old"), FakeResponse(b"new")]
    http_get(URL)
    _age_cache(URL, 3600)
    assert http_get(URL, max_age_s=600) == b"new" and len(net["calls"]) == 2
    assert http_get(URL) == b"new"


def test_stale_copy_is_served_offline(net, monkeypatch):
    net["script"] = [FakeResponse(b"old")]
    http_get(URL)
    _age_cache(URL, 3600)
    monkeypatch.setenv("QUAKENET_OFFLINE", "1")
    assert http_get(URL, max_age_s=600) == b"old" and len(net["calls"]) == 1


def test_retries_and_timeout_can_be_lowered(net):
    net["script"] = [TimeoutError("slow"), TimeoutError("slow")]
    with pytest.raises(QuakeNetError) as err:
        http_get(URL, retries=1, timeout_s=90)
    assert "2 attempts" in err.value.message and len(net["calls"]) == 2
    assert all(timeout == 90 for _, timeout in net["calls"])


def test_cache_age_of_unknown_url_is_none(net):
    assert sources.cache_age_s(URL) is None
