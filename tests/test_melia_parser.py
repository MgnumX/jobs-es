from pathlib import Path

import pytest

from jobs_es.sources.melia import parse_search_links

FIXTURE = Path("tests/fixtures/melia_startrow_0.html")


@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture melia_startrow_0.html missing")
def test_melia_parse_search_links():
    html = FIXTURE.read_text(encoding="utf-8")
    links = parse_search_links(html)

    assert len(links) > 0
    assert all("/job/" in link for link in links)
