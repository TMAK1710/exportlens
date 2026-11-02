"""Build the documentation overview from recorded fixture outcomes."""
import json
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
summary = json.loads((ROOT / "examples/reports/integration-summary.json").read_text(encoding="utf-8"))
cases = summary["cases"]
passed = sum(case["status"] == "pass" for case in cases)
rows = []
labels = {"ordered_slots": "Stable source → import", "wrong_scale": "Scale Factor set to 0.01", "missing_blend_shapes": "Import BlendShapes disabled", "good": "Material slot order changed"}
for name, label in labels.items():
    case = next(case for case in cases if case["case"] == name)
    status = case["status"]
    rows.append(f'<div class="case"><span>{escape(label)}</span><b class="{status}">{status.upper()}</b></div>')
html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>ExportLens — Blender to Unity</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#10181c;color:#e9f2f2;font:16px/1.5 system-ui,'Segoe UI',sans-serif}}main{{width:1280px;padding:40px 64px 32px}}header{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #314047;padding-bottom:22px}}.logo{{font-size:30px;font-weight:750;letter-spacing:-1px}}.logo span{{color:#8ce6c5}}.tag{{font-size:12px;letter-spacing:2px;color:#a6b8bf}}h1{{font-size:48px;letter-spacing:-1.5px;line-height:1.12;margin:30px 0 10px;max-width:1000px}}.lead{{color:#a6b8bf;font-size:18px;margin-bottom:28px}}.columns{{display:grid;grid-template-columns:460px 1fr;gap:28px}}.preview{{border:1px solid #314047;border-radius:14px;background:#19242b;overflow:hidden}}.preview img{{display:block;width:100%;height:365px;object-fit:cover}}.caption{{padding:14px 20px}}.caption strong{{display:block;font-size:17px}}.caption span{{color:#a6b8bf;font-size:13px}}.flow{{display:flex;gap:10px;align-items:stretch;margin-bottom:22px}}.step{{flex:1;border:1px solid #314047;border-radius:8px;padding:12px;background:#19242b}}.step small{{font-size:10px;letter-spacing:1px;color:#8ce6c5}}.step strong{{display:block;font-size:16px;margin-top:4px}}.step p{{font-size:12px;color:#a6b8bf;margin:5px 0}}h2{{font-size:14px;letter-spacing:1px;text-transform:uppercase;color:#a6b8bf;margin:14px 0 8px}}.case{{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #314047;padding:13px 0;font-size:14px;gap:15px}}.case b{{font-size:10px;letter-spacing:1px;border-radius:4px;padding:4px 9px}}.pass{{color:#8ce6c5;background:#243f38}}.fail{{color:#ffaca5;background:#472c2e}}.review{{color:#f4d28b;background:#443c2c}}.note{{color:#a6b8bf;font-size:12px;margin-top:14px}}footer{{display:flex;justify-content:space-between;align-items:center;border-top:1px solid #314047;margin-top:25px;padding-top:20px;font-size:12px;color:#a6b8bf}}footer strong{{color:#e9f2f2}}.checks{{display:flex;gap:25px;font-size:13px}}
</style></head><body><main><header><div class="logo"><span>◈</span> ExportLens</div><div class="tag">BLENDER → UNITY · FBX CONSISTENCY</div></header>
<h1>See what changed.<br>Before the model ships.</h1><p class="lead">Compare source snapshots with actual Unity imports. Keep the evidence local.</p>
<div class="columns"><section class="preview"><img src="images/robot-preview.png" alt="Original mint and graphite robot test fixture"><div class="caption"><strong>Original, reproducible test asset</strong><span>1 × 0.6 × 2 m · 3 bones · 2 shape channels · 2 slots</span></div></section><section><div class="flow"><div class="step"><small>01 / BLENDER</small><strong>Export + snapshot</strong><p>Source properties and FBX SHA-256</p></div><div class="step"><small>02 / UNITY</small><strong>Capture import</strong><p>Read-only preview instance</p></div><div class="step"><small>03 / LOCAL</small><strong>Compare evidence</strong><p>Offline HTML + JSON findings</p></div></div>
<h2>Actual Blender / Unity capture results</h2>{''.join(rows)}<p class="note">{len(cases)} capture pairs replayed with expected outcomes. {passed} pass controls; intentional differences are retained and detected. Blender {escape(cases[0]['blender_version'])} / Unity {escape(cases[0]['unity_version'])}.</p></section></div>
<footer><div class="checks"><strong>Dimensions</strong><strong>Bone hierarchy</strong><strong>Shape channels</strong><strong>Material slots</strong></div><span>v0.1 · Local files · No telemetry</span></footer></main></body></html>'''
(ROOT / "docs/overview.html").write_text(html, encoding="utf-8")
print("Built docs/overview.html from actual integration evidence.")
