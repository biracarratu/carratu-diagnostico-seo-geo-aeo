#!/usr/bin/env python3
"""Monta site.json a partir das saidas do browser_collect.js (quando a rede do sandbox esta bloqueada).

Fluxo:
  1. JS com CONFIG {discover: true}      -> salvar em audit_data/browser/discover.json
  2. python3 from_browser.py audit_data --select --mode quick
       -> imprime lotes de ate 8 URLs para a fase 2
  3. JS com CONFIG {urls: [...lote...]}  -> salvar em audit_data/browser/batch-1.json, batch-2.json...
  4. python3 from_browser.py audit_data --links-plan --mode quick
       -> lotes de links (fase 3 do JS, readBody false) e amostra do sitemap (readBody true)
       salvar em audit_data/browser/links-1.json... e sitemap-1.json...  (opcional, recomendado)
  5. python3 from_browser.py audit_data --build --mode quick
       -> grava audit_data/site.json e audit_data/pages/*.txt (mesmo formato do crawl.py)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crawl import finalize_page, robots_analysis, select_pages, sitemap_stats  # noqa: E402
import linkcheck  # noqa: E402


def load_json(path):
    raw = open(path, encoding="utf-8").read().strip()
    data = json.loads(raw)
    return json.loads(data) if isinstance(data, str) else data  # aceita JSON com aspas extras


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--mode", choices=["quick", "full"], default="quick")
    ap.add_argument("--max-pages", type=int, default=None)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--select", action="store_true")
    g.add_argument("--links-plan", action="store_true")
    g.add_argument("--build", action="store_true")
    a = ap.parse_args()
    max_pages = a.max_pages or (10 if a.mode == "quick" else 60)

    disc = load_json(os.path.join(a.out_dir, "browser", "discover.json"))
    home = disc["home"]
    sm_urls = disc["sitemap"]["urls"]
    selected, buckets = select_pages(home, sm_urls, home["url"], a.mode, max_pages)

    if a.select:
        batches = [selected[i:i + 8] for i in range(0, len(selected), 8)]
        print(json.dumps({"batches": batches, "inventory": {k: len(v) for k, v in buckets.items()}},
                         ensure_ascii=False, indent=1))
        return

    batch_pages = []
    for path in sorted(glob.glob(os.path.join(a.out_dir, "browser", "batch-*.json"))):
        batch_pages += load_json(path).get("pages", [])
    bare = urlparse(disc["base"]).netloc.lower().removeprefix("www.")
    pages_links = {p["url"]: p.get("internal_links", []) for p in [home] + batch_pages if p.get("status") == 200}
    sm_same = [u for u in sm_urls if urlparse(u).netloc.lower().removeprefix("www.") == bare]

    def link_sources():
        src = {}
        for pg, links in pages_links.items():
            for u in links:
                src.setdefault(u, []).append(pg)
        for p in [home] + batch_pages:
            if p.get("status") != 200:
                continue
            for u in [urljoin(p["url"], h["href"]) for h in p.get("hreflang", []) if h.get("href")] + \
                     ([p["canonical"]] if p.get("canonical") else []):
                src.setdefault(u, []).append("(hreflang/canonical)")
        return src

    if a.links_plan:
        sources = link_sources()
        targets = sorted(sources, key=lambda u: -len(sources[u]))[: (80 if a.mode == "quick" else 250)]
        sm_sample = linkcheck.even_sample(sm_same, 25 if a.mode == "quick" else 80)
        print(json.dumps({"link_batches": [targets[i:i + 40] for i in range(0, len(targets), 40)],
                          "sitemap_batches": [sm_sample[i:i + 40] for i in range(0, len(sm_sample), 40)]},
                         ensure_ascii=False, indent=1))
        return

    os.makedirs(os.path.join(a.out_dir, "pages"), exist_ok=True)
    pages = [finalize_page(dict(home), 0, a.out_dir)]
    seen = {home["url"]}
    for p in batch_pages:
        if True:
            if p.get("url") in seen:
                continue
            seen.add(p.get("url"))
            if p.get("status") is None:
                pages.append({"url": p["url"], "status": None, "error": p.get("error"), "type": "other"})
            else:
                pages.append(finalize_page(p, len(pages), a.out_dir))

    base = disc["base"]
    host = urlparse(base).netloc
    data = {
        "audited_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "start_url": home["url"], "base": base, "host": host, "mode": a.mode, "collector": "browser",
        "https": disc["https"],
        "http_redirects_to_https": disc["https"],  # navegador nao permite testar; assumido, verificar manualmente
        "alt_host": {"url": None, "status": None, "final_url": None, "consolidated": None},
        "soft_404": {"status": disc["soft_404_status"], "is_soft_404": disc["soft_404_status"] == 200},
        "robots": robots_analysis(base, disc.get("robots_txt")),
        "ai_user_agent_probe": {},
        "llms_txt": disc["llms_txt"], "llms_full_txt": disc["llms_full_txt"],
        "sitemap": sitemap_stats(sm_urls, disc["sitemap"]["lastmods"], disc["sitemap"]["sources"]),
        "url_inventory_by_type": {k: len(v) for k, v in buckets.items()},
        "home_headers": home.get("server_hints", {}),
        "pages": pages,
        "bing_site_auth_xml": bool(disc.get("bing_site_auth_xml")),
    }
    for p in pages:
        p.pop("_all_internal_links", None)
    link_res, sm_res, unverified = [], [], 0
    for kind, acc in (("links", link_res), ("sitemap", sm_res)):
        for path in sorted(glob.glob(os.path.join(a.out_dir, "browser", f"{kind}-*.json"))):
            for r in load_json(path).get("results", []):
                if r.get("status") is None:  # erro de CORS/rede no navegador: nao da para afirmar que quebrou
                    unverified += 1
                    continue
                acc.append(r)
    if link_res or sm_res:
        sources = link_sources()
        data.update(linkcheck.summarize(link_res, sources, sm_res, bare, https_site=bool(disc["https"])))
        data["links"]["unverified"] = unverified
    json.dump(data, open(os.path.join(a.out_dir, "site.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"ok": True, "pages": len(pages), "site_json": os.path.join(a.out_dir, "site.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
