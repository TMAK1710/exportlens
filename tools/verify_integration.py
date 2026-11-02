"""Assert expected outcomes against actual Blender/Unity fixture captures.

Run from a repository checkout (no third-party dependencies):
    python tools/verify_integration.py --fixtures examples/fixtures --captures examples/captures --output examples/reports
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exportlens.compare import compare
from exportlens.report import write_report


CASES = {
    "good": ("good", "review", {"MATERIAL_SLOT_NAMES_CHANGED"}),
    "cm_units": ("cm_units", "review", {"MATERIAL_SLOT_NAMES_CHANGED"}),
    "ordered_slots": ("ordered_slots", "pass", set()),
    "cm_ordered_slots": ("cm_ordered_slots", "pass", set()),
    "subset_selection": ("subset_selection", "pass", set()),
    "lost_shapes": ("lost_shapes", "fail", {"BLEND_SHAPE_MISSING", "MATERIAL_SLOT_NAMES_CHANGED"}),
    "reparented_bone": ("reparented_bone", "fail", {"BONE_PARENT_CHANGED", "MATERIAL_SLOT_NAMES_CHANGED"}),
    "changed_material": ("changed_material", "review", {"MATERIAL_SLOT_NAMES_CHANGED"}),
    "wrong_scale": ("ordered_slots", "fail", {"BOUNDS_SIZE_CHANGED"}),
    "missing_blend_shapes": ("ordered_slots", "fail", {"BLEND_SHAPE_MISSING"}),
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--captures", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = []
    for name, (source_name, expected_status, required_codes) in CASES.items():
        source = read(args.fixtures / (source_name + ".source.json"))
        target = read(args.captures / (name + ".unity.json"))
        result = compare(source, target)
        codes = {f["code"] for f in result["findings"]}
        # A negative example must fail for its intended reason, not an unrelated error.
        meaningful_codes = {f["code"] for f in result["findings"] if f["severity"] != "info"}
        if result["status"] != expected_status or meaningful_codes != required_codes:
            raise AssertionError(f"{name}: expected {expected_status}/{required_codes}; got {result['status']}/{meaningful_codes}")
        write_report(result, args.output / name)
        evidence.append(dict(case=name, status=result["status"], codes=sorted(codes),
                             blender_version=source["producer_version"], unity_version=target["producer_version"]))
        print(f"OK {name}: {result['status']} ({', '.join(sorted(codes)) or 'no findings'})")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "integration-summary.json").write_text(json.dumps(dict(success=True, cases=evidence), indent=2) + "\n", encoding="utf-8")
    print(f"Validated {len(evidence)} real FBX capture comparisons.")


if __name__ == "__main__":
    main()
