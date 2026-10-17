#!/usr/bin/env python3
"""Calcula notas (0-100) e confianca por dimensao a partir de findings.json.

Uso:
  python3 score.py audit_data/findings.json            # imprime e grava scores em findings.json
  python3 score.py audit_data/findings.json --check    # so valida se ainda ha checks pendentes

Regras:
  pass=1, warn=0.5, fail=0; 'na' sai do calculo; 'unknown' reduz a confianca.
  Nota = 100 * soma(peso*valor) / soma(peso avaliado).
  Confianca = peso avaliado / peso total aplicavel (exclui 'na').
  Indice geral = media ponderada SEO 35%, GEO 35%, AEO 30% (VIS e reportado a parte).
"""
from __future__ import annotations

import argparse
import json

VAL = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
OVERALL_WEIGHTS = {"SEO": 0.35, "GEO": 0.35, "AEO": 0.30}


def band(score):
    if score is None:
        return "Sem dados"
    return "Forte" if score >= 80 else "No caminho" if score >= 60 else "Precisa de atenção" if score >= 40 else "Crítico"


def compute(findings):
    dims = {}
    for f in findings:
        if f["weight"] <= 0 or f["status"] == "na":
            continue
        d = dims.setdefault(f["dim"], {"num": 0.0, "den": 0.0, "total": 0.0, "counts": {}})
        d["total"] += f["weight"]
        d["counts"][f["status"]] = d["counts"].get(f["status"], 0) + 1
        if f["status"] in VAL:
            d["num"] += f["weight"] * VAL[f["status"]]
            d["den"] += f["weight"]
    res = {}
    for k, d in dims.items():
        score = round(100 * d["num"] / d["den"]) if d["den"] else None
        conf = round(100 * d["den"] / d["total"]) if d["total"] else 0
        res[k] = {"score": score, "band": band(score), "confidence": conf, "counts": d["counts"]}
    parts = [(OVERALL_WEIGHTS[k], v["score"]) for k, v in res.items() if k in OVERALL_WEIGHTS and v["score"] is not None]
    overall = round(sum(w * s for w, s in parts) / sum(w for w, _ in parts)) if parts else None
    res["OVERALL"] = {"score": overall, "band": band(overall)}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("findings_json")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    data = json.load(open(a.findings_json, encoding="utf-8"))
    pending = [f["id"] for f in data["findings"] if f["status"] == "unknown" and f["type"] != "data"]
    no_evidence = [f["id"] for f in data["findings"] if f["status"] in VAL and not f.get("evidence")]
    if a.check:
        print(json.dumps({"pending_manual": pending, "missing_evidence": no_evidence}, ensure_ascii=False, indent=1))
        return
    data["scores"] = compute(data["findings"])
    json.dump(data, open(a.findings_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"scores": data["scores"], "pending_manual": pending, "missing_evidence": no_evidence},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
