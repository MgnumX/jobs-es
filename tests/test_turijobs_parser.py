from pathlib import Path

import pytest

from jobs_es.sources.turijobs import parse_listing

FIXTURE = Path("tests/fixtures/turijobs_page_1.html")


@pytest.mark.skipif(not FIXTURE.exists(), reason="fixture turijobs_page_1.html missing")
def test_turijobs_parse_listing():
    html = FIXTURE.read_text(encoding="utf-8")
    items = parse_listing(html)

    assert len(items) > 0
    assert items[0]["url"].startswith("http")
