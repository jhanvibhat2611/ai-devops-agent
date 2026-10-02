"""Read-only local Elasticsearch smoke check; opt in explicitly."""
import os
import pytest

@pytest.mark.live
def test_live_elasticsearch():
    if os.getenv("RUN_LIVE_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_TESTS=1 for local service checks")
    from elasticsearch_client import es
    assert es.ping()
