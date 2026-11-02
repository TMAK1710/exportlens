"""Offline, escaped HTML reports. No network requests or JavaScript required."""
import html
import json
from pathlib import Path


def _esc(value):
    return html.escape(str(value), quote=True)


def _value(value):
    if value is None:
        return "Not captured"
    if isinstance(value, list):
        if not value:
            return "None"
        if all(isinstance(v, (float, int)) for v in value):
            return " / ".join(f"{v:.4g}" for v in value)
        if all(isinstance(v, dict) for v in value):
            return f"{len(value)} hierarchy nodes"
        return ", ".join("(empty slot)" if v is None else str(v) for v in value)
    if isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdefABCDEF" for c in value):
        return value[:16] + "…" + value[-8:]
    return str(value)


def render_html(result):
    status = result["status"]
    title = {"pass": "Consistent within scope", "fail": "Differences detected", "review": "Review required"}[status]
    subtitle = {"pass": "The measured properties match across this FBX export and import.",
                "fail": "Follow the findings below to locate the changed properties.",
                "review": "Some evidence needs review before this capture can pass."}[status]
    labels = {"identity": "FBX identity", "dimensions": "Dimensions", "bones": "Bone hierarchy",
              "blend_shapes": "Shape channels", "materials": "Material slots", "mesh": "Mesh presence"}
    checks = []
    for check in result["checks"]:
        expected, actual = check.get("expected"), check.get("actual")
        raw = json.dumps({"blender": expected, "unity": actual}, ensure_ascii=False, indent=2)
        checks.append(f'''<article class="check"><div class="check-head"><span class="eyebrow">{_esc(labels.get(check['category'], check['category']))}</span><span class="badge {check['status']}">{check['status'].upper()}</span></div>
<h3>{_esc(check['subject'])}</h3><p class="muted">{_esc(check.get('detail', ''))}</p>
<div class="pair"><div><small>BLENDER</small><strong>{_esc(_value(expected))}</strong></div><div><small>UNITY</small><strong>{_esc(_value(actual))}</strong></div></div>
<details><summary>Inspect captured values</summary><pre>{_esc(raw)}</pre></details></article>''')
    findings = []
    for finding in result["findings"]:
        severity = finding["severity"]
        values = ""
        if finding.get("expected") is not None or finding.get("actual") is not None:
            values = f'<div class="finding-values"><span>Expected: {_esc(_value(finding.get("expected")))}</span><span>Actual: {_esc(_value(finding.get("actual")))}</span></div>'
        hint = f'<p class="hint">{_esc(finding["hint"])}</p>' if finding.get("hint") else ""
        findings.append(f'''<article class="finding {severity}"><div class="finding-top"><span class="badge {severity}">{severity.upper()}</span><code>{_esc(finding['code'])}</code><span class="muted">{_esc(finding['subject'])}</span></div><p>{_esc(finding['message'])}</p>{values}{hint}</article>''')
    if not findings:
        findings.append('<div class="empty">No differences found in the measured properties.</div>')
    source, target = result["source"], result["target"]
    summary = result["summary"]
    limitations = "".join(f"<li>{_esc(v)}</li>" for v in result["limitations"])
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="color-scheme" content="dark"><title>ExportLens — {_esc(title)}</title>
<style>
:root{{--bg:#10181c;--panel:#19242b;--line:#314047;--muted:#a6b8bf;--ink:#e9f2f2;--green:#8ce6c5;--red:#ffaca5;--amber:#f4d28b}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,-apple-system,'Segoe UI',sans-serif}}main{{max-width:1120px;margin:auto;padding:30px 36px 48px}}header{{display:flex;align-items:center;gap:18px;border-bottom:1px solid var(--line);padding-bottom:22px}}.logo{{font-size:24px;font-weight:750;letter-spacing:-1px}}.mark{{color:var(--green)}}.tag{{margin-left:auto;color:var(--muted);font-size:12px}}.eyebrow{{font-size:11px;letter-spacing:1.5px;text-transform:uppercase;color:var(--muted)}}.hero{{padding:32px 0 26px;display:flex;justify-content:space-between;gap:24px;align-items:center}}h1{{margin:6px 0;font-size:36px;letter-spacing:-1.1px;line-height:1.2}}.hero.pass h1{{color:var(--green)}}.hero.fail h1{{color:var(--red)}}.hero.review h1{{color:var(--amber)}}p{{margin:8px 0}}.muted{{color:var(--muted)}}.stats{{display:flex;gap:22px;text-align:center;flex-shrink:0}}.stats strong{{font-size:30px;display:block;line-height:1.2}}.stats small{{font-size:11px;color:var(--muted)}}.evidence{{display:grid;grid-template-columns:1fr 1fr;gap:1px;background:var(--line);border:1px solid var(--line);border-radius:10px;overflow:hidden}}.evidence>div{{background:var(--panel);padding:16px 20px}}.evidence strong{{display:block;font-size:16px;margin:2px 0;overflow-wrap:anywhere}}.section-head{{display:flex;align-items:baseline;gap:15px;margin:28px 0 12px}}h2{{font-size:19px;margin:0}}.section-head span{{font-size:12px;color:var(--muted)}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}.check{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px 18px;min-width:0}}.check-head{{display:flex;align-items:center;justify-content:space-between;gap:10px}}h3{{margin:5px 0 0;font-size:18px}}.check>.muted{{font-size:12px;min-height:20px}}.badge{{font-size:10px;font-weight:750;letter-spacing:.7px;border-radius:4px;padding:3px 7px;display:inline-block}}.pass{{color:var(--green)}}.badge.pass{{background:#243f38}}.badge.fail,.badge.error{{background:#472c2e;color:var(--red)}}.badge.review,.badge.warning{{background:#443c2c;color:var(--amber)}}.badge.info{{background:#2a3b4c;color:#b6d3ee}}.pair{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}}.pair small{{display:block;font-size:10px;color:var(--muted);letter-spacing:1px}}.pair strong{{display:block;font-size:13px;font-weight:550;overflow-wrap:anywhere}}details{{margin-top:12px;font-size:11px;color:var(--muted)}}summary{{cursor:pointer}}pre{{font:11px/1.5 ui-monospace,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}}.finding{{border:1px solid var(--line);border-left:3px solid #6f8491;border-radius:7px;background:var(--panel);padding:14px 18px;margin-bottom:10px}}.finding.error{{border-left-color:var(--red)}}.finding.warning{{border-left-color:var(--amber)}}.finding-top{{display:flex;gap:12px;align-items:center;flex-wrap:wrap;font-size:12px}}code{{font:11px ui-monospace,Consolas,monospace}}.finding-values{{display:flex;gap:24px;flex-wrap:wrap;font-size:12px;color:var(--muted);overflow-wrap:anywhere}}.hint{{font-size:12px;color:#c0d3d9;border-top:1px solid var(--line);padding-top:8px;margin-top:10px}}.empty{{padding:18px;border:1px solid var(--line);border-radius:8px;color:var(--green)}}.scope{{margin-top:28px;border-top:1px solid var(--line);padding-top:18px;color:var(--muted);font-size:12px}}.scope strong{{color:var(--ink)}}.scope ul{{padding-left:18px}}footer{{margin-top:20px;font-size:11px;color:var(--muted);display:flex;justify-content:space-between;gap:20px}}@media(max-width:750px){{main{{padding:20px}}.hero{{display:block}}.stats{{justify-content:flex-start;margin-top:22px}}h1{{font-size:30px}}.grid,.evidence{{grid-template-columns:1fr}}.tag{{display:none}}}}
</style></head><body><main>
<header><div class="logo"><span class="mark">◈</span> ExportLens</div><span class="eyebrow">Blender → Unity</span><span class="tag">LOCAL FBX AUDIT · v0.1</span></header>
<section class="hero {status}"><div><div class="eyebrow">Export consistency report</div><h1>{_esc(title)}</h1><p class="muted">{_esc(subtitle)}</p></div><div class="stats"><div><strong>{summary['errors']}</strong><small>ERRORS</small></div><div><strong>{summary['warnings']}</strong><small>REVIEW</small></div><div><strong>{summary['checks']}</strong><small>CHECKS</small></div></div></section>
<section class="evidence"><div><span class="eyebrow">Source · Blender {_esc(source['producer_version'])}</span><strong>{_esc(source['asset_name'])}</strong><span class="muted">{_esc(source['source_file'])}</span></div><div><span class="eyebrow">Imported · Unity {_esc(target['producer_version'])}</span><strong>{_esc(target['asset_name'])}</strong><span class="muted">{_esc(target['source_file'])}</span></div></section>
<div class="section-head"><h2>Measured properties</h2><span>Native units normalized to meters</span></div><section class="grid">{''.join(checks)}</section>
<div class="section-head"><h2>Findings</h2><span>{summary['errors']} errors · {summary['warnings']} warnings · {summary['info']} notes</span></div><section>{''.join(findings)}</section>
<aside class="scope"><strong>Scope of this report</strong><ul>{limitations}</ul>Dimension tolerance: {_esc(result['tolerances']['absolute_m'])} m + {_esc(result['tolerances']['relative'] * 100)}% per source axis. A pass applies only to the properties listed above.</aside>
<footer><span>ExportLens · Local files in, local evidence out.</span><span>Open source · No telemetry · Offline report</span></footer>
</main></body></html>'''


def write_report(result, output):
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (directory / "report.html").write_text(render_html(result), encoding="utf-8")
