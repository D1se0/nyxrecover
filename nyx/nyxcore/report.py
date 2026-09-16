"""Self-contained HTML report generator (no external JS/CSS deps)."""
from __future__ import annotations

import html
import json
import time
from pathlib import Path

_CSS = """
:root{--bg:#0a0e1a;--panel:#111827;--panel2:#0d1321;--line:#1f2a44;--fg:#e5e7eb;
--mut:#94a3b8;--acc:#22d3ee;--acc2:#a78bfa;--ok:#34d399;--warn:#fbbf24;--bad:#f87171}
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',system-ui,sans-serif;
background:radial-gradient(1200px 600px at 20% -10%,#142033 0%,#0a0e1a 60%);color:var(--fg)}
.wrap{max-width:1080px;margin:0 auto;padding:32px 20px}
h1{font-size:26px;margin:0 0 4px}.sub{color:var(--mut);margin:0 0 24px}
.brand{display:flex;align-items:center;gap:12px;margin-bottom:18px}
.logo{width:40px;height:40px;border-radius:10px;display:grid;place-items:center;
background:linear-gradient(135deg,#22d3ee33,#a78bfa33);border:1px solid var(--line);font-size:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px;margin:18px 0}
.card{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line);
border-radius:14px;padding:16px}
.k{color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.08em}
.v{font-size:20px;font-weight:600;margin-top:4px}
table{width:100%;border-collapse:collapse;margin:10px 0;font-size:13px}
th{color:var(--mut);text-align:left;font-weight:600;border-bottom:1px solid var(--line);
padding:8px 6px;text-transform:uppercase;font-size:11px;letter-spacing:.06em}
td{padding:7px 6px;border-bottom:1px solid #16203a;word-break:break-all}
tr:hover td{background:#131c33}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;border:1px solid}
.b-ok{color:var(--ok);border-color:var(--ok)} .b-warn{color:var(--warn);border-color:var(--warn)}
.b-bad{color:var(--bad);border-color:var(--bad)} .b-info{color:var(--acc);border-color:var(--acc)}
footer{color:var(--mut);font-size:12px;margin-top:30px;border-top:1px solid var(--line);padding-top:14px}
code{background:#0b1120;border:1px solid var(--line);padding:1px 6px;border-radius:6px;font-size:12px}
"""


def _badge(ok_text, warn_text=None, cls="b-ok"):
    return f'<span class="badge {cls}">{html.escape(ok_text)}</span>'


def _table(headers, rows):
    if not rows:
        return "<p style='color:#94a3b8'>Sin datos.</p>"
    th = "".join(f"<th>{html.escape(str(h))}</th>" for h in headers)
    trs = []
    for r in rows:
        tds = "".join(f"<td>{c if isinstance(c, str) and c.startswith('<') else html.escape(str(c))}</td>"
                      for c in r)
        trs.append(f"<tr>{tds}</tr>")
    return f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"


def _kpi(items):
    cards = "".join(
        f"<div class='card'><div class='k'>{html.escape(k)}</div><div class='v'>{html.escape(str(v))}</div></div>"
        for k, v in items)
    return f"<div class='grid'>{cards}</div>"


def generate(data: dict, out_path: str) -> Path:
    """data keys: title, subtitle, sections=[{title, kpis, table, note}]"""
    sections_html = []
    for sec in data.get("sections", []):
        s = f"<h2>{html.escape(sec.get('title', ''))}</h2>"
        if sec.get("kpis"):
            s += _kpi(sec["kpis"])
        if sec.get("note"):
            s += f"<p class='sub'>{html.escape(sec['note'])}</p>"
        if sec.get("table"):
            s += _table(sec["table"]["headers"], sec["table"]["rows"])
        sections_html.append(s)
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    doc = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>{html.escape(data.get('title', 'NyxRecover — Informe'))}</title>
<style>{_CSS}</style></head><body><div class='wrap'>
<div class='brand'><div class='logo'>🜲</div>
<div><h1>{html.escape(data.get('title', 'Informe NyxRecover'))}</h1>
<p class='sub'>{html.escape(data.get('subtitle', ''))}</p></div></div>
{''.join(sections_html)}
<footer>Generado por NyxRecover v1.0.0 — {now} — Cadena de custodia: hash del manifiesto incluido en cada sesión.</footer>
</div></body></html>"""
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(doc, encoding="utf-8")
    return p
