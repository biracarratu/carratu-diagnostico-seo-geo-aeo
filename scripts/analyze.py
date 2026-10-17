#!/usr/bin/env python3
"""Aplica os checks automaticos da rubrica sobre site.json e gera findings.json.

Uso:
  python3 analyze.py audit_data/site.json --rubric ../references/rubric.json --out audit_data/findings.json

Checks 'manual' e 'data' ficam com status 'unknown' para o Claude preencher.
Depois rode score.py para calcular as notas.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urljoin

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_RUBRIC = os.path.join(HERE, "..", "references", "rubric.json")

SEARCH_BOTS = ["OAI-SearchBot", "Claude-SearchBot", "PerplexityBot", "Bingbot", "Googlebot", "ChatGPT-User",
               "Claude-User", "Applebot", "Amzn-SearchBot", "meta-webindexer"]
CRITICAL_SEARCH = ("OAI-SearchBot", "Googlebot", "Bingbot", "Claude-SearchBot", "PerplexityBot")
TRAINING_BOTS = ["GPTBot", "ClaudeBot", "Google-Extended", "CCBot", "Applebot-Extended", "Meta-ExternalAgent",
                 "Bytespider", "Amazonbot"]
CONTENT_TYPES = {"blog_post", "product", "service", "case", "comparison", "about", "pricing", "home", "faq"}
MIN_WORDS = {"blog_post": 700, "product": 300, "service": 300, "case": 300, "comparison": 600,
             "about": 200, "pricing": 150, "home": 250, "faq": 250}
RICH_SUPPORTED = {"Organization", "BreadcrumbList", "Article", "BlogPosting", "NewsArticle", "Product",
                  "SoftwareApplication", "Review", "AggregateRating", "Event", "JobPosting", "LocalBusiness",
                  "Recipe", "VideoObject", "Course", "Offer", "WebSite", "Person", "ProfilePage",
                  "DiscussionForumPosting", "QAPage", "Dataset", "Book", "Movie", "Organization"}
DEPRECATED = {"HowTo": "rich result removido em set/2023",
              "FAQPage": "rich result encerrado para todos os sites em mai/2026",
              "SpecialAnnouncement": "removido em 2025", "ClaimReview": "removido em 2025",
              "Course": "Course Info removido em 2025 (Course list segue)", "Vehicle": "Vehicle Listing removido em 2025",
              "SpeakableSpecification": "beta, restrito a noticias"}


def ok_pages(site):
    return [p for p in site["pages"] if p.get("status") == 200]


def pct(n, d):
    return round(100 * n / d) if d else 0


def status_from_ratio(r, good=0.9, mid=0.6):
    return "pass" if r >= good else "warn" if r >= mid else "fail"


def run_checks(site: dict) -> dict[str, dict]:
    P = ok_pages(site)
    n = len(P) or 1
    out: dict[str, dict] = {}

    def put(cid, status, evidence, pages=None, data=None):
        out[cid] = {"status": status, "evidence": evidence, "pages": pages or [], "data": data or {}}

    # ---------------- SEO -----------------------------------------------------
    noindex = [p["url"] for p in P if "noindex" in ((p.get("meta_robots") or "") + (p.get("x_robots_tag") or "")).lower()]
    put("seo.indexable", "pass" if not noindex else ("fail" if any(p["type"] in ("home", "product", "service", "pricing") for p in P if p["url"] in noindex) else "warn"),
        f"{len(noindex)} de {len(P)} páginas com noindex." if noindex else f"Nenhuma das {len(P)} páginas auditadas tem noindex.", noindex)

    rb = site["robots"]
    if not rb["present"]:
        put("seo.googlebot_allowed", "pass", "Sem robots.txt: tudo liberado por padrão (recomenda-se publicar um com a linha Sitemap).")
    else:
        blocked = [a for a in ("Googlebot", "Bingbot") if not rb["agents"][a]["home_allowed"]]
        blog_blocked = [a for a in ("Googlebot", "Bingbot") if not rb["agents"][a]["blog_allowed"]]
        put("seo.googlebot_allowed", "fail" if blocked else "warn" if blog_blocked else "pass",
            f"Bloqueados na home: {blocked or 'nenhum'}; no /blog/: {blog_blocked or 'nenhum'}.")

    https_ok = site["https"] and site["http_redirects_to_https"]
    if site.get("collector") == "browser":
        put("seo.https", "pass" if site["https"] else "fail",
            f"HTTPS: {'sim' if site['https'] else 'não'}. Redirecionamento HTTP->HTTPS não testável pelo navegador.")
    else:
        put("seo.https", "pass" if https_ok else "fail" if not site["https"] else "warn",
        f"HTTPS: {'sim' if site['https'] else 'não'}; HTTP redireciona para HTTPS: {'sim' if site['http_redirects_to_https'] else 'não'}; "
        f"HSTS: {'sim' if any(k.lower() == 'strict-transport-security' for k in site.get('home_headers', {})) else 'não'}.")

    ah = site["alt_host"]
    if ah.get("url") is None:
        put("seo.host_consolidated", "unknown", "Não testável pelo navegador; verificar manualmente se www e sem www redirecionam para a mesma versão.")
    elif ah["status"] is None:
        put("seo.host_consolidated", "na", f"Variante {ah['url']} não responde (sem DNS), nada a consolidar.")
    else:
        put("seo.host_consolidated", "pass" if ah["consolidated"] else "warn",
            f"{ah['url']} -> {ah['final_url']} (status {ah['status']}).")

    s4 = site["soft_404"]
    put("seo.soft404", "fail" if s4["is_soft_404"] else "pass" if s4["status"] in (404, 410) else "warn",
        f"URL inexistente retornou status {s4['status']}.")

    sm = site["sitemap"]
    in_robots = bool(rb.get("sitemaps"))
    if not sm["url_count"]:
        put("seo.sitemap", "fail", "Nenhum sitemap XML encontrado (robots.txt, /sitemap.xml, /sitemap_index.xml).")
    else:
        lm = pct(sm["with_lastmod"], sm["url_count"])
        st = "pass" if in_robots and lm >= 80 else "warn"
        put("seo.sitemap", st, f"{sm['url_count']} URLs em {len(sm['sources'])} sitemap(s); {lm}% com lastmod; "
            f"declarado no robots.txt: {'sim' if in_robots else 'não'}.", data={"sources": sm["sources"]})

    # Ambos os coletores leem o HTML do servidor (sem executar JS), como os crawlers de IA.
    csr = [p["url"] for p in P if p.get("likely_client_rendered")]
    gap = [p["url"] for p in P if p.get("rendered_word_count") and p["rendered_word_count"] > 150
           and p.get("raw_word_count", p["word_count"]) < 0.5 * p["rendered_word_count"]]
    bad = sorted(set(csr + gap))
    put("seo.server_rendered", "pass" if not bad else "fail" if len(bad) >= n / 2 or any(p["type"] == "home" and p["url"] in bad for p in P) else "warn",
        (f"{len(bad)} página(s) com pouco ou nenhum texto no HTML do servidor (conteúdo depende de JavaScript, invisível para GPTBot/ClaudeBot/PerplexityBot)."
         if bad else "Conteúdo principal presente no HTML do servidor em todas as páginas auditadas."), bad)

    titles = [(p["url"], p.get("title") or "") for p in P]
    missing = [u for u, t in titles if not t]
    dup = [t for t, c in Counter(t for _, t in titles if t).items() if c > 1]
    bad_len = [(u, len(t)) for u, t in titles if t and not (25 <= len(t) <= 65)]
    issues = len(missing) * 2 + len(dup) * 2 + len(bad_len)
    put("seo.title", "pass" if issues == 0 else "warn" if issues <= max(2, n // 3) and not missing else "fail",
        f"Ausentes: {len(missing)}; duplicados: {len(dup)}; fora de 25-65 caracteres: {len(bad_len)}.",
        missing + [u for u, _ in bad_len][:10], {"duplicates": dup[:5], "length_issues": bad_len[:10]})

    descs = [(p["url"], p.get("meta_description") or "") for p in P]
    dmiss = [u for u, d in descs if not d]
    ddup = [d for d, c in Counter(d for _, d in descs if d).items() if c > 1]
    dlen = [(u, len(d)) for u, d in descs if d and not (70 <= len(d) <= 170)]
    put("seo.meta_description", status_from_ratio(1 - (len(dmiss) + len(ddup)) / n, 0.9, 0.6) if not dlen or len(dlen) < n / 2 else "warn",
        f"Ausentes: {len(dmiss)}; duplicadas: {len(ddup)}; fora de 70-170 caracteres: {len(dlen)}.", dmiss + [u for u, _ in dlen][:10])

    h1bad = [(p["url"], len(p.get("h1") or [])) for p in P if len(p.get("h1") or []) != 1]
    put("seo.h1", status_from_ratio(1 - len(h1bad) / n), f"{len(h1bad)} página(s) sem H1 ou com mais de um.",
        [u for u, _ in h1bad], {"detail": h1bad[:10]})

    skips = []
    for p in P:
        lv = [h["level"] for h in p.get("headings", [])]
        if any(b - a > 1 for a, b in zip(lv, lv[1:])):
            skips.append(p["url"])
    put("seo.heading_hierarchy", status_from_ratio(1 - len(skips) / n, 0.8, 0.5), f"{len(skips)} página(s) com saltos de nível (ex.: H2 para H4).", skips)

    can_missing = [p["url"] for p in P if not p.get("canonical")]
    can_other = [p["url"] for p in P if p.get("canonical") and p["canonical"].rstrip("/").split("?")[0] != p["url"].rstrip("/").split("?")[0]]
    put("seo.canonical", "pass" if not can_missing and len(can_other) <= 1 else "warn" if len(can_missing) < n / 2 else "fail",
        f"Sem canonical: {len(can_missing)}; canonical apontando para outra URL: {len(can_other)} (verificar se intencional).",
        can_missing + can_other)

    nolang = [p["url"] for p in P if not p.get("lang")]
    novp = [p["url"] for p in P if not p.get("viewport")]
    put("seo.lang_mobile", "pass" if not nolang and not novp else "warn" if len(nolang) + len(novp) < n else "fail",
        f"Sem lang: {len(nolang)}; sem viewport: {len(novp)}. Idiomas declarados: {sorted({p.get('lang') for p in P if p.get('lang')})}.")

    imgs = sum(p.get("images", 0) for p in P)
    noalt = sum(p.get("images_missing_alt", 0) for p in P)
    put("seo.image_alt", "na" if not imgs else status_from_ratio(1 - noalt / imgs, 0.9, 0.7),
        f"{noalt} de {imgs} imagens sem alt ({pct(noalt, imgs)}%).")

    avg_int = sum(p.get("internal_link_count", 0) for p in P) / n
    low = [p["url"] for p in P if p.get("internal_link_count", 0) < 5]
    empty = sum(p.get("empty_anchor_links", 0) for p in P)
    put("seo.internal_links", "pass" if avg_int >= 15 and len(low) <= 1 else "warn" if avg_int >= 6 else "fail",
        f"Média de {avg_int:.0f} links internos por página; {len(low)} página(s) com menos de 5; {empty} links sem texto.", low)

    noog = [p["url"] for p in P if not (p.get("og") or {}).get("title") or not (p.get("og") or {}).get("image")]
    put("seo.social_meta", status_from_ratio(1 - len(noog) / n), f"{len(noog)} página(s) sem og:title ou og:image.", noog)

    thin = [(p["url"], p["type"], p["word_count"]) for p in P if p.get("type") in MIN_WORDS and p["word_count"] < MIN_WORDS[p["type"]]]
    ctyp = [p for p in P if p.get("type") in MIN_WORDS]
    put("seo.content_depth", "na" if not ctyp else status_from_ratio(1 - len(thin) / len(ctyp), 0.8, 0.5),
        f"{len(thin)} de {len(ctyp)} páginas abaixo da profundidade mínima para o tipo.", [t[0] for t in thin], {"thin": thin[:15]})

    errs = sum(p.get("jsonld_parse_errors", 0) for p in P)
    with_schema = [p for p in P if p.get("jsonld_types") or p.get("microdata_types")]
    posts = [p for p in P if p["type"] == "blog_post"]
    posts_article = [p for p in posts if {"Article", "BlogPosting", "NewsArticle", "TechArticle"} & set(p.get("jsonld_types", []))]
    home = next((p for p in P if p["type"] == "home"), P[0] if P else {})
    org = bool({"Organization", "Corporation", "LocalBusiness", "ProfessionalService"} & set(home.get("jsonld_types", [])))
    score = (1 if not errs else 0) + (1 if org else 0) + (1 if not posts or len(posts_article) == len(posts) else 0.5 if posts_article else 0) + (1 if len(with_schema) >= n / 2 else 0)
    all_types = sorted({t for p in P for t in p.get("jsonld_types", [])})
    put("seo.structured_data", "pass" if score >= 3.5 else "warn" if score >= 2 else "fail",
        f"Tipos encontrados: {', '.join(all_types) or 'nenhum'}. Erros de JSON-LD: {errs}. Organization na home: {'sim' if org else 'não'}. "
        f"Artigos com Article/BlogPosting: {len(posts_article)}/{len(posts)}.", data={"types": all_types})

    # ---------------- GEO -----------------------------------------------------
    agents = rb.get("agents", {})
    if not rb["present"]:
        put("geo.ai_search_bots", "pass", "Sem robots.txt: bots de busca de IA liberados por padrão.")
    else:
        blocked = [b for b in SEARCH_BOTS if b in agents and not agents[b]["home_allowed"]]
        put("geo.ai_search_bots", "fail" if any(b in blocked for b in CRITICAL_SEARCH) else "warn" if blocked else "pass",
            f"Bots de busca/recuperação bloqueados no robots.txt: {', '.join(blocked) or 'nenhum'}.", data={"blocked": blocked})

    probe = site.get("ai_user_agent_probe") or {}
    if not probe:
        put("geo.waf_blocking", "unknown", "Teste de user-agent não executado (coleta via navegador).")
    else:
        wb = [k for k, v in probe.items() if v.get("looks_blocked")]
        ppc = [k for k, v in probe.items() if v.get("pay_per_crawl")]
        hh = {k.lower(): v for k, v in site.get("home_headers", {}).items()}
        cf = "cf-ray" in hh or "cloudflare" in str(hh.get("server", "")).lower()
        put("geo.waf_blocking", "fail" if any(b in wb for b in ("OAI-SearchBot", "PerplexityBot")) else "warn" if wb else "pass",
            f"Requisições com user-agent de bots de IA aparentemente bloqueadas: {', '.join(wb) or 'nenhuma'}"
            + (f"; cobrança por rastreio (HTTP 402/crawler-price) para: {', '.join(ppc)}" if ppc else "")
            + (". Site atrás do Cloudflare: revisar AI Crawl Control. Desde set/2026 o padrão de novos domínios bloqueia bots de treino/agente, "
               "e bloquear treino pode bloquear também Googlebot, Bingbot e Applebot." if cf else ".") + " "
            "Obs.: o teste imita o user-agent, mas não o IP do bot; confirmar nos logs do servidor/CDN.",
            data={"probe": probe, "cloudflare": cf})

    tb = [b for b in TRAINING_BOTS if b in agents and not agents[b]["home_allowed"]]
    put("geo.training_policy", "na", f"Bots de treino bloqueados: {', '.join(tb) or 'nenhum'}. Content-Signal no robots.txt: {rb.get('content_signals') or 'não'}.")

    dated = []
    now = datetime.now(timezone.utc).date()
    for p in posts or [p for p in P if p["type"] in ("blog_post", "case", "comparison")]:
        d = p.get("dates") or {}
        cand = d.get("dateModified") or d.get("modified") or d.get("datePublished") or d.get("published") or (d.get("time_tags") or [None])[0]
        if cand and re.match(r"\d{4}-\d{2}-\d{2}", cand):
            dated.append((p["url"], (now - datetime.strptime(cand[:10], "%Y-%m-%d").date()).days))
    lm_recent = pct(sm.get("modified_last_12m", 0), sm.get("with_lastmod", 0))
    if not posts and not dated:
        put("geo.freshness", "warn" if lm_recent < 30 else "pass",
            f"Sem artigos na amostra. {lm_recent}% das URLs com lastmod foram atualizadas nos últimos 12 meses.")
    else:
        fresh = [u for u, dd in dated if dd <= 365]
        cover = len(dated) / max(len(posts), 1)
        put("geo.freshness", "pass" if cover >= 0.8 and len(fresh) >= 0.5 * max(len(dated), 1) else "warn" if dated else "fail",
            f"{len(dated)} de {len(posts)} artigos com data legível por máquina; {len(fresh)} atualizados nos últimos 12 meses; "
            f"{lm_recent}% das URLs do sitemap com lastmod no último ano.", data={"ages_days": dated[:15]})

    if not posts:
        put("geo.authorship", "unknown", "Nenhum artigo na amostra para avaliar autoria; checar manualmente páginas de autor/equipe.")
    else:
        authored = [p for p in posts if p.get("byline_text") or (p.get("dates") or {}).get("schema_author") or p.get("meta_author")]
        person = [p for p in posts if "Person" in p.get("jsonld_types", [])]
        put("geo.authorship", "pass" if len(authored) == len(posts) and person else "warn" if authored else "fail",
            f"{len(authored)}/{len(posts)} artigos com autor identificado; {len(person)} com Person no schema.",
            [p["url"] for p in posts if p not in authored])

    sameas = sorted({s for p in P for s in p.get("schema_sameas", [])})
    about = [p for p in P if p["type"] == "about"]
    socials = sorted({s for p in P for s in p.get("social_links", [])})
    pts = (1 if org else 0) + (1 if len(sameas) >= 2 else 0.5 if sameas else 0) + (1 if about else 0) \
        + (0.5 if len(socials) >= 2 and len(sameas) < 2 else 0)
    put("geo.org_entity", "pass" if pts >= 3 else "warn" if pts >= 1.5 else "fail",
        f"Organization: {'sim' if org else 'não'}; sameAs: {len(sameas)} perfis; página Sobre: {'sim' if about else 'não'}; "
        f"links sociais no site: {len(socials)}.", data={"sameAs": sameas, "socials": socials[:10]})

    put("geo.llms_txt", "na", f"llms.txt: {'presente' if site['llms_txt']['present'] else 'ausente'}. Informativo: sem evidência de impacto em citações.")

    # ---------------- AEO -----------------------------------------------------
    qa = [(p["url"], a) for p in P for a in p.get("answer_after_question", [])]
    good = [x for x in qa if x[1]["next_tag"] == "p" and 25 <= x[1]["words"] <= 80]
    qh_pages = [p for p in P if p.get("question_headings")]
    if not qa:
        put("aeo.direct_answers", "fail", "Nenhum H2/H3 em formato de pergunta encontrado nas páginas auditadas.")
    else:
        r = len(good) / len(qa)
        put("aeo.direct_answers", "pass" if r >= 0.6 and len(qh_pages) >= n / 3 else "warn" if r >= 0.3 or len(good) >= 3 else "fail",
            f"{len(qa)} headings de pergunta em {len(qh_pages)} página(s); {len(good)} seguidos de parágrafo de 25-80 palavras.",
            data={"examples": [{"url": u, **a} for u, a in qa[:8]]})

    lt = [p for p in P if p.get("lists", 0) or p.get("tables", 0)]
    cand = [p for p in P if p["type"] in ("blog_post", "comparison", "pricing", "product", "service")]
    with_struct = [p for p in cand if p.get("lists", 0) >= 1 or p.get("tables", 0) >= 1]
    put("aeo.structured_formats", "na" if not cand else status_from_ratio(len(with_struct) / len(cand), 0.7, 0.4),
        f"{len(with_struct)}/{len(cand)} páginas de conteudo/comerciais usam listas ou tabelas; tabelas no total: {sum(p.get('tables', 0) for p in P)}.")

    faq_pages = [p for p in P if p["type"] == "faq" or len(p.get("question_headings", [])) >= 3 or "FAQPage" in p.get("jsonld_types", [])]
    commercial = [p for p in P if p["type"] in ("product", "service", "pricing", "home")]
    put("aeo.faq_content", "pass" if len(faq_pages) >= 2 else "warn" if faq_pages else "fail",
        f"{len(faq_pages)} página(s) com bloco de perguntas (3+ headings de pergunta, página FAQ ou FAQPage); {len(commercial)} páginas comerciais auditadas.",
        [p["url"] for p in faq_pages])

    ns = [p["url"] for p in P if re.search(r"nosnippet|max-snippet:\s*0", ((p.get("meta_robots") or "") + (p.get("x_robots_tag") or "")), re.I)]
    put("aeo.snippet_controls", "fail" if ns else "pass", f"{len(ns)} página(s) com nosnippet ou max-snippet:0.", ns)

    dep = sorted({t for p in P for t in p.get("jsonld_types", []) if t in DEPRECATED})
    bc = [p for p in P if "BreadcrumbList" in p.get("jsonld_types", [])]
    sup = sorted({t for p in P for t in p.get("jsonld_types", []) if t in RICH_SUPPORTED})
    pts = (1 if bc else 0) + (1 if len(sup) >= 3 else 0.5 if sup else 0)
    put("aeo.rich_result_schema", "pass" if pts >= 2 else "warn" if pts >= 1 else "fail",
        f"Tipos com rich result ativo: {', '.join(sup) or 'nenhum'}; BreadcrumbList em {len(bc)}/{n} páginas."
        + (f" Tipos sem rich result para a maioria dos sites: {', '.join(f'{d} ({DEPRECATED[d]})' for d in dep)}." if dep else ""),
        data={"deprecated": dep})
    # ---------------- v1.1: links, redirecionamentos, sitemap, hreflang, Bing, preço ----
    def short(u):
        return re.sub(r"^https?://[^/]+", "", u) or "/"

    L = site.get("links")
    if not L or not L.get("checked"):
        put("seo.broken_links", "unknown", "Verificação de links não executada (rode a fase de links da coleta).")
        put("seo.redirects", "unknown", "Verificação de links não executada.")
    else:
        chk, br = L["checked"], L["broken"]
        unv = L.get("unverified", 0)
        put("seo.broken_links", "pass" if not br else "warn" if len(br) <= max(2, 0.03 * chk) else "fail",
            f"{len(br)} de {chk} links internos verificados retornam erro"
            + (": " + "; ".join(f"{short(b['url'])} ({b['status'] or 'sem resposta'}, linkado em {', '.join(short(x) for x in b['sources'][:2]) or '?'})" for b in br[:4]) if br else "")
            + (f". {unv} não puderam ser verificados pelo navegador." if unv else "."),
            [b["url"] for b in br], {"broken": br[:20]})
        rd, ch, hl = L["redirected"], L.get("chains_2plus", []), L.get("http_internal_links", [])
        put("seo.redirects", "pass" if not rd and not hl else "fail" if ch or len(rd) > 0.15 * chk else "warn",
            f"{len(rd)} link(s) interno(s) passam por redirecionamento; {len(ch)} com cadeia de 2+ saltos; {len(hl)} link(s) http:// num site https."
            + (" Ex.: " + "; ".join(f"{short(x['url'])} -> {short(x['final_url'])}" for x in rd[:3]) if rd else ""),
            [x["url"] for x in rd], {"redirected": rd[:20], "http_links": hl[:10]})

    SH = site.get("sitemap_health")
    if not sm["url_count"]:
        put("seo.sitemap_health", "na", "Sem sitemap para amostrar.")
    elif not SH or not SH.get("sampled"):
        put("seo.sitemap_health", "unknown", "Amostra do sitemap não verificada.")
    else:
        bad = SH["non_200"] + [{"url": u, "status": "noindex"} for u in SH["noindex"]]
        put("seo.sitemap_health", "pass" if not bad and len(SH["redirects"]) <= 1 else "fail" if len(bad) > 0.1 * SH["sampled"] else "warn",
            f"Amostra de {SH['sampled']} URLs do sitemap: {len(SH['non_200'])} com erro, {len(SH['redirects'])} redirecionando, {len(SH['noindex'])} com noindex."
            + (" Ex.: " + "; ".join(f"{short(b['url'])} ({b['status']})" for b in bad[:3]) if bad else ""),
            [b["url"] for b in bad] + [x["url"] for x in SH["redirects"]])

    hl_pages = [p for p in P if p.get("hreflang")]
    langs = {(p.get("lang") or "").lower()[:2] for p in P if p.get("lang")}
    if not hl_pages:
        put("seo.hreflang", "fail" if len(langs) > 1 else "na",
            f"Páginas em idiomas diferentes ({', '.join(sorted(langs))}) sem hreflang." if len(langs) > 1 else "Site em um idioma só: hreflang não se aplica.")
    else:
        code_re = re.compile(r"^(x-default|[a-z]{2,3}(-[A-Za-z]{2}|-[A-Za-z]{4})?)$")
        bad_codes = sorted({h["lang"] for p in hl_pages for h in p["hreflang"] if not code_re.match(h.get("lang") or "")})
        no_self = [p["url"] for p in hl_pages if not any(urljoin(p["url"], h["href"]).rstrip("/") == p["url"].rstrip("/") for h in p["hreflang"] if h.get("href"))]
        no_xdef = [p["url"] for p in hl_pages if not any((h.get("lang") or "").lower() == "x-default" for h in p["hreflang"])]
        fetched = {p["url"].rstrip("/"): p for p in P}
        nonrecip = []
        for p in hl_pages:
            for h in p["hreflang"]:
                tgt = fetched.get(urljoin(p["url"], h.get("href") or "").rstrip("/"))
                if tgt and tgt is not p and not any(urljoin(tgt["url"], x.get("href") or "").rstrip("/") == p["url"].rstrip("/") for x in tgt.get("hreflang", [])):
                    nonrecip.append(f"{short(p['url'])} -> {short(tgt['url'])}")
        broken_t = [b["url"] for b in (L or {}).get("broken", []) if "(hreflang/canonical)" in b.get("sources", [])]
        issues = len(bad_codes) * 2 + len(broken_t) * 2 + len(no_self) + len(nonrecip) + (1 if no_xdef else 0)
        put("seo.hreflang", "pass" if issues == 0 else "warn" if issues <= 3 and not broken_t and not bad_codes else "fail",
            f"hreflang em {len(hl_pages)} página(s). Códigos inválidos: {', '.join(bad_codes) or 'nenhum'}; sem autorreferência: {len(no_self)}; "
            f"sem x-default: {len(no_xdef)}; sem reciprocidade: {len(nonrecip)}; destinos com erro: {len(broken_t)}"
            + (f" ({', '.join(short(u) for u in broken_t[:3])})" if broken_t else "") + ".",
            no_self + broken_t, {"nonreciprocal": nonrecip[:10]})

    bing_meta = any((p.get("verification_metas") or {}).get("bing") for p in P)
    google_meta = any((p.get("verification_metas") or {}).get("google") for p in P)
    if bing_meta or site.get("bing_site_auth_xml"):
        put("seo.bing_webmaster", "pass", f"Verificação do Bing detectada ({'meta msvalidate.01' if bing_meta else 'BingSiteAuth.xml'}).")
    else:
        put("seo.bing_webmaster", "unknown",
            "Nenhuma verificação do Bing visível no HTML ou em /BingSiteAuth.xml. Pode estar verificada por DNS: confirmar com o cliente."
            + (" Verificação do Google por meta tag: sim." if google_meta else ""))

    pricing = [p for p in P if p["type"] == "pricing"]
    with_price = [p for p in P if p.get("price_mentions", 0) > 0 or p.get("schema_has_offer")]
    talk = sorted({t for p in P for t in p.get("price_talk", [])})
    if pricing:
        pp = [p for p in pricing if p.get("price_mentions", 0) > 0 or p.get("schema_has_offer")]
        put("aeo.pricing_visible", "pass" if pp else "warn" if any(p.get("price_talk") for p in pricing) else "fail",
            f"Página de preços: {short(pricing[0]['url'])}; valores em texto: {'sim' if pp else 'não'}"
            + (f"; menções: {', '.join(talk)}" if talk else "") + ("" if pp or pricing[0].get("word_count", 0) > 50 else "; página quase vazia no HTML do servidor") + ".",
            [p["url"] for p in pricing if p not in pp])
    else:
        put("aeo.pricing_visible", "pass" if with_price else "warn",
            ("Preços em texto em: " + ", ".join(short(p["url"]) for p in with_price[:3]) + "." if with_price else
             "Nenhuma página de preços nem valores em texto nas páginas auditadas"
             + (f" (apenas: {', '.join(talk)})" if talk else "") + ". Se o modelo é sob consulta, marque como N/A ou recomende 'a partir de'."))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site_json")
    ap.add_argument("--rubric", default=DEFAULT_RUBRIC)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    site = json.load(open(a.site_json, encoding="utf-8"))
    rubric = json.load(open(a.rubric, encoding="utf-8"))
    auto = run_checks(site)
    findings = []
    for c in rubric["checks"]:
        r = auto.get(c["id"])
        if r is None:
            r = {"status": "unknown", "evidence": "", "pages": [], "data": {}}
        item = {**c, "evidence_level": c["evidence"]}
        item.update(r)  # 'evidence' passa a ser o texto do que foi encontrado
        item["source"] = "auto" if c["id"] in auto else "pending"
        findings.append(item)
    out = a.out or os.path.join(os.path.dirname(a.site_json), "findings.json")
    json.dump({"host": site["host"], "mode": site["mode"], "audited_at": site["audited_at"],
               "collector": site.get("collector"), "pages_audited": [
                   {"url": p["url"], "type": p.get("type"), "status": p.get("status"), "words": p.get("word_count"),
                    "title": p.get("title")} for p in site["pages"]],
               "findings": findings}, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    pend = [f["id"] for f in findings if f["status"] == "unknown"]
    summary = Counter(f["status"] for f in findings)
    print(json.dumps({"out": out, "status_counts": summary, "pending_for_claude": pend}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
