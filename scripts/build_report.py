#!/usr/bin/env python3
"""Gera o relatorio DOCX (e PDF, se o LibreOffice estiver disponivel).

Uso:
  python3 build_report.py audit_data/findings.json audit_data/report.json --out outputs/
  [--brand ../assets/brand.json] [--no-pdf]

findings.json: saida de analyze.py + score.py (checks completos).
report.json:   narrativa escrita pelo Claude. Formato em references/report-schema.md.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

try:
    from docx import Document
    from docx.enum.section import WD_SECTION
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor, Cm
except ImportError:
    raise SystemExit("Instale python-docx: pip install python-docx --break-system-packages")

HERE = os.path.dirname(os.path.abspath(__file__))
STATUS_PT = {"pass": "OK", "warn": "Atenção", "fail": "Falha", "na": "N/A", "unknown": "Não avaliado"}
DIM_NAME = {"SEO": "SEO", "GEO": "GEO", "AEO": "AEO", "VIS": "Visibilidade medida"}
DIM_DESC = {
    "SEO": "Fundação técnica e on-page: ser rastreado, indexado e ranquear no Google e no Bing.",
    "GEO": "Prontidão para ser recuperado e citado por ChatGPT, Perplexity, Gemini, Claude e AI Overviews.",
    "AEO": "Respostas extraíveis para snippets, People Also Ask, AI Overviews e assistentes de voz.",
    "VIS": "O que os dados externos mostram de verdade: rankings, AI Overviews e citações em respostas de IA.",
}
PRIO_KEY = {"critica": "critical", "critical": "critical", "alta": "high", "high": "high",
            "media": "medium", "medium": "medium", "ganho rapido": "quickwin", "quick win": "quickwin", "quickwin": "quickwin"}


def norm(txt):
    import unicodedata
    return "".join(ch for ch in unicodedata.normalize("NFD", str(txt).lower().strip()) if unicodedata.category(ch) != "Mn")


# ------------------------------------------------------------------ helpers
def rgb(h):
    return RGBColor.from_string(h.upper())


def shade(cell, hex_color):
    tcPr = cell._tc.get_or_add_tcPr()
    for old in tcPr.findall(qn("w:shd")):
        tcPr.remove(old)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_color)
    tcPr.append(shd)


def cell_margins(cell, top=80, bottom=80, left=100, right=100):
    tcPr = cell._tc.get_or_add_tcPr()
    mar = OxmlElement("w:tcMar")
    for k, v in (("top", top), ("bottom", bottom), ("start", left), ("end", right)):
        el = OxmlElement(f"w:{k}")
        el.set(qn("w:w"), str(v))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tcPr.append(mar)


def table_borders(table, color="E5E7EB", size=4, inside=True):
    tblPr = table._tbl.tblPr
    b = OxmlElement("w:tblBorders")
    edges = ["top", "left", "bottom", "right"] + (["insideH", "insideV"] if inside else [])
    for e in ["top", "left", "bottom", "right", "insideH", "insideV"]:
        el = OxmlElement(f"w:{e}")
        if e in edges:
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), str(size))
            el.set(qn("w:color"), color)
        else:
            el.set(qn("w:val"), "nil")
        b.append(el)
    tblPr.append(b)


def set_col_widths(table, widths_cm):
    table.autofit = False
    tbl = table._tbl
    tblPr = tbl.tblPr
    for old in tblPr.findall(qn("w:tblW")) + tblPr.findall(qn("w:tblLayout")):
        tblPr.remove(old)
    tw = OxmlElement("w:tblW")
    tw.set(qn("w:w"), str(int(sum(widths_cm) * 567)))
    tw.set(qn("w:type"), "dxa")
    tblPr.append(tw)
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tblPr.append(layout)
    grid = tbl.tblGrid
    cols = grid.findall(qn("w:gridCol"))
    for i, w in enumerate(widths_cm):
        if i < len(cols):
            cols[i].set(qn("w:w"), str(int(w * 567)))
    for row in table.rows:
        for i, w in enumerate(widths_cm):
            if i < len(row.cells):
                row.cells[i].width = Cm(w)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def keep_row_together(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def add_field(paragraph, instr):
    run = paragraph.add_run()
    for t, extra in (("begin", None), ("instr", instr), ("separate", None), ("end", None)):
        if t == "instr":
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = extra
        else:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), t)
        run._r.append(el)
    return run


def para_border_bottom(p, color, size=8):
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    el = OxmlElement("w:bottom")
    el.set(qn("w:val"), "single")
    el.set(qn("w:sz"), str(size))
    el.set(qn("w:space"), "4")
    el.set(qn("w:color"), color)
    bdr.append(el)
    pPr.append(bdr)


def set_page_background(doc, hex_color):
    """Cor de fundo da página (tema escuro). Word e LibreOffice respeitam."""
    body = doc.element
    for old in body.findall(qn("w:background")):
        body.remove(old)
    bg = OxmlElement("w:background")
    bg.set(qn("w:color"), hex_color)
    body.insert(0, bg)
    settings = doc.settings.element
    if settings.find(qn("w:displayBackgroundShape")) is None:
        settings.insert(0, OxmlElement("w:displayBackgroundShape"))


def letter_spacing(run, twips):
    rPr = run._r.get_or_add_rPr()
    sp = OxmlElement("w:spacing")
    sp.set(qn("w:val"), str(twips))
    rPr.append(sp)


def asset_path(brand, rel):
    if not rel:
        return None
    p = rel if os.path.isabs(rel) else os.path.join(brand.get("_dir", os.path.join(HERE, "..", "assets")), rel)
    return p if os.path.exists(p) else None


def producer_footer(R, section, brand):
    """Rodapé: texto de crédito + logo da produtora (largura máxima em px, 96 dpi)."""
    pf = brand.get("producer_footer")
    if not pf:
        return
    fp = section.footer.paragraphs[0]
    fp.text = ""
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    R.runs(fp, pf.get("text", "") + "  ", size=7.5, color=R.c["muted"])
    logo = asset_path(brand, pf.get("logo"))
    if logo:
        width_cm = min(int(pf.get("max_width_px", 70)), 70) * 2.54 / 96  # 70 px a 96 dpi = 1,85 cm
        fp.add_run().add_picture(logo, width=Cm(width_cm))


class Report:
    def __init__(self, brand):
        self.b = brand
        self.c = brand["colors"]
        self.doc = Document()
        st = self.doc.styles["Normal"]
        st.font.name = brand.get("font", "Arial")
        st.element.rPr.rFonts.set(qn("w:eastAsia"), brand.get("font", "Arial"))
        st.font.size = Pt(10.5)
        st.font.color.rgb = rgb(self.c["text"])
        st.paragraph_format.space_after = Pt(6)
        st.paragraph_format.line_spacing = 1.15
        self.dark = brand.get("theme") == "dark"
        hfont = brand.get("heading_font") or brand.get("font", "Arial")
        for lvl, size in ((1, 20), (2, 14), (3, 12)):
            h = self.doc.styles[f"Heading {lvl}"]
            h.font.name = hfont
            h.element.rPr.rFonts.set(qn("w:asciiTheme"), "")
            h.element.rPr.rFonts.set(qn("w:hAnsiTheme"), "")
            h.font.size = Pt(size)
            h.font.bold = True
            if self.dark:
                h.font.color.rgb = rgb(self.c["text"] if lvl != 2 else self.c.get("eyebrow", self.c["primary"]))
            else:
                h.font.color.rgb = rgb(self.c["dark"] if lvl != 2 else self.c["primary"])
            h.paragraph_format.space_before = Pt(18 if lvl == 1 else 12)
            h.paragraph_format.space_after = Pt(6)
            h.paragraph_format.keep_with_next = True
        sec = self.doc.sections[0]
        sec.page_width, sec.page_height = Cm(21), Cm(29.7)
        for side in ("left_margin", "right_margin"):
            setattr(sec, side, Cm(2))
        sec.top_margin, sec.bottom_margin = Cm(2), Cm(2)
        self.width_cm = 17.0
        if self.dark:
            set_page_background(self.doc, self.c["page_bg"])

    # -- primitives
    def p(self, text="", size=None, bold=False, color=None, italic=False, align=None, after=None, before=None):
        para = self.doc.add_paragraph()
        if text:
            self.runs(para, text, size=size, bold=bold, color=color, italic=italic)
        if align == "center":
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if after is not None:
            para.paragraph_format.space_after = Pt(after)
        if before is not None:
            para.paragraph_format.space_before = Pt(before)
        return para

    def runs(self, para, text, size=None, bold=False, color=None, italic=False):
        # suporta **negrito** simples dentro do texto
        for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", str(text))):
            if not part:
                continue
            r = para.add_run(part)
            r.bold = bold or (i % 2 == 1)
            r.italic = italic
            if size:
                r.font.size = Pt(size)
            if color:
                r.font.color.rgb = rgb(color)
        return para

    def bullet(self, text):
        para = self.doc.add_paragraph(style="List Bullet")
        self.runs(para, text)
        para.paragraph_format.space_after = Pt(3)
        return para

    def cell_text(self, cell, text, bold=False, color=None, size=9.5, align=None, italic=False):
        cell.text = ""
        para = cell.paragraphs[0]
        para.paragraph_format.space_after = Pt(0)
        self.runs(para, text, size=size, bold=bold, color=color, italic=italic)
        if align == "center":
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        return para

    def table(self, header, rows, widths, status_col=None, status_map=None, zebra=True, header_color=None):
        t = self.doc.add_table(rows=1, cols=len(header))
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        table_borders(t, self.c["border"])
        hdr = t.rows[0]
        repeat_header(hdr)
        for i, h in enumerate(header):
            c = hdr.cells[i]
            shade(c, header_color or self.c["dark"])
            cell_margins(c)
            self.cell_text(c, h, bold=True, color="FFFFFF", size=9)
        for ri, row in enumerate(rows):
            r = t.add_row()
            keep_row_together(r)
            for i, val in enumerate(row):
                c = r.cells[i]
                cell_margins(c)
                if status_col is not None and i == status_col and status_map:
                    key, label = val
                    shade(c, status_map.get(key, self.c["na"]))
                    self.cell_text(c, label, bold=True, color="FFFFFF", size=8.5, align="center")
                else:
                    if zebra and ri % 2 == 1:
                        shade(c, self.c["light_bg"])
                    self.cell_text(c, val if val is not None else "")
        set_col_widths(t, widths)
        self.p(after=4)
        return t

    def callout(self, text, fill=None, border=None, title=None):
        t = self.doc.add_table(rows=1, cols=1)
        table_borders(t, border or self.c["primary"], size=12, inside=False)
        c = t.rows[0].cells[0]
        shade(c, fill or "FFF4EF")
        cell_margins(c, 160, 160, 200, 200)
        c.text = ""
        if title:
            self.runs(c.paragraphs[0], title, bold=True, size=11, color=self.c["primary"])
            para = c.add_paragraph()
        else:
            para = c.paragraphs[0]
        for i, chunk in enumerate([x for x in str(text).split("\n\n") if x.strip()]):
            if i:
                para = c.add_paragraph()
            self.runs(para, chunk.strip(), size=10.5)
        set_col_widths(t, [self.width_cm])
        self.p(after=6)

    def page_break(self):
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def score_color(self, s):
        if s is None:
            return self.c["na"]
        return self.c["pass"] if s >= 80 else self.c["warn"] if s >= 50 else self.c["fail"]

    # -- header/footer
    def header_footer(self, section, host, title):
        section.different_first_page_header_footer = False
        hp = section.header.paragraphs[0]
        hp.text = ""
        self.runs(hp, host, size=8.5, bold=True, color=self.c["dark"])
        hp.add_run("\t\t")
        self.runs(hp, title, size=8.5, color=self.c["muted"])
        para_border_bottom(hp, self.c["primary"], 8)
        fp = section.footer.paragraphs[0]
        fp.text = ""
        self.runs(fp, self.b["footer_credit"], size=8, color=self.c["muted"])
        fp.add_run("\t\t")
        r = add_field(fp, "PAGE")
        r.font.size = Pt(8)


# ------------------------------------------------------------------ build
def build(findings, rep, brand, out_docx):
    R = Report(brand)
    c = brand["colors"]
    sc = findings.get("scores") or {}
    host = findings["host"]
    mode = "Auditoria completa" if findings.get("mode") == "full" else "Auditoria rápida"
    date = rep.get("date") or findings["audited_at"][:10]
    F = findings["findings"]

    # ---------- CAPA (seção própria, sem cabecalho)
    bar = R.doc.add_table(rows=1, cols=1)
    table_borders(bar, c["primary"], 0, inside=False)
    shade(bar.rows[0].cells[0], c["primary"])
    R.cell_text(bar.rows[0].cells[0], " ", size=4)
    set_col_widths(bar, [R.width_cm])
    R.p(before=70)
    R.p(brand["agency"].upper(), size=10, bold=True, color=c["primary"], after=4)
    R.p(rep.get("client_name") or host, size=32, bold=True, color=c["dark"], after=2)
    if rep.get("client_name"):
        R.p(host, size=13, color=c["muted"], after=2)
    R.p("Auditoria de Visibilidade em Busca: SEO · GEO · AEO", size=15, color=c["text"], after=2)
    R.p(f"{mode} · {date}", size=10, color=c["muted"], after=28)

    dims = [d for d in ("SEO", "GEO", "AEO", "VIS") if d in sc and sc[d].get("score") is not None]
    cards = R.doc.add_table(rows=1, cols=len(dims) + 1)
    table_borders(cards, "FFFFFF", 0, inside=False)
    allcards = [("ÍNDICE GERAL", sc.get("OVERALL", {}))] + [(DIM_NAME[d].upper(), sc[d]) for d in dims]
    for i, (label, s) in enumerate(allcards):
        cell = cards.rows[0].cells[i]
        shade(cell, c["dark"] if i == 0 else R.score_color(s.get("score")))
        cell_margins(cell, 220, 220, 80, 80)
        R.cell_text(cell, label, bold=True, color="FFFFFF", size=8, align="center")
        p2 = cell.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        R.runs(p2, str(s.get("score", "-")), size=30, bold=True, color="FFFFFF")
        p3 = cell.add_paragraph()
        p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        conf = f" · conf. {s['confidence']}%" if "confidence" in s else ""
        R.runs(p3, f"{s.get('band', '')}{conf}", size=7.5, italic=True, color="FFFFFF")
    set_col_widths(cards, [R.width_cm / len(allcards)] * len(allcards))
    R.p(before=90)
    R.p(f"Preparado por {brand['author']} · {brand['agency']}", size=9, color=c["muted"], after=0)
    R.p(brand["methodology_name"], size=8.5, italic=True, color=c["muted"])

    sec = R.doc.add_section(WD_SECTION.NEW_PAGE)
    sec.header.is_linked_to_previous = False
    sec.footer.is_linked_to_previous = False
    R.header_footer(sec, host, "Auditoria SEO · GEO · AEO")
    first = R.doc.sections[0]
    first.different_first_page_header_footer = True

    # ---------- 1. RESUMO EXECUTIVO
    R.doc.add_heading("Resumo executivo", 1)
    R.callout(rep.get("executive_summary", ""))
    rows = []
    for d in ("SEO", "GEO", "AEO", "VIS"):
        if d not in sc:
            continue
        s = sc[d]
        rows.append([DIM_NAME[d], (("pass" if (s["score"] or 0) >= 80 else "warn" if (s["score"] or 0) >= 50 else "fail") if s["score"] is not None else "na",
                                   f"{s['score']}/100" if s["score"] is not None else "sem dados"),
                     s["band"], f"{s.get('confidence', 0)}%", (rep.get("dimension_takeaways") or {}).get(d, "")])
    R.table(["Dimensão", "Nota", "Faixa", "Confiança", "Leitura"], rows, [3.2, 2.2, 2.6, 2.0, 7.0], status_col=1,
            status_map={"pass": c["pass"], "warn": c["warn"], "fail": c["fail"], "na": c["na"]})
    chart = pillar_chart(F, brand, os.path.splitext(out_docx)[0] + "-pilares.png")
    if chart:
        R.doc.add_picture(chart, width=Cm(R.width_cm))
        R.p("Nota por pilar (0 a 100). Pilares sem dados não aparecem.", size=8.5, italic=True, color=c["muted"])
    if rep.get("top_priorities"):
        R.doc.add_heading("As 3 prioridades", 2)
        for i, t in enumerate(rep["top_priorities"][:3], 1):
            para = R.p(after=4)
            R.runs(para, f"{i}. ", bold=True, color=c["primary"])
            R.runs(para, t)
    if rep.get("biggest_strength"):
        R.doc.add_heading("Maior força", 2)
        R.p(rep["biggest_strength"])

    # ---------- 2. CONTEXTO E MÉTODO
    R.doc.add_heading("Contexto e método", 1)
    ctx = rep.get("context") or {}
    ctx_rows = [[k, v] for k, v in (("Negócio", ctx.get("business")), ("Público-alvo (ICP)", ctx.get("icp")),
                                    ("Mercado/idioma", ctx.get("market")), ("Objetivo da auditoria", ctx.get("goal")),
                                    ("Concorrentes de referência", ", ".join(ctx.get("competitors", [])) if ctx.get("competitors") else None),
                                    ("Fontes de dados usadas", ", ".join(rep.get("data_sources", [])) or None),
                                    ("Páginas analisadas", str(len([p for p in findings["pages_audited"] if p.get("status") == 200]))))
               if v]
    R.table(["Item", "Detalhe"], ctx_rows, [4.5, 12.5])
    R.p("Como ler as notas", bold=True, color=c["dark"], after=2).paragraph_format.keep_with_next = True
    R.p("Cada dimensão recebe nota de 0 a 100, calculada a partir de checks ponderados (OK = 1, Atenção = 0,5, Falha = 0). "
        "A **confiança** mostra quanto do peso total foi de fato avaliado: notas com confiança baixa dependem de dados que "
        "não estávam disponíveis. Cada check traz o nível de evidência que o sustenta: **S** (teste controlado ou documentação "
        "oficial), **C** (correlação em grandes bases), **A** (prática de mercado). Itens sem evidência de impacto, como llms.txt, "
        "aparecem como informativos e não pontuam.", size=9.5)

    # ---------- 3. RECOMENDAÇÕES
    recs = rep.get("recommendations", [])
    if recs:
        R.doc.add_heading("Prioridades e recomendações", 1)
        R.p("Ordenadas por impacto no negócio e esforço. Comece pelas críticas e pelos ganhos rápidos.", size=9.5, color=c["muted"])
        pm = {"critical": c["critical"], "high": c["high"], "medium": c["medium"], "quickwin": c["quickwin"]}
        label = {"critical": "Crítica", "high": "Alta", "medium": "Média", "quickwin": "Ganho rápido"}
        rows = []
        for r in recs:
            k = PRIO_KEY.get(norm(r.get("priority", "")), "medium")
            issue = f"**{r.get('issue', '')}**" + (f"\n{r['how']}" if r.get("how") else "")
            rows.append([(k, label[k]), issue, r.get("dimension", ""), r.get("effort", ""), r.get("impact", ""), r.get("owner", "")])
        t = R.table(["Prioridade", "O que fazer", "Dim.", "Esforço", "Impacto", "Responsável"], [], [2.2, 7.3, 1.2, 1.7, 1.7, 2.9])
        # linhas com quebra de parágrafo no campo "O que fazer"
        for row in rows:
            r = t.add_row()
            keep_row_together(r)
            for i, val in enumerate(row):
                cell = r.cells[i]
                cell_margins(cell)
                if i == 0:
                    shade(cell, pm[val[0]])
                    R.cell_text(cell, val[1], bold=True, color="FFFFFF", size=8.5, align="center")
                elif i == 1:
                    head, _, body = val.partition("\n")
                    R.cell_text(cell, head, size=9.5)
                    if body:
                        pp = cell.add_paragraph()
                        pp.paragraph_format.space_after = Pt(0)
                        R.runs(pp, body, size=8.5, color=c["muted"])
                else:
                    R.cell_text(cell, val, size=9)
        set_col_widths(t, [2.2, 7.3, 1.2, 1.7, 1.7, 2.9])

    plan = rep.get("action_plan") or {}
    if plan:
        R.doc.add_heading("Plano de 30, 60 e 90 dias", 2)
        cols = [("30", "Primeiros 30 dias"), ("60", "Ate 60 dias"), ("90", "Ate 90 dias")]
        t = R.doc.add_table(rows=2, cols=3)
        table_borders(t, c["border"])
        for i, (k, title) in enumerate(cols):
            hc = t.rows[0].cells[i]
            shade(hc, c["dark"])
            cell_margins(hc)
            R.cell_text(hc, title, bold=True, color="FFFFFF", size=9.5)
            bc = t.rows[1].cells[i]
            cell_margins(bc, 120, 120, 120, 120)
            bc.text = ""
            for j, item in enumerate(plan.get(k, [])):
                pp = bc.paragraphs[0] if j == 0 else bc.add_paragraph()
                pp.paragraph_format.space_after = Pt(4)
                R.runs(pp, "• " + item, size=9)
        set_col_widths(t, [R.width_cm / 3] * 3)
        R.p(after=4)

    # ---------- 4. VISIBILIDADE MEDIDA
    vis = rep.get("visibility") or {}
    if vis:
        R.doc.add_heading("Visibilidade medida", 1)
        R.p(DIM_DESC["VIS"], size=9.5, color=c["muted"])
        if vis.get("summary"):
            R.callout(vis["summary"], fill=c["light_bg"], border=c["border"])
        if vis.get("ai_prompts"):
            R.doc.add_heading("Teste de prompts em motores de IA", 2)
            R.p(vis.get("ai_method", "Cada prompt foi executado mais de uma vez por motor; reportamos a taxa de menção, não uma posição única."), size=9, color=c["muted"])
            rows = [[x.get("prompt", ""), x.get("engine", ""), str(x.get("runs", "")), x.get("mentioned", ""), x.get("cited", ""),
                     ", ".join(x.get("competitors", [])) if isinstance(x.get("competitors"), list) else x.get("competitors", "")]
                    for x in vis["ai_prompts"]]
            R.table(["Prompt", "Motor", "Rodadas", "Menção", "Citação (URL)", "Quem aparece"], rows, [5.4, 2.0, 1.5, 1.8, 2.3, 4.0])
        for key, title in (("semrush", "Dados do Semrush"), ("serp", "Dados de busca")):
            if not vis.get(key):
                continue
            R.doc.add_heading(title, 2)
            sm = vis[key]
            if sm.get("highlights"):
                for h in sm["highlights"]:
                    R.bullet(h)
            if sm.get("table"):
                R.table(sm["table"]["header"], sm["table"]["rows"], sm["table"].get("widths") or [R.width_cm / len(sm["table"]["header"])] * len(sm["table"]["header"]))
        for extra in vis.get("extra_tables", []):
            R.doc.add_heading(extra["title"], 2)
            R.table(extra["header"], extra["rows"], extra.get("widths") or [R.width_cm / len(extra["header"])] * len(extra["header"]))

    # ---------- 5. ANÁLISE POR DIMENSÃO
    smap = {"pass": c["pass"], "warn": c["warn"], "fail": c["fail"], "na": c["na"], "unknown": c["na"]}
    for d in ("SEO", "GEO", "AEO"):
        items = [f for f in F if f["dim"] == d]
        if not items:
            continue
        R.page_break()
        s = sc.get(d, {})
        R.doc.add_heading(f"Análise {DIM_NAME[d]}", 1)
        para = R.p(after=2)
        R.runs(para, f"Nota {s.get('score', '-')}/100 · {s.get('band', '')} · confiança {s.get('confidence', 0)}%", bold=True,
               color=R.score_color(s.get("score")))
        R.p(DIM_DESC[d], size=9.5, color=c["muted"])
        if (rep.get("dimension_narratives") or {}).get(d):
            R.p(rep["dimension_narratives"][d])
        for pillar in dict.fromkeys(f["pillar"] for f in items):
            R.doc.add_heading(pillar, 2)
            rows = []
            for f in [x for x in items if x["pillar"] == pillar]:
                ev = f.get("evidence") or "Não avaliado nesta auditoria."
                if f.get("pages") and f["status"] in ("warn", "fail"):
                    ev += " Ex.: " + ", ".join(re.sub(r"^https?://[^/]+", "", u) or "/" for u in f["pages"][:3])
                fix = f.get("fix") if f["status"] in ("warn", "fail") else ""
                lvl = f.get("evidence_level")
                rows.append([f"{f['name']} ({lvl})" if lvl else f["name"], (f["status"], STATUS_PT[f["status"]]), ev, fix])
            R.table(["Check", "Status", "Evidência encontrada", "Como corrigir"], rows, [4.2, 1.9, 6.0, 4.9], status_col=1, status_map=smap)

    # ---------- 6. O QUE FUNCIONA
    if rep.get("strengths"):
        R.doc.add_heading("O que já está funcionando", 1)
        rows = [[x.get("title", ""), x.get("evidence", "")] for x in rep["strengths"]]
        t = R.table(["Força", "Evidência"], rows, [5.0, 12.0], zebra=False, header_color=c["pass"])

    # ---------- 7. PÁGINAS
    R.doc.add_heading("Páginas auditadas", 1)
    rows = [[re.sub(r"^https?://[^/]+", "", p["url"]) or "/", p.get("type", ""), str(p.get("status")), str(p.get("words") or ""),
             (p.get("title") or "")[:70]] for p in findings["pages_audited"]]
    R.table(["URL", "Tipo", "Status", "Palavras", "Title"], rows, [5.5, 2.2, 1.4, 1.6, 6.3])

    # ---------- 8. LIMITES
    gaps = rep.get("limitations") or []
    unknown = [f["name"] for f in F if f["status"] == "unknown" and f["weight"] > 0]
    if gaps or unknown:
        R.doc.add_heading("Limitações e dados para a próxima rodada", 1)
        for g in gaps:
            R.bullet(g)
        if unknown:
            R.bullet("Checks não avaliados nesta rodada (reduzem a confiança): " + "; ".join(unknown) + ".")

    # ---------- 9. GLOSSÁRIO
    if findings.get("mode") == "full" or rep.get("include_glossary"):
        R.doc.add_heading("Glossário", 1)
        for term, desc in (
                ("SEO", "Search Engine Optimization: otimização para ranquear nos buscadores tradicionais (Google, Bing)."),
                ("GEO", "Generative Engine Optimization: otimização para ser recuperado e citado por motores de resposta generativa como ChatGPT, Perplexity, Gemini, Claude e AI Overviews."),
                ("AEO", "Answer Engine Optimization: estruturar respostas para snippets, People Also Ask, AI Overviews e voz."),
                ("AI Overviews / AI Mode", "Respostas geradas por IA no topo da Busca Google e o modo de conversa da Busca."),
                ("Query fan-out", "Técnica em que o motor de IA divide a pergunta em várias subconsultas e junta as fontes de cada uma."),
                ("E-E-A-T", "Experiência, Especialidade, Autoridade e Confiabilidade: critérios de qualidade do Google."),
                ("Taxa de menção", "Percentual de respostas de IA, em várias rodadas, em que a marca aparece."),
                ("Share of voice", "Menções da marca divididas pelo total de menções da marca e dos concorrentes monitorados.")):
            para = R.p(after=3)
            R.runs(para, term + ": ", bold=True, color=c["dark"])
            R.runs(para, desc)

    R.doc.core_properties.author = brand["author"]
    R.doc.core_properties.title = f"Auditoria SEO GEO AEO - {host}"
    R.doc.save(out_docx)


def pillar_scores(F):
    acc = {}
    for f in F:
        if f["weight"] <= 0 or f["status"] not in ("pass", "warn", "fail"):
            continue
        k = (f["dim"], f["pillar"])
        n, d = acc.get(k, (0.0, 0.0))
        acc[k] = (n + f["weight"] * {"pass": 1, "warn": 0.5, "fail": 0}[f["status"]], d + f["weight"])
    return [(dim, pil, round(100 * n / d)) for (dim, pil), (n, d) in acc.items() if d]


def pillar_chart(F, brand, path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None
    data = pillar_scores(F)
    if not data:
        return None
    c = brand["colors"]
    order = {"SEO": 0, "GEO": 1, "AEO": 2, "VIS": 3}
    data.sort(key=lambda x: (order.get(x[0], 9), -x[2]))
    labels = [f"{d} · {p}" for d, p, _ in data][::-1]
    vals = [v for _, _, v in data][::-1]
    cols = ["#" + (c["pass"] if v >= 80 else c["warn"] if v >= 50 else c["fail"]) for v in vals]
    fig, ax = plt.subplots(figsize=(8, 0.38 * len(vals) + 0.6), dpi=200)
    ax.barh(labels, vals, color=cols, height=0.62)
    for i, v in enumerate(vals):
        ax.text(v + 1.2, i, str(v), va="center", fontsize=8, color="#" + c["text"])
    ax.set_xlim(0, 108)
    ax.set_xticks([0, 50, 80, 100])
    ax.tick_params(axis="both", labelsize=8, colors="#" + c["muted"])
    for sp in ("top", "right", "left"):
        ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_color("#" + c["border"])
    ax.axvline(80, color="#" + c["border"], lw=0.8, ls="--", zorder=0)
    ax.axvline(50, color="#" + c["border"], lw=0.8, ls="--", zorder=0)
    plt.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def build_onepager(findings, rep, brand, out_docx):
    """Diagnóstico de 1 página: notas, o que encontramos, problemas principais e CTA. Respeita tema claro/escuro."""
    R = Report(brand)
    c = brand["colors"]
    dark = R.dark
    hfont = brand.get("heading_font") or brand.get("font", "Arial")
    panel, panel2 = c.get("panel", c["light_bg"]), c.get("panel2", c["light_bg"])
    eyebrow_c = c.get("eyebrow", c["primary"])
    sc = findings.get("scores") or {}
    host = findings["host"]
    date = rep.get("date") or findings["audited_at"][:10]
    F = findings["findings"]
    sec = R.doc.sections[0]
    sec.top_margin, sec.bottom_margin = Cm(1.3), Cm(1.4)
    sec.footer_distance = Cm(0.6)

    def eyebrow(text, before=6, after=3, align=None):
        para = R.p(before=before, after=after, align=align)
        r = para.add_run(text.upper())
        r.bold = True
        r.font.size = Pt(7.5)
        r.font.color.rgb = rgb(eyebrow_c)
        letter_spacing(r, 30)
        return para

    def title(text, size, color=None, after=0):
        para = R.p(after=after)
        r = para.add_run(text)
        r.bold = True
        r.font.size = Pt(size)
        r.font.name = hfont
        r._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:hAnsi"), hfont)
        r.font.color.rgb = rgb(color or c["text"])
        return para

    # cabeçalho: logo + rótulo
    logo = asset_path(brand, brand.get("logo"))
    head = R.doc.add_table(rows=1, cols=2)
    table_borders(head, c.get("page_bg", "FFFFFF"), 0, inside=False)
    lc, rc = head.rows[0].cells
    lc.text = ""
    if logo:
        lc.paragraphs[0].add_run().add_picture(logo, width=Cm(brand.get("logo_width_cm", 4.6)))
    else:
        R.runs(lc.paragraphs[0], brand["agency"], size=14, bold=True, color=c["primary"])
    rc.text = ""
    rp = rc.paragraphs[0]
    rp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = rp.add_run("DIAGNÓSTICO DE VISIBILIDADE EM BUSCA")
    r.bold, r.font.size = True, Pt(7.5)
    r.font.color.rgb = rgb(eyebrow_c)
    letter_spacing(r, 30)
    rp2 = rc.add_paragraph()
    rp2.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    R.runs(rp2, f"SEO · GEO · AEO · {date}", size=8, color=c["muted"])
    rc.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    set_col_widths(head, [8.5, 8.5])
    if not dark:
        rule = R.p(after=0)
        para_border_bottom(rule, c["primary"], 12)

    title(rep.get("client_name") or host, 24, after=0).paragraph_format.space_before = Pt(10)
    R.p(f"{host} · auditoria de como o site aparece no Google e nas IAs generativas", size=9, color=c["muted"], after=10)

    # cartões de nota
    dims = [d for d in ("SEO", "GEO", "AEO", "VIS") if d in sc and sc[d].get("score") is not None]
    short_dim = {"VIS": "Visibilidade"}
    allc = [("Índice geral", sc.get("OVERALL", {}))] + [(short_dim.get(d, DIM_NAME[d]), sc[d]) for d in dims]
    cards = R.doc.add_table(rows=1, cols=len(allc))
    table_borders(cards, c.get("page_bg", "FFFFFF") if dark else "FFFFFF", 12 if dark else 0, inside=True)
    for i, (label, s_) in enumerate(allc):
        cell = cards.rows[0].cells[i]
        cell_margins(cell, 140, 140, 80, 80)
        num_color = "FFFFFF"
        if dark:
            shade(cell, c["deep"] if i == 0 else panel2)
            if i:
                num_color = R.score_color(s_.get("score"))
        else:
            shade(cell, c["dark"] if i == 0 else R.score_color(s_.get("score")))
        cell.text = ""
        p1 = cell.paragraphs[0]
        p1.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rr = p1.add_run(label.upper())
        rr.bold, rr.font.size = True, Pt(7)
        rr.font.color.rgb = rgb(eyebrow_c if dark else "FFFFFF")
        letter_spacing(rr, 20)
        p2 = cell.add_paragraph()
        p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p2.paragraph_format.space_after = Pt(0)
        rn = p2.add_run(str(s_.get("score", "-")))
        rn.bold, rn.font.size, rn.font.name = True, Pt(24), hfont
        rn.font.color.rgb = rgb(num_color)
        p3 = cell.add_paragraph()
        p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
        R.runs(p3, s_.get("band", ""), size=7, color=c["muted"] if dark else "FFFFFF")
    set_col_widths(cards, [R.width_cm / len(allc)] * len(allc))
    R.p(after=2)

    if rep.get("executive_summary"):
        R.p(rep["executive_summary"].split("\n\n")[0], size=10, after=4)

    eyebrow("O que mais pesa hoje", before=8)
    for i, t in enumerate(rep.get("top_priorities", [])[:3], 1):
        para = R.p(after=3)
        R.runs(para, f"{i:02d}  ", bold=True, color=c["primary"], size=10)
        R.runs(para, t, size=10)

    fails = sorted([f for f in F if f["status"] in ("fail", "warn") and f["weight"] > 0],
                   key=lambda f: (f["status"] != "fail", -f["weight"]))[:5]
    if fails:
        eyebrow("Sinais encontrados", before=10)
        smap = {"pass": c["pass"], "warn": c["warn"], "fail": c["fail"], "na": c["na"]}
        t = R.doc.add_table(rows=1, cols=3)
        table_borders(t, c["border"], 4)
        for j, h in enumerate(["Status", "Sinal", "O que vimos"]):
            hc = t.rows[0].cells[j]
            shade(hc, c["deep"] if dark else c["dark"])
            cell_margins(hc)
            R.cell_text(hc, h, bold=True, color="FFFFFF", size=8.5)
        for k, f in enumerate(fails):
            row = t.add_row()
            keep_row_together(row)
            cells = row.cells
            for cc in cells:
                cell_margins(cc)
            shade(cells[0], smap[f["status"]])
            R.cell_text(cells[0], STATUS_PT[f["status"]], bold=True, color="FFFFFF", size=8, align="center")
            for cc in cells[1:]:
                shade(cc, panel if (dark and k % 2 == 0) else panel2 if dark else ("FFFFFF" if k % 2 == 0 else c["light_bg"]))
            R.cell_text(cells[1], f["name"], size=8.5, bold=True)
            R.cell_text(cells[2], (f.get("evidence") or "")[:170], size=8.5, color=c["muted"] if dark else None)
        set_col_widths(t, [2.0, 5.6, 9.4])
        R.p(after=2)

    if rep.get("biggest_strength"):
        para = R.p(after=6, before=4)
        R.runs(para, "Ponto forte: ", bold=True, color=c["pass"] if not dark else c["primary_soft"] if "primary_soft" in c else c["pass"])
        R.runs(para, rep["biggest_strength"], size=10)

    cta_title = rep.get("cta_title") or brand.get("cta_title")
    if cta_title:
        box = R.doc.add_table(rows=1, cols=1)
        table_borders(box, c["primary"], 8 if dark else 12, inside=False)
        bc = box.rows[0].cells[0]
        shade(bc, panel2 if dark else "FFF4EF")
        cell_margins(bc, 180, 180, 240, 240)
        bc.text = ""
        pt_ = bc.paragraphs[0]
        rt = pt_.add_run(cta_title)
        rt.bold, rt.font.size, rt.font.name = True, Pt(14), hfont
        rt.font.color.rgb = rgb(c["text"] if dark else c["dark"])
        pb = bc.add_paragraph()
        R.runs(pb, rep.get("cta_text") or brand.get("cta_text", ""), size=9.5, color=c["muted"] if dark else None)
        if brand.get("cta_url"):
            pu = bc.add_paragraph()
            pu.paragraph_format.space_before = Pt(4)
            ru = pu.add_run("  " + brand["cta_url"] + "  →  ")
            ru.bold, ru.font.size = True, Pt(10)
            ru.font.color.rgb = rgb(c["primary"])
        set_col_widths(box, [R.width_cm])
    R.p(f"Metodologia: {brand['methodology_name']}. Notas de 0 a 100 a partir de "
        f"{len([f for f in F if f['weight'] > 0])} sinais ponderados com nível de evidência.",
        size=7, color=c["muted"], before=6, after=0)

    producer_footer(R, sec, brand)
    R.doc.core_properties.author = brand["author"]
    R.doc.save(out_docx)


def install_fonts():
    """Instala as fontes da marca (assets/fonts, licença OFL) para o PDF sair com a tipografia certa."""
    src = os.path.join(HERE, "..", "assets", "fonts")
    if not os.path.isdir(src):
        return
    dst = os.path.expanduser("~/.local/share/fonts/carratu-skill")
    try:
        os.makedirs(dst, exist_ok=True)
        new = False
        for f in os.listdir(src):
            if f.lower().endswith((".ttf", ".otf")) and not os.path.exists(os.path.join(dst, f)):
                shutil.copy(os.path.join(src, f), dst)
                new = True
        if new and shutil.which("fc-cache"):
            subprocess.run(["fc-cache", "-f", dst], capture_output=True, timeout=60)
    except Exception as e:
        print(f"Aviso: não foi possível instalar as fontes ({e})", file=sys.stderr)


def to_pdf(docx_path, out_dir):
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    install_fonts()
    try:
        subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, docx_path],
                       check=True, capture_output=True, timeout=180)
    except Exception as e:
        print(f"PDF falhou: {e}", file=sys.stderr)
        return None
    pdf = os.path.splitext(docx_path)[0] + ".pdf"
    return pdf if os.path.exists(pdf) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("findings_json")
    ap.add_argument("report_json")
    ap.add_argument("--out", default="outputs")
    ap.add_argument("--brand", default=os.path.join(HERE, "..", "assets", "brand.json"))
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--format", choices=["full", "onepager", "both"], default="full",
                    help="full = relatório completo; onepager = diagnóstico de 1 página com CTA; both = os dois")
    ap.add_argument("--onepager-brand", default=None,
                    help="identidade do diagnóstico; padrão: campo onepager_brand do brand.json")
    a = ap.parse_args()
    findings = json.load(open(a.findings_json, encoding="utf-8"))
    rep = json.load(open(a.report_json, encoding="utf-8"))
    brand = json.load(open(a.brand, encoding="utf-8"))
    brand["_dir"] = os.path.dirname(os.path.abspath(a.brand))
    one_brand = brand
    ob = a.onepager_brand or brand.get("onepager_brand")
    if ob:
        ob_path = ob if os.path.isabs(ob) or os.path.exists(ob) else os.path.join(brand["_dir"], ob)
        one_brand = json.load(open(ob_path, encoding="utf-8"))
        one_brand["_dir"] = os.path.dirname(os.path.abspath(ob_path))
    vis_path = os.path.join(os.path.dirname(os.path.abspath(a.findings_json)), "visibility.json")
    if not rep.get("visibility") and os.path.exists(vis_path):
        rep["visibility"] = json.load(open(vis_path, encoding="utf-8"))
    os.makedirs(a.out, exist_ok=True)
    date = (rep.get("date") or findings["audited_at"][:10])
    slug = re.sub(r"[^a-z0-9]+", "-", findings["host"].lower()).strip("-")
    out = {}
    if a.format in ("full", "both"):
        docx_path = os.path.abspath(os.path.join(a.out, f"auditoria-seo-geo-aeo-{slug}-{date}.docx"))
        build(findings, rep, brand, docx_path)
        png = os.path.splitext(docx_path)[0] + "-pilares.png"
        out["docx"], out["pdf"] = docx_path, None if a.no_pdf else to_pdf(docx_path, os.path.abspath(a.out))
        if os.path.exists(png):
            os.remove(png)
    if a.format in ("onepager", "both"):
        one = os.path.abspath(os.path.join(a.out, f"diagnostico-{slug}-{date}.docx"))
        build_onepager(findings, rep, one_brand, one)
        out["onepager_docx"], out["onepager_pdf"] = one, None if a.no_pdf else to_pdf(one, os.path.abspath(a.out))
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
