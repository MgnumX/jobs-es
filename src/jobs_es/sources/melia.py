"""Meliá Hotels International: SuccessFactors SSR (careers.melia.com)."""
import hashlib
import re
from urllib.parse import unquote, urljoin

from .. import httpclient, register, report, source_debug
from ..models import Job
from ..normalize import classify_text, parse_salary, sector_of

NAME = "melia"
BASE_URL = "https://careers.melia.com"


def fetch_search_page(startrow: int, opts: dict | None = None) -> str:
    url = f"{BASE_URL}/search/?q=&locationsearch=espa%C3%B1a&startrow={startrow}"
    resp = httpclient.get(url, source=NAME)
    source_debug.maybe_save_fixture(NAME, f"startrow_{startrow}", resp.text, opts)
    return resp.text


def parse_search_links(html: str) -> list[str]:
    links = _parse_search_links_selectolax(html)
    if not links:
        links = _parse_search_links_regex(html)
    return list(dict.fromkeys(links))


def _parse_search_links_selectolax(html: str) -> list[str]:
    try:
        from selectolax.parser import HTMLParser
    except ImportError:
        return []
    tree = HTMLParser(html)
    out = []
    for a in tree.css("a[href]"):
        href = a.attributes.get("href") or ""
        if "/job/" in href:
            out.append(urljoin(BASE_URL, href))
    return out


def _parse_search_links_regex(html: str) -> list[str]:
    out = []
    for href in re.findall(r'href="([^"]*/job/[^"]*)"', html, re.I):
        out.append(urljoin(BASE_URL, href))
    return out


def parse_detail(html: str) -> dict:
    try:
        from selectolax.parser import HTMLParser
        tree = HTMLParser(html)
        title_node = tree.css_first("h1")
        body = tree.body.text(separator="\n", strip=True) if tree.body else httpclient.strip_tags(html)
        return {"title": title_node.text(strip=True) if title_node else "", "text": body}
    except Exception:
        return {"title": "", "text": httpclient.strip_tags(html)}


def fetch_detail(url: str, info: dict, opts: dict | None = None):
    use_cache = bool((opts or {}).get("use_cache", True))
    try:
        resp = httpclient.get(url, source=NAME, cache=use_cache, cache_ttl_hours=24*7)
    except Exception:
        info["http_errors"] += 1
        raise
    info["detail_fetched"] += 1
    if getattr(resp, "from_cache", False):
        info["cache_hits"] += 1
    label = "detail_" + hashlib.sha1(url.encode()).hexdigest()[:10]
    source_debug.maybe_save_fixture(NAME, label, resp.text, opts)
    try:
        return parse_detail(resp.text)
    except Exception:
        info["parse_errors"] += 1
        return {"title": "", "text": httpclient.strip_tags(resp.text)}


def _city_from_path(path: str) -> str:
    try:
        slug = unquote(path.split("/")[2])
        first = slug.split("-")[0]
        return first.strip().title()[:40]
    except Exception:
        return ""


@register("melia")
def run(con, *, pages: int = 10, detail_budget: int = 250, budget: int | None = None, opts: dict | None = None, **kwargs):  # ponytail: budget alias
    if budget is not None:
        detail_budget = budget
    opts = opts or {}
    info = report.new_info()
    if opts.get("no_detail"):
        detail_budget = 0

    seen: dict[str, str] = {}
    for page_index in range(pages):
        startrow = page_index * 25
        try:
            html = fetch_search_page(startrow, opts)
        except Exception:
            info["http_errors"] += 1
            report.add_warning(info, f"http_error_startrow_{startrow}")
            break
        links = parse_search_links(html)
        info["listed"] += len(links)
        if not links and len(html) > 5000:
            report.add_warning(info, "zero_links")
            source_debug.maybe_save_debug(NAME, f"startrow_{startrow}", html, opts)
        for link in links:
            if opts.get("limit") and len(seen) >= opts["limit"]:
                break
            if link not in seen:
                seen[link] = link

        if opts.get("limit") and len(seen) >= opts["limit"]:
            break
        # early stop if no new links (deduped)
        if not links:
            break

    jobs: list[Job] = []
    for url in seen:
        # title from URL slug for now, detail will refine
        slug_title = unquote(url.split("/")[2]).replace("-", " ").strip() if "/job/" in url else ""
        city = _city_from_path(url)
        jobs.append(Job(source=NAME, url=url, title=slug_title, company="Meliá Hotels",
                        city=city, province=city, sector=sector_of(slug_title), direct=True))

    from ..db import known_ids
    seen_ids = known_ids(con, {j.id for j in jobs})
    fresh = [j for j in jobs if j.id not in seen_ids]
    info["new"] = len(fresh)

    for j in fresh[:detail_budget]:
        if opts.get("no_detail"):
            break
        try:
            detail = fetch_detail(j.url, info, opts)
        except Exception:
            continue
        text = detail.get("text", "")
        title = detail.get("title") or j.title
        j.title = title
        j.housing, j.food = classify_text(text)
        j.hourly, j.salary_text = parse_salary(text)
        j.sector = sector_of(title, text)
        j.text = text[:1500]

    return jobs, info
