#!/usr/bin/env python3
"""Calcula a dimensão "Visibilidade medida" a partir de planilhas simples, com ou sem Semrush.

A mesma planilha aceita dados de qualquer fonte (coluna source): semrush, gsc, websearch, chrome, hubspot, manual.
Assim a skill funciona para quem tem Semrush e para quem não tem.

Uso:
  python3 data_metrics.py prompts audit_data/prompts.csv --brand "Acme" --aliases "Acme CRM,acme.com.br" \
      --findings audit_data/findings.json
  python3 data_metrics.py serp audit_data/serp.csv --domain acme.com.br --findings audit_data/findings.json
  python3 data_metrics.py template audit_data            # cria prompts.csv e serp.csv vazios com cabeçalho

Saída: atualiza os checks vis.* em findings.json e grava audit_data/visibility.json, que o build_report.py
usa automaticamente na seção "Visibilidade medida" (se report.json não trouxer a sua própria).

prompts.csv (uma linha por resposta; rode cada prompt 3+ vezes por motor):
  prompt,intent,engine,run,brand_mentioned,brand_cited,position,competitors,sources,accurate
  intent: problema | categoria | comparacao | alternativas | preco | marca
  brand_mentioned / brand_cited / accurate: 1, 0 ou vazio · position: inicio | meio | fim | vazio
  competitors e sources: listas separadas por | (ou ; se o arquivo usar vírgula) · sources = domínios citados

serp.csv (uma linha por palavra-chave do ICP):
  keyword,intent,source,position,url,aio_present,aio_cites_brand,competitors_top10
  position: posição orgânica do domínio (vazio = fora do top 100 ou não encontrado)
  aio_present / aio_cites_brand: 1, 0 ou vazio (vazio = não verificado)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter, defaultdict

PROMPT_COLS = ["prompt", "intent", "engine", "run", "brand_mentioned", "brand_cited", "position", "competitors", "sources", "accurate"]
SERP_COLS = ["keyword", "intent", "source", "position", "url", "aio_present", "aio_cites_brand", "competitors_top10"]
NON_BRANDED = {"problema", "categoria", "comparacao", "comparação", "alternativas", "preco", "preço"}


def b(v):
    v = str(v or "").strip().lower()
    return True if v in ("1", "s", "sim", "y", "yes", "true") else False if v in ("0", "n", "nao", "não", "no", "false") else None


def split(v):
    return [x.strip() for x in re.split(r"[;|]", str(v or "")) if x.strip()]


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        header = f.readline()
        f.seek(0)
        delim = max(",;\t", key=header.count)  # o delimitador mais frequente no cabeçalho
        return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items() if k}
                for row in csv.DictReader(f, delimiter=delim)]


def set_checks(findings_path, items, source):
    data = json.load(open(findings_path, encoding="utf-8"))
    for it in items:
        for f in data["findings"]:
            if f["id"] == it["id"]:
                f.update({"status": it["status"], "evidence": it["evidence"], "source": source})
    json.dump(data, open(findings_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def merge_visibility(out_dir, block):
    path = os.path.join(out_dir, "visibility.json")
    cur = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for k, v in block.items():
        if k == "summary_parts":
            cur.setdefault("summary_parts", {}).update(v)
        elif k == "extra_tables":
            titles = {t["title"] for t in v}
            cur["extra_tables"] = [t for t in cur.get("extra_tables", []) if t["title"] not in titles] + v
        else:
            cur[k] = v
    cur["summary"] = " ".join(cur.get("summary_parts", {}).values())
    json.dump(cur, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return path


def grade(rate, hi, lo):
    return "pass" if rate >= hi else "warn" if rate >= lo else "fail"


# ----------------------------------------------------------------------------- prompts
def cmd_prompts(a):
    rows = read_csv(a.csv)
    if not rows:
        raise SystemExit("prompts.csv vazio")
    brand_names = [a.brand] + split(a.aliases)
    by_prompt = defaultdict(list)
    for r in rows:
        by_prompt[(r.get("prompt", ""), r.get("engine", "") or "?")].append(r)

    nb = [r for r in rows if (r.get("intent") or "").lower() in NON_BRANDED]
    base = nb or rows
    ment = [b(r.get("brand_mentioned")) for r in base if b(r.get("brand_mentioned")) is not None]
    cit = [b(r.get("brand_cited")) for r in base if b(r.get("brand_cited")) is not None]
    m_rate = sum(ment) / len(ment) if ment else 0
    c_rate = sum(cit) / len(cit) if cit else 0

    # share of voice: cada resposta conta 1 menção por entidade presente
    entity = Counter()
    for r in base:
        if b(r.get("brand_mentioned")):
            entity[a.brand] += 1
        for c in {x.lower(): x for x in split(r.get("competitors"))}.values():
            if c.lower() not in (n.lower() for n in brand_names):
                entity[c] += 1
    total = sum(entity.values()) or 1
    sov = [(k, v, round(100 * v / total)) for k, v in entity.most_common(10)]
    brand_share = entity[a.brand] / total
    comp_max = max([v for k, v in entity.items() if k != a.brand] or [0]) / total

    sources = Counter(d.lower().removeprefix("www.") for r in rows for d in split(r.get("sources")))
    pos = Counter((r.get("position") or "").lower() for r in base if b(r.get("brand_mentioned")))
    branded = [r for r in rows if (r.get("intent") or "").lower() == "marca"]
    acc = [b(r.get("accurate")) for r in branded if b(r.get("accurate")) is not None]
    engines = sorted({k[1] for k in by_prompt})
    runs = len(rows)

    items = [{"id": "vis.ai_answers", "status": grade(m_rate, 0.5, 0.15),
              "evidence": f"Marca mencionada em {sum(ment)} de {len(ment)} respostas ({round(100 * m_rate)}%) "
                          f"{'sem citar a marca no prompt' if nb else ''}; URL da marca citada em {round(100 * c_rate)}%. "
                          f"{len(by_prompt)} combinações prompt x motor ({', '.join(engines)}), {runs} respostas no total."
                          + (f" Descrição correta da marca em {sum(acc)}/{len(acc)} respostas sobre ela." if acc else "")}]
    if len(entity) > 1:
        st = "pass" if brand_share >= 0.8 * comp_max else "warn" if brand_share >= 0.4 * comp_max else "fail"
        items.append({"id": "vis.competitors", "status": st,
                      "evidence": "Share of voice nas respostas: " + ", ".join(f"{k} {p}%" for k, _, p in sov[:5]) + "."})
    set_checks(a.findings, items, a.source or "prompts")

    table_rows = []
    for (prompt, eng), rs in by_prompt.items():
        mm = [b(r.get("brand_mentioned")) for r in rs if b(r.get("brand_mentioned")) is not None]
        cc = [b(r.get("brand_cited")) for r in rs if b(r.get("brand_cited")) is not None]
        comps = Counter(c for r in rs for c in split(r.get("competitors")))
        table_rows.append({"prompt": prompt, "engine": eng, "runs": len(rs), "mentioned": f"{sum(mm)}/{len(mm)}",
                           "cited": f"{sum(cc)}/{len(cc)}", "competitors": [c for c, _ in comps.most_common(3)]})
    block = {
        "ai_method": f"{len(by_prompt)} combinações de prompt e motor ({', '.join(engines)}), {runs} respostas no total. "
                     "Reportamos taxa de menção em várias rodadas, não uma posição única.",
        "ai_prompts": table_rows,
        "summary_parts": {"prompts": f"Nos testes em IA, a marca apareceu em {round(100 * m_rate)}% das respostas e teve "
                                     f"{round(100 * brand_share)}% de share of voice frente aos concorrentes monitorados."},
        "extra_tables": [t for t in (
            {"title": "Share of voice nas respostas de IA", "header": ["Marca", "Respostas com menção", "Share"],
             "rows": [[k, str(v), f"{p}%"] for k, v, p in sov]} if len(entity) > 1 else None,
            {"title": "Fontes mais citadas pelas IAs", "header": ["Domínio", "Citações"],
             "rows": [[d, str(n)] for d, n in sources.most_common(12)]} if sources else None,
            {"title": "Posição da marca dentro das respostas", "header": ["Faixa", "Respostas"],
             "rows": [[k or "não informado", str(v)] for k, v in pos.most_common()]} if pos else None) if t],
    }
    path = merge_visibility(os.path.dirname(os.path.abspath(a.findings)), block)
    print(json.dumps({"mention_rate": round(m_rate, 3), "citation_rate": round(c_rate, 3), "share_of_voice": sov[:6],
                      "top_sources": sources.most_common(8), "checks": [(i["id"], i["status"]) for i in items],
                      "visibility_json": path}, ensure_ascii=False, indent=1))


# ----------------------------------------------------------------------------- serp
def cmd_serp(a):
    rows = read_csv(a.csv)
    if not rows:
        raise SystemExit("serp.csv vazio")

    def posv(r):
        try:
            return int(float(r.get("position") or ""))
        except ValueError:
            return None

    n = len(rows)
    top3 = [r for r in rows if (posv(r) or 999) <= 3]
    top10 = [r for r in rows if (posv(r) or 999) <= 10]
    srcs = sorted({(r.get("source") or "manual").lower() for r in rows})
    items = [{"id": "vis.rankings", "status": grade(len(top10) / n, 0.4, 0.15),
              "evidence": f"{len(top10)} de {n} palavras-chave do ICP no top 10 ({round(100 * len(top10) / n)}%), {len(top3)} no top 3. "
                          f"Fonte: {', '.join(srcs)}." + (" Posições por busca web são aproximadas (personalização e localização)."
                                                           if "websearch" in srcs else "")}]
    aio_rows = [r for r in rows if b(r.get("aio_present"))]
    aio_known = [r for r in rows if b(r.get("aio_present")) is not None]
    if aio_rows:
        cited = [r for r in aio_rows if b(r.get("aio_cites_brand"))]
        items.append({"id": "vis.ai_overviews", "status": grade(len(cited) / len(aio_rows), 0.4, 0.15),
                      "evidence": f"AI Overview presente em {len(aio_rows)} de {len(aio_known)} palavras verificadas; "
                                  f"a marca é citada em {len(cited)} delas ({round(100 * len(cited) / len(aio_rows))}%)."})
    elif aio_known:
        items.append({"id": "vis.ai_overviews", "status": "na",
                      "evidence": f"Nenhuma das {len(aio_known)} palavras verificadas exibe AI Overview."})
    set_checks(a.findings, items, a.source or ",".join(srcs))

    comp = Counter(c for r in rows for c in split(r.get("competitors_top10")))
    gaps = [r for r in rows if (posv(r) or 999) > 10]
    block = {
        "semrush" if "semrush" in srcs else "serp": {
            "highlights": [items[0]["evidence"]] + ([items[1]["evidence"]] if len(items) > 1 else [])
                          + ([f"Concorrentes mais presentes no top 10: {', '.join(f'{c} ({v})' for c, v in comp.most_common(5))}."] if comp else []),
            "table": {"header": ["Palavra-chave", "Intenção", "Posição", "AI Overview", "Cita a marca?"],
                      "rows": [[r.get("keyword", ""), r.get("intent", ""), str(posv(r) or "fora"),
                                {True: "sim", False: "não", None: "?"}[b(r.get("aio_present"))],
                                {True: "sim", False: "não", None: "?"}[b(r.get("aio_cites_brand"))]] for r in rows[:25]],
                      "widths": [6.0, 2.6, 2.0, 3.0, 3.4]}},
        "summary_parts": {"serp": f"Na busca tradicional, {round(100 * len(top10) / n)}% das palavras-chave monitoradas estão no top 10"
                                  + (f" e {len(gaps)} oportunidades estão fora dele." if gaps else ".")},
    }
    path = merge_visibility(os.path.dirname(os.path.abspath(a.findings)), block)
    print(json.dumps({"keywords": n, "top10": len(top10), "top3": len(top3), "aio_with_feature": len(aio_rows),
                      "checks": [(i["id"], i["status"]) for i in items], "visibility_json": path}, ensure_ascii=False, indent=1))


def cmd_template(a):
    os.makedirs(a.out_dir, exist_ok=True)
    for name, cols in (("prompts.csv", PROMPT_COLS), ("serp.csv", SERP_COLS)):
        p = os.path.join(a.out_dir, name)
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow(cols)
    print(json.dumps({"created": [os.path.join(a.out_dir, n) for n in ("prompts.csv", "serp.csv")]}))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prompts")
    p.add_argument("csv")
    p.add_argument("--brand", required=True)
    p.add_argument("--aliases", default="")
    p.add_argument("--findings", required=True)
    p.add_argument("--source", default=None)
    s = sub.add_parser("serp")
    s.add_argument("csv")
    s.add_argument("--domain", required=True)
    s.add_argument("--findings", required=True)
    s.add_argument("--source", default=None)
    t = sub.add_parser("template")
    t.add_argument("out_dir")
    a = ap.parse_args()
    {"prompts": cmd_prompts, "serp": cmd_serp, "template": cmd_template}[a.cmd](a)


if __name__ == "__main__":
    main()
