#!/usr/bin/env python3
"""Registra o resultado de checks manuais ou de dados em findings.json.

Uso (um check):
  python3 set_check.py audit_data/findings.json geo.answer_first warn "Home abre com slogan, sem dizer o que o produto faz." --pages https://x.com/ https://x.com/produto

Uso (varios de uma vez, via arquivo JSON):
  python3 set_check.py audit_data/findings.json --batch checks.json
  checks.json = [{"id": "geo.passages", "status": "pass", "evidence": "...", "pages": ["..."], "source": "claude"}, ...]

status: pass | warn | fail | na | unknown
source: claude (leitura das paginas) | semrush | pagespeed | websearch | prompts | hubspot | gsc | user
"""
from __future__ import annotations

import argparse
import json
import sys

VALID = {"pass", "warn", "fail", "na", "unknown"}


def apply(data, item):
    if item["status"] not in VALID:
        raise SystemExit(f"status invalido para {item['id']}: {item['status']}")
    for f in data["findings"]:
        if f["id"] == item["id"]:
            f["status"] = item["status"]
            f["evidence"] = item.get("evidence", f.get("evidence", ""))
            if item.get("pages"):
                f["pages"] = item["pages"]
            f["source"] = item.get("source", "claude")
            return True
    raise SystemExit(f"check inexistente: {item['id']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("findings_json")
    ap.add_argument("check_id", nargs="?")
    ap.add_argument("status", nargs="?")
    ap.add_argument("evidence", nargs="?", default="")
    ap.add_argument("--pages", nargs="*", default=[])
    ap.add_argument("--source", default="claude")
    ap.add_argument("--batch")
    a = ap.parse_args()
    data = json.load(open(a.findings_json, encoding="utf-8"))
    if a.batch:
        items = json.load(open(a.batch, encoding="utf-8"))
    elif a.check_id and a.status:
        items = [{"id": a.check_id, "status": a.status, "evidence": a.evidence, "pages": a.pages, "source": a.source}]
    else:
        sys.exit("informe check_id e status, ou --batch")
    for it in items:
        apply(data, it)
    json.dump(data, open(a.findings_json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    left = [f["id"] for f in data["findings"] if f["status"] == "unknown"]
    print(json.dumps({"updated": [i["id"] for i in items], "still_unknown": left}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
