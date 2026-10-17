#!/usr/bin/env python3
"""Coleta de dados do site para a auditoria SEO/GEO/AEO.

Uso:
  python3 crawl.py https://exemplo.com.br --mode quick --out audit_data
  python3 crawl.py https://exemplo.com.br --mode full --max-pages 60 --out audit_data

Saidas em --out:
  site.json          sinais do site (robots, bots de IA, sitemap, llms.txt, paginas)
  pages/NN-slug.txt  texto principal de cada pagina (para analise qualitativa)

Codigo de saida 3 = rede bloqueada para o dominio (use o modo navegador, ver SKILL.md).
Somente biblioteca padrao + beautifulsoup4.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extract import extract  # noqa: E402
import linkcheck  # noqa: E402

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

# Agentes de IA relevantes e sua funcao. Mantenha alinhado com references/ai-crawlers.md
AI_AGENTS = {
    "GPTBot": "treino (OpenAI)",
    "OAI-SearchBot": "busca (ChatGPT Search)",
    "ChatGPT-User": "acesso disparado pelo usuário (ChatGPT)",
    "ClaudeBot": "treino (Anthropic)",
    "Claude-SearchBot": "busca (Claude)",
    "Claude-User": "acesso disparado pelo usuário (Claude)",
    "PerplexityBot": "busca/indice (Perplexity)",
    "Perplexity-User": "acesso disparado pelo usuário (Perplexity)",
    "Google-Extended": "token de controle: treino/grounding Gemini (NÃO afeta Busca nem AI Overviews)",
    "Googlebot": "Busca Google, inclui AI Overviews e AI Mode",
    "Bingbot": "Bing, base do Copilot",
    "Applebot": "busca Apple (Siri, Spotlight, Safari)",
    "Applebot-Extended": "token de controle: treino Apple Intelligence",
    "Amzn-SearchBot": "busca Amazon/Alexa (sem treino)",
    "Amazonbot": "Amazon (pode treinar modelos)",
    "meta-webindexer": "citações no Meta AI",
    "Meta-ExternalAgent": "treino e indexação (Meta)",
    "CCBot": "Common Crawl (dataset usado em treino)",
    "Bytespider": "treino (ByteDance; costuma ignorar robots.txt)",
    "DuckAssistBot": "respostas de IA do DuckDuckGo",
    "MistralAI-User": "acesso disparado pelo usuário (Mistral)",
}
UA_PROBES = {
    "GPTBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; GPTBot/1.2; +https://openai.com/gptbot",
    "OAI-SearchBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko); compatible; OAI-SearchBot/1.0; +https://openai.com/searchbot",
    "ClaudeBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; ClaudeBot/1.0; +claudebot@anthropic.com)",
    "PerplexityBot": "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; PerplexityBot/1.0; +https://perplexity.ai/perplexitybot)",
}

_SEG = r"(?:^|/)(?:{})(?:/|$)"  # casa so o segmento inteiro
PAGE_PATTERNS = [  # (tipo, regex no path) em ordem de prioridade
    ("comparison", r"(?:-vs-|/vs/|(?:^|/)(?:alternativas?|alternatives?|comparativo|comparacao|versus|compare)(?:/|$|-))"),
    ("about", _SEG.format("sobre|sobre-nos|quem-somos|about|about-us|empresa|nossa-historia|institucional|team|equipe|nosso-time|nossa-equipe")),
    ("pricing", _SEG.format("precos|preco|planos|pricing|plans|planos-e-precos")),
    ("product", _SEG.format("produto|produtos|product|products|solucoes|solucao|solutions|features|funcionalidades|recursos-do-produto|plataforma|platform")),
    ("service", _SEG.format("servicos|servico|services|o-que-fazemos")),
    ("case", _SEG.format("cases|case|casos|casos-de-sucesso|cases-de-sucesso|historias-de-sucesso|clientes|customers|portfolio|trabalhos|depoimentos|customer-stories|success-stories")),
    ("faq", _SEG.format("faq|perguntas-frequentes|perguntas|duvidas|ajuda|help|suporte|central-de-ajuda")),
    ("contact", _SEG.format("contato|fale-conosco|contact|contact-us")),
    ("blog_index", r"(?:^|/)(?:blog|artigos|conteudos|insights|resources|recursos|materiais|noticias|news)/?$"),
    ("blog_post", r"(?:^|/)(?:blog|artigos|conteudos|insights|resources|noticias|news|guias?)/.+"),
    ("integration", _SEG.format("integracoes|integrations|parceiros|partners")),
]
SKIP_RE = re.compile(r"/(privacidade|privacy|termos|terms|cookies|login|entrar|signin|sign-in|cadastro|"
                     r"signup|register|account|minha-conta|carrinho|cart|checkout|obrigado|thank|wp-admin|"
                     r"wp-login|feed|tag/|author/|autor/|page/\d+|\?|\.(pdf|jpg|jpeg|png|gif|webp|svg|zip|xml|mp4))", re.I)

CTX = ssl.create_default_context()


class NetworkBlocked(Exception):
    pass


def fetch(url: str, ua: str = BROWSER_UA, timeout: int = 20, max_bytes: int = 4_000_000, method: str = "GET"):
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": ua, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8", "Accept-Encoding": "gzip"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            body = r.read(max_bytes)
            if r.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return {"url": url, "final_url": r.geturl(), "status": r.status, "headers": dict(r.headers),
                    "body": body.decode(r.headers.get_content_charset() or "utf-8", "replace"),
                    "ms": int((time.time() - t0) * 1000)}
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read(200_000).decode("utf-8", "replace")
        except Exception:
            pass
        return {"url": url, "final_url": e.geturl() if hasattr(e, "geturl") else url, "status": e.code,
                "headers": dict(e.headers or {}), "body": body, "ms": int((time.time() - t0) * 1000)}
    except Exception as e:  # DNS, proxy, TLS, timeout
        return {"url": url, "final_url": url, "status": None, "headers": {}, "body": "", "error": repr(e)[:300],
                "ms": int((time.time() - t0) * 1000)}


def classify(url: str) -> str:
    path = urlparse(url).path.lower() or "/"
    if path in ("", "/"):
        return "home"
    for kind, rx in PAGE_PATTERNS:
        if re.search(rx, path):
            return kind
    return "other"


def parse_sitemaps(urls: list[str], limit: int = 5000, max_children: int = 8):
    seen, found, lastmods, sources = set(), [], [], []
    queue = list(dict.fromkeys(urls))
    children = 0
    while queue and len(found) < limit:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        r = fetch(sm, timeout=20, max_bytes=15_000_000)
        if r["status"] != 200 or "<" not in r["body"][:500]:
            continue
        sources.append(sm)
        try:
            root = ET.fromstring(r["body"].encode("utf-8", "replace"))
        except ET.ParseError:
            continue
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        if root.tag.endswith("sitemapindex"):
            for loc in root.findall(".//s:sitemap/s:loc", ns):
                if children < max_children and loc.text:
                    queue.append(loc.text.strip())
                    children += 1
        else:
            for u in root.findall(".//s:url", ns):
                loc = u.find("s:loc", ns)
                lm = u.find("s:lastmod", ns)
                if loc is not None and loc.text:
                    found.append(loc.text.strip())
                    if lm is not None and lm.text:
                        lastmods.append(lm.text.strip()[:10])
    return found, lastmods, sources


def robots_analysis(base: str, robots_txt: str | None):
    res = {"present": robots_txt is not None, "sitemaps": [], "agents": {}, "raw_excerpt": None}
    if robots_txt is None:
        return res
    res["raw_excerpt"] = robots_txt[:3000]
    res["sitemaps"] = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", robots_txt)
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(robots_txt.splitlines())
    named = {m.lower() for m in re.findall(r"(?im)^\s*user-agent:\s*(\S+)", robots_txt)}
    for agent, role in AI_AGENTS.items():
        res["agents"][agent] = {
            "role": role,
            "home_allowed": rp.can_fetch(agent, urljoin(base, "/")),
            "blog_allowed": rp.can_fetch(agent, urljoin(base, "/blog/")),
            "explicit_rule": agent.lower() in named,
        }
    res["wildcard_disallow_all"] = bool(re.search(r"(?ims)user-agent:\s*\*\s*(?:\n(?!user-agent).*)*?\n\s*disallow:\s*/\s*$", robots_txt))
    res["content_signals"] = re.findall(r"(?im)^\s*content-signal:\s*(.+)$", robots_txt)
    return res


def select_pages(home_sig: dict, sm_urls: list[str], home_url: str, mode: str, max_pages: int):
    """Escolhe paginas por tipo (prioridade de negocio). Retorna (urls, inventario por tipo)."""
    bare = urlparse(home_url).netloc.lower().removeprefix("www.")
    candidates = list(dict.fromkeys(home_sig["nav_links"] + home_sig["internal_links"] +
                                    [u for u in sm_urls if urlparse(u).netloc.lower().removeprefix("www.") == bare]))
    candidates = [u for u in candidates if not SKIP_RE.search(u) and u.rstrip("/") != home_url.rstrip("/")]
    buckets: dict[str, list[str]] = {}
    for u in candidates:
        buckets.setdefault(classify(u), []).append(u)
    order = ["about", "pricing", "product", "service", "case", "faq", "contact", "blog_index",
             "comparison", "blog_post", "integration", "other"]
    per_type_quick = {"blog_post": 3, "product": 2, "service": 2, "case": 1, "comparison": 1}
    selected = []
    if mode == "quick":
        for k in order:
            selected += buckets.get(k, [])[: per_type_quick.get(k, 1)]
    else:
        rr = {k: list(v) for k, v in buckets.items()}
        while any(rr.values()) and len(selected) < max_pages * 2:
            for k in order:
                if rr.get(k):
                    selected.append(rr[k].pop(0))
    selected = list(dict.fromkeys(selected))
    if len(selected) < max_pages - 1:  # completa com links do menu (ordem de candidatos ja prioriza nav)
        for u in candidates:
            if u not in selected:
                selected.append(u)
            if len(selected) >= max_pages - 1:
                break
    return selected[: max_pages - 1], buckets


def finalize_page(sig: dict, idx: int, out_dir: str, ms: int | None = None) -> dict:
    sig["type"] = classify(sig["url"])
    sig["response_ms"] = ms
    sig["likely_client_rendered"] = sig["word_count"] < 80 and sig["script_tags"] >= 8
    slug = re.sub(r"[^a-z0-9]+", "-", urlparse(sig["url"]).path.lower()).strip("-") or "home"
    fname = f"{idx:02d}-{slug[:60]}.txt"
    with open(os.path.join(out_dir, "pages", fname), "w", encoding="utf-8") as f:
        f.write(f"URL: {sig['url']}\nTITLE: {sig.get('title')}\n\n{sig.pop('main_text_excerpt', '')}")
    sig["text_file"] = f"pages/{fname}"
    sig["_all_internal_links"] = sig.get("internal_links", [])
    sig["internal_links"] = sig.get("internal_links", [])[:60]
    return sig


def sitemap_stats(sm_urls, lastmods, sources):
    now = datetime.now(timezone.utc).date()
    recent = sum(1 for d in lastmods if re.match(r"\d{4}-\d{2}-\d{2}$", d) and
                 (now - datetime.strptime(d, "%Y-%m-%d").date()).days <= 365)
    return {"sources": sources, "url_count": len(sm_urls), "with_lastmod": len(lastmods),
            "modified_last_12m": recent, "sample": sm_urls[:20]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--mode", choices=["quick", "full"], default="quick")
    ap.add_argument("--max-pages", type=int, default=None)
    ap.add_argument("--out", default="audit_data")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    start = a.url if a.url.startswith("http") else "https://" + a.url
    max_pages = a.max_pages or (10 if a.mode == "quick" else 60)
    os.makedirs(os.path.join(a.out, "pages"), exist_ok=True)

    home = fetch(start)
    if home["status"] is None:
        print(json.dumps({"error": "network_blocked_or_unreachable", "detail": home.get("error"),
                          "next": "Use a coleta pelo navegador (SKILL.md, Etapa 1-B)."}, ensure_ascii=False))
        sys.exit(3)
    if home["status"] >= 400 or len(home["body"]) < 500:
        print(json.dumps({"error": "home_error_or_blocked", "status": home["status"], "bytes": len(home["body"]),
                          "body_excerpt": home["body"][:200],
                          "next": "A home respondeu erro ou quase vazia (firewall, proxy do ambiente ou bloqueio de bots). "
                                  "Use a coleta pelo navegador (Etapa 1-B) e registre o achado: se for o site bloqueando "
                                  "requisicoes automatizadas, isso tambem afeta crawlers de IA."}, ensure_ascii=False))
        sys.exit(4)
    base = f"{urlparse(home['final_url']).scheme}://{urlparse(home['final_url']).netloc}/"
    host = urlparse(base).netloc

    # ---- verificacoes de site em paralelo --------------------------------------
    bare = host.removeprefix("www.")
    alt_host = bare if host.startswith("www.") else "www." + bare
    jobs = {
        "robots": (urljoin(base, "/robots.txt"), BROWSER_UA),
        "llms": (urljoin(base, "/llms.txt"), BROWSER_UA),
        "llms_full": (urljoin(base, "/llms-full.txt"), BROWSER_UA),
        "http_variant": (f"http://{host}/", BROWSER_UA),
        "alt_host": (f"https://{alt_host}/", BROWSER_UA),
        "soft404": (urljoin(base, f"/pagina-inexistente-{uuid.uuid4().hex[:8]}"), BROWSER_UA),
        "bing_auth": (urljoin(base, "/BingSiteAuth.xml"), BROWSER_UA),
    }
    for name, ua in UA_PROBES.items():
        jobs[f"ua_{name}"] = (base, ua)
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs = {k: ex.submit(fetch, u, ua) for k, (u, ua) in jobs.items()}
        site = {k: f.result() for k, f in futs.items()}

    robots_txt = site["robots"]["body"] if site["robots"]["status"] == 200 and "<html" not in site["robots"]["body"][:500].lower() else None
    robots = robots_analysis(base, robots_txt)

    def llms_info(r):
        ok = r["status"] == 200 and "<html" not in r["body"][:300].lower() and len(r["body"].strip()) > 20
        return {"present": ok, "bytes": len(r["body"]) if ok else 0, "excerpt": r["body"][:800] if ok else None}

    home_len = len(home["body"])
    ua_probe = {}
    for name in UA_PROBES:
        r = site[f"ua_{name}"]
        hdrs = {k.lower(): v for k, v in r["headers"].items()}
        ua_probe[name] = {"status": r["status"], "bytes": len(r["body"]),
                          "pay_per_crawl": r["status"] == 402 or "crawler-price" in hdrs or "crawler-charged" in hdrs,
                          "looks_blocked": (r["status"] in (401, 402, 403, 406, 429, 503)) or
                          (r["status"] == 200 and home_len > 0 and len(r["body"]) < 0.3 * home_len) or
                          ("cf-chl" in r["body"][:5000] or "challenge-platform" in r["body"][:5000])}

    # ---- sitemap ------------------------------------------------------------
    sm_candidates = robots["sitemaps"] or [urljoin(base, "/sitemap.xml"), urljoin(base, "/sitemap_index.xml")]
    sm_urls, lastmods, sm_sources = parse_sitemaps(sm_candidates)

    # ---- selecao de paginas -----------------------------------------------------
    home_sig = extract(home["body"], home["final_url"], home["status"], home["headers"])
    selected, buckets = select_pages(home_sig, sm_urls, home["final_url"], a.mode, max_pages)

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        results = list(ex.map(fetch, selected))

    pages = []
    seen_final = set()
    for i, r in enumerate([home] + results):
        fin = (r.get("final_url") or r["url"]).rstrip("/")
        if fin in seen_final:
            continue  # duas URLs que redirecionam para a mesma pagina
        seen_final.add(fin)
        if r["status"] is None:
            pages.append({"url": r["url"], "status": None, "error": r.get("error"), "type": classify(r["url"])})
            continue
        sig = home_sig if i == 0 else extract(r["body"], r["final_url"], r["status"], r["headers"])
        sig["requested_url"] = r["url"]
        sig["html_bytes"] = len(r["body"])
        pages.append(finalize_page(sig, i, a.out, r["ms"]))

    data = {
        "audited_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "start_url": start, "base": base, "host": host, "mode": a.mode, "collector": "python",
        "https": base.startswith("https://"),
        "http_redirects_to_https": (site["http_variant"].get("final_url") or "").startswith("https://"),
        "alt_host": {"url": f"https://{alt_host}/", "status": site["alt_host"]["status"],
                     "final_url": site["alt_host"]["final_url"],
                     "consolidated": urlparse(site["alt_host"]["final_url"] or "").netloc == host},
        "soft_404": {"status": site["soft404"]["status"], "is_soft_404": site["soft404"]["status"] == 200},
        "robots": robots,
        "ai_user_agent_probe": ua_probe,
        "llms_txt": llms_info(site["llms"]),
        "llms_full_txt": llms_info(site["llms_full"]),
        "sitemap": sitemap_stats(sm_urls, lastmods, sm_sources),
        "url_inventory_by_type": {k: len(v) for k, v in buckets.items()},
        "home_headers": {k: v for k, v in home["headers"].items() if k.lower() in
                         ("server", "cf-ray", "x-vercel-id", "x-powered-by", "strict-transport-security",
                          "content-security-policy", "x-robots-tag", "cache-control")},
        "pages": pages,
        "bing_site_auth_xml": site["bing_auth"]["status"] == 200 and "<user>" in site["bing_auth"]["body"].lower(),
    }
    # ---- links internos, redirecionamentos e saude do sitemap ------------------------
    pages_links, extra = {}, []
    for p in pages:
        links = p.pop("_all_internal_links", [])
        if p.get("status") == 200:
            pages_links[p["url"]] = links
            extra += [urljoin(p["url"], h["href"]) for h in p.get("hreflang", []) if h.get("href")]
            if p.get("canonical"):
                extra.append(p["canonical"])
    same_host = [u for u in sm_urls if urlparse(u).netloc.removeprefix("www.") == bare]
    data.update(linkcheck.run(pages_links, same_host, bare, a.mode, extra_targets=extra, workers=a.workers,
                              https_site=base.startswith("https://")))
    with open(os.path.join(a.out, "site.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)

    ok = [p for p in pages if p.get("status") == 200]
    print(json.dumps({"ok": True, "host": host, "pages_fetched": len(ok), "pages_failed": len(pages) - len(ok),
                      "sitemap_urls": len(sm_urls), "robots": robots["present"],
                      "llms_txt": data["llms_txt"]["present"],
                      "broken_internal_links": len(data["links"]["broken"]),
                      "redirected_internal_links": len(data["links"]["redirected"]),
                      "sitemap_sample_problems": len(data["sitemap_health"]["non_200"]) + len(data["sitemap_health"]["noindex"]),
                      "ai_bots_blocked_robots": [k for k, v in robots["agents"].items() if not v["home_allowed"]],
                      "ai_bots_blocked_waf": [k for k, v in ua_probe.items() if v["looks_blocked"]],
                      "out": os.path.abspath(a.out)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
