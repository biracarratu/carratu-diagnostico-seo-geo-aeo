"""Extrai sinais de SEO/GEO/AEO de um HTML bruto.

Usado por crawl.py (coleta via rede) e por from_html.py (HTML vindo do navegador).
Saida: dict JSON-serializavel com o mesmo formato que extract_signals.js produz.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urljoin, urlparse

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    raise SystemExit("Instale beautifulsoup4: pip install beautifulsoup4 --break-system-packages")

try:
    import lxml  # noqa: F401
    PARSER = "lxml"
except ImportError:  # pragma: no cover
    PARSER = "html.parser"

QUESTION_RE = re.compile(
    r"(\?\s*$)|^(o que|como|por que|porque|quando|onde|qual|quais|quanto|quem|"
    r"what|how|why|when|where|which|who|is|are|can|does|do|should)\b",
    re.I,
)
NUMBER_RE = re.compile(r"\b\d+(?:[.,]\d+)?\s?(?:%|x|mil|milh(?:ao|oes|ão|ões)|bi|k|m)?\b", re.I)
DEFINITION_RE = re.compile(r"\b(é um|é uma|são|refere-se a|consiste em|is a|is an|are|refers to|means)\b", re.I)
SOCIAL_HOSTS = ("linkedin.com", "instagram.com", "facebook.com", "x.com", "twitter.com",
                "youtube.com", "tiktok.com", "github.com", "wikipedia.org", "wikidata.org",
                "crunchbase.com", "g2.com", "capterra.com", "reclameaqui.com.br")
PRICE_RE = re.compile(r"(R\$|US\$|USD|BRL|€|£|\$)\s?\d[\d.,]*|\d[\d.,]*\s?(?:reais|/m[eê]s|por m[eê]s|/month|per month|/usu[aá]rio|/user)", re.I)
PRICE_TALK_RE = re.compile(r"\b(gr[aá]tis|gratuito|free trial|teste gr[aá]tis|plano free|sob consulta|fale com vendas|solicite (?:um )?or[cç]amento|contact sales|request a quote)\b", re.I)
VERIFY_METAS = {"google": "google-site-verification", "bing": "msvalidate.01", "yandex": "yandex-verification"}
BYLINE_HINTS = re.compile(r"(author|autor|byline|escrito-por|post-author|entry-author)", re.I)


def _text(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


def _flatten_types(node, acc: list, sameas: list, raw_nodes: list):
    if isinstance(node, list):
        for n in node:
            _flatten_types(n, acc, sameas, raw_nodes)
        return
    if not isinstance(node, dict):
        return
    t = node.get("@type")
    if t:
        for tt in (t if isinstance(t, list) else [t]):
            acc.append(str(tt))
        raw_nodes.append(node)
    sa = node.get("sameAs")
    if sa:
        sameas.extend(sa if isinstance(sa, list) else [sa])
    for k, v in node.items():
        if k == "@graph" or isinstance(v, (dict, list)):
            _flatten_types(v, acc, sameas, raw_nodes)


def _summarize_node(n: dict) -> dict:
    """Versao compacta de um no de schema para o relatorio (sem textos longos)."""
    out = {}
    for k, v in n.items():
        if isinstance(v, str):
            out[k] = v[:160]
        elif isinstance(v, (int, float, bool)):
            out[k] = v
        elif isinstance(v, dict):
            out[k] = {"@type": v.get("@type"), "name": str(v.get("name", ""))[:80]} if v.get("@type") else "{...}"
        elif isinstance(v, list):
            out[k] = f"[{len(v)} itens]"
    return out


def extract(html: str, url: str, status: int | None = None, headers: dict | None = None,
            fetched_via: str = "python") -> dict:
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    soup = BeautifulSoup(html or "", PARSER)
    host = urlparse(url).netloc.lower().removeprefix("www.")

    def meta(name=None, prop=None):
        el = soup.find("meta", attrs={"name": re.compile(f"^{name}$", re.I)}) if name else \
            soup.find("meta", attrs={"property": re.compile(f"^{prop}$", re.I)})
        return (el.get("content") or "").strip() if el else None

    # --- JSON-LD -----------------------------------------------------------
    jsonld_types, sameas, nodes, jsonld_errors = [], [], [], 0
    for s in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        raw = (s.string or s.get_text() or "").strip()
        if not raw:
            continue
        try:
            _flatten_types(json.loads(raw), jsonld_types, sameas, nodes)
        except Exception:
            jsonld_errors += 1
    microdata_types = sorted({(el.get("itemtype") or "").rstrip("/").split("/")[-1]
                              for el in soup.find_all(attrs={"itemtype": True})} - {""})

    # --- links (antes de remover nav/footer) --------------------------------
    internal, external_domains, social_links = set(), set(), set()
    nav_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absu = urljoin(url, href).split("#")[0]
        h = urlparse(absu).netloc.lower().removeprefix("www.")
        if not h:
            continue
        if h == host:
            internal.add(absu)
            if a.find_parent(["nav", "header", "footer"]):
                nav_links.append(absu)
        else:
            external_domains.add(h)
            if any(h.endswith(s) for s in SOCIAL_HOSTS):
                social_links.add(absu)
    empty_anchor = sum(1 for a in soup.find_all("a", href=True) if not _text(a) and not a.find("img", alt=True))

    # --- autoria / datas -------------------------------------------------------
    byline_el = soup.find(attrs={"class": BYLINE_HINTS}) or soup.find(attrs={"rel": "author"}) \
        or soup.find(attrs={"itemprop": "author"})
    dates = {
        "published": meta(prop="article:published_time"),
        "modified": meta(prop="article:modified_time") or meta(prop="og:updated_time"),
        "time_tags": [t.get("datetime") for t in soup.find_all("time") if t.get("datetime")][:3],
    }
    for n in nodes:
        for key in ("datePublished", "dateModified"):
            if n.get(key) and not dates.get(key):
                dates[key] = str(n.get(key))
        if n.get("author") and not dates.get("schema_author"):
            a = n["author"]
            a = a[0] if isinstance(a, list) and a else a
            dates["schema_author"] = (a.get("name") if isinstance(a, dict) else str(a))[:80]

    # --- imagens ------------------------------------------------------------
    imgs = soup.find_all("img")
    img_no_alt = [i.get("src", "")[:120] for i in imgs if not (i.get("alt") or "").strip()]

    # --- conteudo principal ---------------------------------------------------
    scripts_count = len(soup.find_all("script"))
    for t in soup(["script", "style", "noscript", "svg", "template", "iframe"]):
        t.decompose()
    main = soup.find("main") or soup.find("article") or soup.find(attrs={"role": "main"})
    body_scope = main or soup.body or soup
    scope_copy = BeautifulSoup(str(body_scope), PARSER)
    if not main:
        for t in scope_copy(["nav", "header", "footer", "aside", "form"]):
            t.decompose()
    main_text = _text(scope_copy)
    words = main_text.split()
    paragraphs = [p for p in (_text(x) for x in scope_copy.find_all("p")) if len(p.split()) >= 5]

    headings = []
    for h in soup.find_all(re.compile("^h[1-6]$")):
        txt = _text(h)
        if txt:
            headings.append({"level": int(h.name[1]), "text": txt[:140]})
    h1s = [h["text"] for h in headings if h["level"] == 1]
    sub = [h for h in headings if h["level"] in (2, 3)]
    question_headings = [h["text"] for h in sub if QUESTION_RE.search(h["text"])]

    # resposta logo apos headings em formato de pergunta (40-60 palavras ideal)
    answer_first = []
    for h in soup.find_all(["h2", "h3"]):
        if not QUESTION_RE.search(_text(h)):
            continue
        nxt = h.find_next(["p", "ul", "ol", "table"])
        if nxt is not None:
            answer_first.append({"q": _text(h)[:120], "next_tag": nxt.name,
                                 "words": len(_text(nxt).split())})
    first_para = paragraphs[0] if paragraphs else ""

    price_hits = PRICE_RE.findall(main_text)
    schema_price = any(("price" in n) or (isinstance(n.get("offers"), (dict, list))) for n in nodes)
    verifications = {k: bool(soup.find("meta", attrs={"name": re.compile(f"^{v}$", re.I)})) for k, v in VERIFY_METAS.items()}

    hreflang = [{"lang": l.get("hreflang"), "href": l.get("href")}
                for l in soup.find_all("link", rel=lambda v: v and "alternate" in v, hreflang=True)]
    canonical_el = soup.find("link", rel=lambda v: v and "canonical" in v)

    return {
        "url": url,
        "status": status,
        "fetched_via": fetched_via,
        "content_type": headers.get("content-type"),
        "x_robots_tag": headers.get("x-robots-tag"),
        "server_hints": {k: headers[k] for k in ("server", "cf-ray", "x-vercel-id", "x-powered-by",
                                                   "cache-control", "last-modified") if k in headers},
        "lang": (soup.html.get("lang") if soup.html else None),
        "title": _text(soup.title) if soup.title else None,
        "meta_description": meta("description"),
        "meta_robots": meta("robots"),
        "canonical": urljoin(url, canonical_el["href"]) if canonical_el and canonical_el.get("href") else None,
        "viewport": meta("viewport"),
        "hreflang": hreflang[:20],
        "og": {k: meta(prop=f"og:{k}") for k in ("title", "description", "image", "type", "site_name")},
        "twitter_card": meta("twitter:card"),
        "meta_author": meta("author"),
        "h1": h1s,
        "headings": headings[:80],
        "question_headings": question_headings[:30],
        "answer_after_question": answer_first[:20],
        "word_count": len(words),
        "paragraph_count": len(paragraphs),
        "avg_paragraph_words": round(sum(len(p.split()) for p in paragraphs) / len(paragraphs), 1) if paragraphs else 0,
        "first_paragraph": " ".join(first_para.split()[:90]),
        "has_definition_sentence": bool(DEFINITION_RE.search(" ".join(words[:300]))),
        "lists": len(scope_copy.find_all(["ul", "ol"])),
        "tables": len(scope_copy.find_all("table")),
        "blockquotes": len(scope_copy.find_all("blockquote")),
        "numbers_in_text": len(NUMBER_RE.findall(main_text)),
        "images": len(imgs),
        "images_missing_alt": len(img_no_alt),
        "images_missing_alt_sample": img_no_alt[:5],
        "internal_links": sorted(internal)[:400],
        "internal_link_count": len(internal),
        "nav_links": list(dict.fromkeys(nav_links))[:120],
        "external_domains": sorted(external_domains)[:80],
        "external_link_count": len(external_domains),
        "empty_anchor_links": empty_anchor,
        "social_links": sorted(social_links)[:20],
        "jsonld_types": sorted(set(jsonld_types)),
        "jsonld_nodes": [_summarize_node(n) for n in nodes[:15]],
        "jsonld_parse_errors": jsonld_errors,
        "microdata_types": microdata_types,
        "schema_sameas": sorted(set(map(str, sameas)))[:20],
        "byline_text": _text(byline_el)[:120] if byline_el else None,
        "dates": dates,
        "script_tags": scripts_count,
        "price_mentions": len(price_hits),
        "price_talk": sorted({m.lower() for m in PRICE_TALK_RE.findall(main_text)})[:5],
        "schema_has_offer": schema_price,
        "verification_metas": verifications,
        "main_text_excerpt": " ".join(words[:1200]),
    }
