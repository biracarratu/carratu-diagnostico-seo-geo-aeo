"""Verificacao de links internos, redirecionamentos e saude do sitemap.

Usado pelo crawl.py (rede direta) e pelo from_browser.py (resultados vindos do navegador).
Formato de cada resultado: {"url", "status", "chain": [urls intermediarias], "final_url", "noindex", "error"}
"""
from __future__ import annotations

import gzip
import re
import ssl
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
NOINDEX_RE = re.compile(r"<meta[^>]+name=[\"']robots[\"'][^>]+content=[\"'][^\"']*noindex", re.I)
CTX = ssl.create_default_context()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect, urllib.request.HTTPSHandler(context=CTX))


def check_url(url: str, max_hops: int = 5, read_body: bool = False, timeout: int = 15) -> dict:
    chain, cur = [], url
    for _ in range(max_hops + 1):
        req = urllib.request.Request(cur, headers={"User-Agent": UA, "Accept-Encoding": "gzip",
                                                   "Accept": "text/html,*/*;q=0.8"})
        try:
            r = _OPENER.open(req, timeout=timeout)
            status, headers = r.status, r.headers
            body = r.read(300_000 if read_body else 2_000)
        except urllib.error.HTTPError as e:
            status, headers = e.code, e.headers
            body = b""
            if status in (301, 302, 303, 307, 308) and headers.get("Location"):
                chain.append(cur)
                cur = urljoin(cur, headers["Location"])
                continue
        except Exception as e:  # DNS, TLS, timeout
            return {"url": url, "status": None, "chain": chain, "final_url": cur, "noindex": False, "error": repr(e)[:160]}
        if status in (301, 302, 303, 307, 308) and headers.get("Location"):
            chain.append(cur)
            cur = urljoin(cur, headers["Location"])
            continue
        noindex = False
        if read_body:
            if headers.get("Content-Encoding") == "gzip":
                try:
                    body = gzip.decompress(body)
                except Exception:
                    body = b""
            text = body.decode("utf-8", "replace")
            noindex = bool(NOINDEX_RE.search(text)) or "noindex" in (headers.get("X-Robots-Tag") or "").lower()
        return {"url": url, "status": status, "chain": chain, "final_url": cur, "noindex": noindex, "error": None}
    return {"url": url, "status": None, "chain": chain, "final_url": cur, "noindex": False, "error": "too_many_redirects"}


def even_sample(items: list, n: int) -> list:
    if len(items) <= n:
        return list(items)
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def summarize(link_results: list[dict], sources: dict[str, list[str]], sitemap_results: list[dict], host: str,
              https_site: bool = True) -> dict:
    def src(u):
        return sources.get(u, [])[:3]

    broken = [{"url": r["url"], "status": r["status"], "error": r.get("error"), "sources": src(r["url"])}
              for r in link_results if r["status"] is None or r["status"] >= 400]
    redirected = [{"url": r["url"], "final_url": r["final_url"], "hops": len(r["chain"]), "status": r["status"],
                   "sources": src(r["url"])} for r in link_results if r["chain"] and r["status"] and r["status"] < 400]
    http_links = sorted({u for u in sources if https_site and u.startswith("http://")
                         and urlparse(u).netloc.removeprefix("www.") == host})
    sm_bad = [{"url": r["url"], "status": r["status"]} for r in sitemap_results if r["status"] is None or r["status"] >= 400]
    sm_redirect = [{"url": r["url"], "final_url": r["final_url"]} for r in sitemap_results if r["chain"] and r["status"] and r["status"] < 400]
    sm_noindex = [r["url"] for r in sitemap_results if r.get("noindex")]
    return {
        "links": {"checked": len(link_results), "broken": broken[:50], "redirected": redirected[:50],
                  "chains_2plus": [r for r in redirected if r["hops"] >= 2][:20], "http_internal_links": http_links[:20]},
        "sitemap_health": {"sampled": len(sitemap_results), "non_200": sm_bad[:30], "redirects": sm_redirect[:30],
                           "noindex": sm_noindex[:30]},
    }


def run(pages_links: dict[str, list[str]], sitemap_urls: list[str], host: str, mode: str = "quick",
        extra_targets: list[str] | None = None, workers: int = 8, https_site: bool = True) -> dict:
    """pages_links: {pagina_origem: [links internos]}."""
    sources: dict[str, list[str]] = {}
    for page, links in pages_links.items():
        for u in links:
            sources.setdefault(u, []).append(page)
    for u in extra_targets or []:
        sources.setdefault(u, []).append("(hreflang/canonical)")
    targets = sorted(sources, key=lambda u: -len(sources[u]))  # mais linkados primeiro
    targets = targets[: (80 if mode == "quick" else 250)]
    sm_sample = even_sample(sitemap_urls, 25 if mode == "quick" else 80)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        link_results = list(ex.map(check_url, targets))
        sm_results = list(ex.map(lambda u: check_url(u, read_body=True), sm_sample))
    return summarize(link_results, sources, sm_results, host, https_site)
