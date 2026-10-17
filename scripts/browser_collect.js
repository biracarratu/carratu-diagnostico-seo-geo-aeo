// Coletor via navegador (Claude in Chrome / navegador integrado).
// Uso: abra a HOME do site numa aba e execute este arquivo inteiro com a ferramenta de JavaScript,
// trocando a linha CONFIG abaixo. Ele busca (fetch, mesma origem) o HTML do servidor de cada URL,
// robots.txt, sitemap e llms.txt, e devolve um JSON compacto. Salve a saida em
// audit_data/browser/batch-N.json e rode scripts/from_browser.py.
// Fase 1: CONFIG = {discover: true}  -> devolve site-level + lista de URLs candidatas
// Fase 2: CONFIG = {urls: [...ate 8 URLs...], excerptWords: 600} -> devolve sinais das paginas
// Fase 3: CONFIG = {checkLinks: [...ate 40 URLs...], readBody: false} -> status/redirecionamento de links
//         (use readBody: true para a amostra do sitemap, que tambem verifica noindex)
(async () => {
  const CONFIG = { discover: true, urls: [], excerptWords: 600, checkLinks: null, readBody: false }; // <- EDITAR
  const origin = location.origin;
  const host = location.host.replace(/^www\./, "");
  const Q = /(\?\s*$)|^(o que|como|por que|porque|quando|onde|qual|quais|quanto|quem|what|how|why|when|where|which|who|is|are|can|does|do|should)\b/i;
  const NUM = /\b\d+(?:[.,]\d+)?\s?(?:%|x|mil|milh(?:ao|oes|ão|ões)|bi|k|m)?\b/gi;
  const DEF = /\b(é um|é uma|são|refere-se a|consiste em|is a|is an|are|refers to|means)\b/i;
  const SOCIAL = ["linkedin.com","instagram.com","facebook.com","x.com","twitter.com","youtube.com","tiktok.com","github.com","wikipedia.org","wikidata.org","crunchbase.com","g2.com","capterra.com","reclameaqui.com.br"];
  const PRICE = /(R\$|US\$|USD|BRL|€|£|\$)\s?\d[\d.,]*|\d[\d.,]*\s?(?:reais|\/m[eê]s|por m[eê]s|\/month|per month|\/usu[aá]rio|\/user)/gi;
  const PTALK = /\b(gr[aá]tis|gratuito|free trial|teste gr[aá]tis|plano free|sob consulta|fale com vendas|solicite (?:um )?or[cç]amento|contact sales|request a quote)\b/gi;
  const T = (el) => (el ? (el.textContent || "").replace(/\s+/g, " ").trim() : "");
  const get = async (u) => {
    try { const r = await fetch(u, { redirect: "follow", credentials: "omit" });
      return { status: r.status, url: r.url, headers: Object.fromEntries(r.headers.entries()), body: await r.text() };
    } catch (e) { return { status: null, url: u, headers: {}, body: "", error: String(e).slice(0, 200) }; }
  };
  const flat = (node, types, sameas, nodes) => {
    if (Array.isArray(node)) return node.forEach((n) => flat(n, types, sameas, nodes));
    if (!node || typeof node !== "object") return;
    if (node["@type"]) { [].concat(node["@type"]).forEach((t) => types.push(String(t))); nodes.push(node); }
    if (node.sameAs) [].concat(node.sameAs).forEach((s) => sameas.push(String(s)));
    Object.values(node).forEach((v) => { if (v && typeof v === "object") flat(v, types, sameas, nodes); });
  };
  const extract = (html, url, status, headers) => {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const meta = (n, p) => { const el = n ? doc.querySelector(`meta[name="${n}" i]`) : doc.querySelector(`meta[property="${p}" i]`); return el ? (el.getAttribute("content") || "").trim() : null; };
    const vmeta = (n) => doc.querySelector(`meta[name="${n}" i]`);
    const types = [], sameas = [], nodes = []; let errs = 0;
    doc.querySelectorAll('script[type*="ld+json" i]').forEach((s) => { try { flat(JSON.parse(s.textContent), types, sameas, nodes); } catch { errs++; } });
    const internal = new Set(), ext = new Set(), social = new Set(), nav = []; let empty = 0;
    doc.querySelectorAll("a[href]").forEach((a) => {
      const href = a.getAttribute("href").trim();
      if (/^(mailto:|tel:|javascript:|#)/.test(href)) return;
      let u; try { u = new URL(href, url); } catch { return; }
      const h = u.host.replace(/^www\./, ""); u.hash = "";
      if (!T(a) && !a.querySelector("img[alt]")) empty++;
      if (h === host) { internal.add(u.href); if (a.closest("nav,header,footer")) nav.push(u.href); }
      else { ext.add(h); if (SOCIAL.some((s) => h.endsWith(s))) social.add(u.href); }
    });
    const byline = doc.querySelector('[class*="author" i],[class*="autor" i],[class*="byline" i],[rel="author"],[itemprop="author"]');
    const dates = { published: meta(null, "article:published_time"), modified: meta(null, "article:modified_time") || meta(null, "og:updated_time"),
      time_tags: [...doc.querySelectorAll("time[datetime]")].slice(0, 3).map((t) => t.getAttribute("datetime")) };
    nodes.forEach((n) => { ["datePublished", "dateModified"].forEach((k) => { if (n[k] && !dates[k]) dates[k] = String(n[k]); });
      if (n.author && !dates.schema_author) { const a = [].concat(n.author)[0]; dates.schema_author = String(a && a.name ? a.name : a).slice(0, 80); } });
    const imgs = [...doc.querySelectorAll("img")]; const noalt = imgs.filter((i) => !(i.getAttribute("alt") || "").trim());
    const scripts = doc.querySelectorAll("script").length;
    doc.querySelectorAll("script,style,noscript,svg,template,iframe").forEach((e) => e.remove());
    const main = doc.querySelector("main,article,[role=main]");
    const scope = (main || doc.body || doc.documentElement).cloneNode(true);
    if (!main) scope.querySelectorAll("nav,header,footer,aside,form").forEach((e) => e.remove());
    const text = T(scope); const words = text ? text.split(" ") : [];
    const paras = [...scope.querySelectorAll("p")].map(T).filter((p) => p.split(" ").length >= 5);
    const headings = [...doc.querySelectorAll("h1,h2,h3,h4,h5,h6")].map((h) => ({ level: +h.tagName[1], text: T(h).slice(0, 140) })).filter((h) => h.text);
    const qh = headings.filter((h) => h.level <= 3 && h.level >= 2 && Q.test(h.text)).map((h) => h.text);
    const aaq = [];
    doc.querySelectorAll("h2,h3").forEach((h) => { if (!Q.test(T(h))) return; let n = h.nextElementSibling;
      while (n && !/^(P|UL|OL|TABLE|H[1-6])$/.test(n.tagName)) n = n.querySelector("p,ul,ol,table") || n.nextElementSibling;
      if (n && !/^H/.test(n.tagName)) aaq.push({ q: T(h).slice(0, 120), next_tag: n.tagName.toLowerCase(), words: T(n).split(" ").length }); });
    const can = doc.querySelector('link[rel~="canonical"]');
    const lc = Object.fromEntries(Object.entries(headers || {}).map(([k, v]) => [k.toLowerCase(), v]));
    return {
      url, status, fetched_via: "browser", content_type: lc["content-type"] || null, x_robots_tag: lc["x-robots-tag"] || null,
      server_hints: Object.fromEntries(["server","cf-ray","x-vercel-id","x-powered-by","cache-control","last-modified"].filter((k) => lc[k]).map((k) => [k, lc[k]])),
      lang: doc.documentElement.getAttribute("lang"), title: doc.title || null, meta_description: meta("description"), meta_robots: meta("robots"),
      canonical: can ? new URL(can.getAttribute("href"), url).href : null, viewport: meta("viewport"),
      hreflang: [...doc.querySelectorAll('link[rel~="alternate"][hreflang]')].slice(0, 20).map((l) => ({ lang: l.getAttribute("hreflang"), href: l.getAttribute("href") })),
      og: Object.fromEntries(["title","description","image","type","site_name"].map((k) => [k, meta(null, "og:" + k)])), twitter_card: meta("twitter:card"), meta_author: meta("author"),
      h1: headings.filter((h) => h.level === 1).map((h) => h.text), headings: headings.slice(0, 80), question_headings: qh.slice(0, 30), answer_after_question: aaq.slice(0, 20),
      word_count: words.length, paragraph_count: paras.length,
      avg_paragraph_words: paras.length ? Math.round(10 * paras.reduce((s, p) => s + p.split(" ").length, 0) / paras.length) / 10 : 0,
      first_paragraph: (paras[0] || "").split(" ").slice(0, 90).join(" "), has_definition_sentence: DEF.test(words.slice(0, 300).join(" ")),
      lists: scope.querySelectorAll("ul,ol").length, tables: scope.querySelectorAll("table").length, blockquotes: scope.querySelectorAll("blockquote").length,
      numbers_in_text: (text.match(NUM) || []).length, images: imgs.length, images_missing_alt: noalt.length,
      images_missing_alt_sample: noalt.slice(0, 5).map((i) => (i.getAttribute("src") || "").slice(0, 120)),
      internal_links: [...internal].sort().slice(0, 60), internal_link_count: internal.size, nav_links: [...new Set(nav)].slice(0, 120),
      external_domains: [...ext].sort().slice(0, 80), external_link_count: ext.size, empty_anchor_links: empty, social_links: [...social].sort().slice(0, 20),
      jsonld_types: [...new Set(types)].sort(), jsonld_parse_errors: errs,
      microdata_types: [...new Set([...doc.querySelectorAll("[itemtype]")].map((e) => e.getAttribute("itemtype").replace(/\/$/, "").split("/").pop()))].filter(Boolean),
      schema_sameas: [...new Set(sameas)].slice(0, 20), byline_text: byline ? T(byline).slice(0, 120) : null, dates, script_tags: scripts,
      price_mentions: (text.match(PRICE) || []).length,
      price_talk: [...new Set((text.match(PTALK) || []).map((m) => m.toLowerCase()))].slice(0, 5),
      schema_has_offer: nodes.some((n) => "price" in n || (n.offers && typeof n.offers === "object")),
      verification_metas: { google: !!vmeta("google-site-verification"), bing: !!vmeta("msvalidate.01"), yandex: !!vmeta("yandex-verification") },
      main_text_excerpt: words.slice(0, CONFIG.excerptWords).join(" "), html_bytes: html.length,
    };
  };

  if (CONFIG.checkLinks) {
    const out = [];
    const one = async (u) => {
      try { const r = await fetch(u, { redirect: "follow", credentials: "omit" });
        let noindex = /noindex/i.test(r.headers.get("x-robots-tag") || "");
        if (CONFIG.readBody) { const b = await r.text(); noindex = noindex || /<meta[^>]+name=["']robots["'][^>]+content=["'][^"']*noindex/i.test(b); }
        return { url: u, status: r.status, chain: r.redirected ? [u] : [], final_url: r.url, noindex, error: null };
      } catch (e) { return { url: u, status: null, chain: [], final_url: u, noindex: false, error: String(e).slice(0, 120) }; }
    };
    const list = CONFIG.checkLinks.slice(0, 40);
    for (let i = 0; i < list.length; i += 8) out.push(...(await Promise.all(list.slice(i, i + 8).map(one))));
    return JSON.stringify({ phase: "links", readBody: CONFIG.readBody, results: out });
  }
  if (CONFIG.discover) {
    const [home, robots, llms, llmsFull, soft, bingAuth] = await Promise.all([get(location.href), get(origin + "/robots.txt"), get(origin + "/llms.txt"),
      get(origin + "/llms-full.txt"), get(origin + "/pagina-inexistente-" + Math.random().toString(36).slice(2, 8)), get(origin + "/BingSiteAuth.xml")]);
    const robotsTxt = robots.status === 200 && !/<html/i.test(robots.body.slice(0, 500)) ? robots.body : null;
    const smList = robotsTxt ? [...robotsTxt.matchAll(/^\s*sitemap:\s*(\S+)/gim)].map((m) => m[1]) : [];
    const smUrls = [], lastmods = [], smSources = []; const queue = smList.length ? smList : [origin + "/sitemap.xml", origin + "/sitemap_index.xml"]; let kids = 0;
    while (queue.length && smUrls.length < 5000) { const s = queue.shift(); if (new URL(s, origin).origin !== origin) continue; const r = await get(s);
      if (r.status !== 200) continue; const x = new DOMParser().parseFromString(r.body, "application/xml"); smSources.push(s);
      x.querySelectorAll("sitemap > loc").forEach((l) => { if (kids++ < 8) queue.push(l.textContent.trim()); });
      x.querySelectorAll("url").forEach((u) => { const l = u.querySelector("loc"), m = u.querySelector("lastmod"); if (l) smUrls.push(l.textContent.trim()); if (m) lastmods.push(m.textContent.trim().slice(0, 10)); }); }
    const rendered = (document.querySelector("main,article") || document.body).innerText.split(/\s+/).filter(Boolean).length;
    const homeSig = extract(home.body, home.url, home.status, home.headers);
    homeSig.rendered_word_count = rendered; homeSig.raw_word_count = homeSig.word_count;
    const info = (r) => { const ok = r.status === 200 && !/<html/i.test(r.body.slice(0, 300)) && r.body.trim().length > 20; return { present: ok, bytes: ok ? r.body.length : 0, excerpt: ok ? r.body.slice(0, 800) : null }; };
    return JSON.stringify({ phase: "discover", base: origin + "/", host: location.host, https: location.protocol === "https:",
      robots_txt: robotsTxt, llms_txt: info(llms), llms_full_txt: info(llmsFull), soft_404_status: soft.status, bing_site_auth_xml: bingAuth.status === 200 && /<user>/i.test(bingAuth.body),
      sitemap: { sources: smSources, urls: smUrls.slice(0, 3000), lastmods }, home: homeSig });
  }
  const pages = [];
  for (const u of CONFIG.urls.slice(0, 8)) { const r = await get(u);
    pages.push(r.status ? extract(r.body, r.url, r.status, r.headers) : { url: u, status: null, error: r.error }); }
  return JSON.stringify({ phase: "pages", pages });
})();
