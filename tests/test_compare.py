import copy
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from exportlens.compare import SnapshotError, compare
from exportlens.report import render_html, write_report
from exportlens.__main__ import main


def captures():
    mesh = dict(name="Robot", path="Rig/Robot", bounds_size=[1, .6, 2], vertex_count=100,
                materials=["Mint", "Graphite"], blend_shapes=["Smile", "Blink"],
                bones=[dict(name="Base", parent=None), dict(name="Chest", parent="Base"), dict(name="Head", parent="Chest")])
    source = dict(schema_version=1, producer="blender", producer_version="5.2.3", asset_name="Robot",
                  source_file="robot.blend", artifact_sha256="a" * 64,
                  units=dict(meters_per_unit=1., up_axis="Z"), meshes=[mesh])
    target = copy.deepcopy(source)
    target.update(producer="unity", producer_version="2022.3.22f1", source_file="robot.fbx",
                  units=dict(meters_per_unit=1., up_axis="Y"))
    target["meshes"][0]["bounds_size"] = [1, 2, .6]
    return source, target


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.source, self.target = captures()
        self.s = self.source["meshes"][0]
        self.t = self.target["meshes"][0]

    def codes(self):
        result = compare(self.source, self.target)
        return result, {f["code"] for f in result["findings"]}

    def test_baseline(self):
        result = compare(self.source, self.target)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["summary"], dict(errors=0, warnings=0, info=0, checks=5))

    def test_centimeters_are_physical_not_raw_unit_equality(self):
        self.source["units"]["meters_per_unit"] = .01
        self.s["bounds_size"] = [100, 60, 200]
        self.assertEqual(compare(self.source, self.target)["status"], "pass")

    def test_vertex_splits_are_informational(self):
        self.t["vertex_count"] = 400
        result, codes = self.codes()
        self.assertEqual(result["status"], "pass")
        self.assertIn("VERTEX_COUNT_CHANGED", codes)

    def test_wrong_scale(self):
        self.t["bounds_size"] = [.01, .02, .006]
        result, codes = self.codes()
        self.assertEqual(result["status"], "fail")
        self.assertIn("BOUNDS_SIZE_CHANGED", codes)
        self.assertEqual(next(c for c in result["checks"] if c["category"] == "dimensions")["status"], "fail")

    def test_tolerance_boundary(self):
        self.t["bounds_size"][0] += .0109
        self.assertEqual(compare(self.source, self.target)["status"], "pass")
        self.t["bounds_size"][0] += .0002
        self.assertEqual(compare(self.source, self.target)["status"], "fail")

    def test_custom_tolerance(self):
        self.t["bounds_size"][0] += .02
        self.assertEqual(compare(self.source, self.target, dict(absolute_tolerance_m=.03, relative_tolerance=0))["status"], "pass")

    def test_lost_shape(self):
        self.t["blend_shapes"] = ["Blink"]
        self.assertIn("BLEND_SHAPE_MISSING", self.codes()[1])

    def test_unique_shape_prefix(self):
        self.t["blend_shapes"] = ["Robot.Smile", "Robot.Blink"]
        result, codes = self.codes()
        self.assertEqual(result["status"], "pass")
        self.assertIn("BLEND_SHAPE_PREFIX", codes)

    def test_ambiguous_shape_prefix(self):
        self.t["blend_shapes"] = ["Robot.Smile", "Other.Smile", "Blink"]
        self.assertIn("BLEND_SHAPE_AMBIGUOUS", self.codes()[1])

    def test_overlapping_shape_matches(self):
        self.s["blend_shapes"] = ["Smile", "Robot.Smile"]
        self.t["blend_shapes"] = ["Robot.Smile"]
        self.assertIn("BLEND_SHAPE_AMBIGUOUS", self.codes()[1])

    def test_exact_shape_takes_priority(self):
        self.t["blend_shapes"].append("Other.Smile")
        self.assertEqual(compare(self.source, self.target)["status"], "pass")

    def test_bone_reparent(self):
        self.t["bones"][2]["parent"] = "Base"
        self.assertIn("BONE_PARENT_CHANGED", self.codes()[1])

    def test_missing_bone(self):
        self.t["bones"].pop()
        self.assertIn("BONE_MISSING", self.codes()[1])

    def test_import_wrapper_ignored(self):
        self.t["bones"][0]["parent"] = "Rig"
        self.t["bones"][2]["parent"] = "Wrapper"
        self.t["bones"] += [dict(name="Rig", parent=None), dict(name="Wrapper", parent="Chest")]
        self.assertEqual(compare(self.source, self.target)["status"], "pass")

    def test_duplicate_relevant_bone_fails(self):
        self.t["bones"].append(dict(name="Head", parent="Base"))
        self.assertIn("BONE_AMBIGUOUS", self.codes()[1])

    def test_duplicate_unused_nodes_dont_fail(self):
        self.t["bones"] += [dict(name="Unused", parent=None)] * 2
        self.assertEqual(compare(self.source, self.target)["status"], "pass")

    def test_missing_wrapper_link_fails(self):
        self.t["bones"][0]["parent"] = "MissingWrapper"
        self.assertIn("BONE_PARENT_UNRESOLVED", self.codes()[1])

    def test_wrapper_cycle_fails(self):
        self.t["bones"][0]["parent"] = "Wrapper"
        self.t["bones"] += [dict(name="Wrapper", parent="Loop"), dict(name="Loop", parent="Wrapper")]
        self.assertIn("BONE_PARENT_UNRESOLVED", self.codes()[1])

    def test_lost_slot_fails(self):
        self.t["materials"].pop()
        self.assertIn("MATERIAL_SLOT_COUNT_CHANGED", self.codes()[1])

    def test_slot_order_review(self):
        self.t["materials"].reverse()
        result, codes = self.codes()
        self.assertEqual(result["status"], "review")
        self.assertIn("MATERIAL_SLOT_NAMES_CHANGED", codes)

    def test_hash_mismatch(self):
        self.target["artifact_sha256"] = "b" * 64
        result, codes = self.codes()
        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["checks"][0]["status"], "fail")
        self.assertIn("ARTIFACT_MISMATCH", codes)

    def test_unbound_review(self):
        self.source["artifact_sha256"] = None
        self.assertEqual(compare(self.source, self.target)["status"], "review")

    def test_hash_case_insensitive(self):
        self.target["artifact_sha256"] = "A" * 64
        self.assertEqual(compare(self.source, self.target)["status"], "pass")

    def test_mesh_missing(self):
        self.t["name"] = "Renamed"
        self.assertIn("MESH_MISSING", self.codes()[1])
        self.assertEqual(compare(self.source, self.target, dict(mesh_map=dict(Robot="Renamed")))["status"], "pass")

    def test_mapping_must_be_one_to_one(self):
        mesh = copy.deepcopy(self.s)
        mesh["name"] = "Other"
        self.source["meshes"].append(mesh)
        with self.assertRaises(SnapshotError):
            compare(self.source, self.target, dict(mesh_map=dict(Other="Robot")))

    def test_added_mesh_review(self):
        mesh = copy.deepcopy(self.t)
        mesh["name"] = "Added"
        self.target["meshes"].append(mesh)
        self.assertEqual(compare(self.source, self.target)["status"], "review")

    def test_invalid_snapshots_rejected(self):
        cases = [("schema_version", True), ("schema_version", 2), ("units", None), ("units", []),
                 ("units", dict(meters_per_unit=float("nan"), up_axis="Z")),
                 ("units", dict(meters_per_unit=True, up_axis="Z")), ("meshes", []),
                 ("artifact_sha256", "nope"), ("producer", "unity")]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                snapshot = copy.deepcopy(self.source)
                snapshot[key] = value
                with self.assertRaises(SnapshotError):
                    compare(snapshot, self.target)

    def test_invalid_meshes_rejected(self):
        cases = [("bounds_size", [1, float("inf"), 2]), ("bounds_size", [-1, 2, 3]),
                 ("vertex_count", True), ("blend_shapes", ["A", "A"]), ("materials", "Mint"),
                 ("bones", [dict(name="A", parent="A")]), ("bones", [dict(name="A", parent="Missing")])]
        for key, value in cases:
            with self.subTest(key=key, value=value):
                snapshot = copy.deepcopy(self.source)
                snapshot["meshes"][0][key] = value
                with self.assertRaises(SnapshotError):
                    compare(snapshot, self.target)

    def test_invalid_config_rejected(self):
        for config in (False, [], dict(typo=1), dict(relative_tolerance=-1), dict(absolute_tolerance_m=float("nan")), dict(mesh_map=dict(Unknown="X"))):
            with self.subTest(config=config), self.assertRaises(SnapshotError):
                compare(self.source, self.target, config)

    def test_duplicate_mesh_names_rejected(self):
        self.source["meshes"].append(copy.deepcopy(self.s))
        with self.assertRaises(SnapshotError):
            compare(self.source, self.target)

    def test_capture_scope_notes_remain_visible(self):
        self.source["metadata"] = dict(warnings=["Base snapshot ignores modifiers on Robot: Bevel"])
        result, codes = self.codes()
        self.assertEqual(result["status"], "pass")
        self.assertIn("CAPTURE_SCOPE_NOTE", codes)
        self.assertIn("Bevel", render_html(result))

    def test_large_integer_rejected_without_overflow(self):
        self.source["units"]["meters_per_unit"] = 10 ** 400
        with self.assertRaises(SnapshotError):
            compare(self.source, self.target)

    def test_normalized_dimension_overflow_rejected(self):
        self.source["units"]["meters_per_unit"] = 1e308
        with self.assertRaises(SnapshotError):
            compare(self.source, self.target)

    def test_tolerance_overflow_rejected(self):
        with self.assertRaises(SnapshotError):
            compare(self.source, self.target, dict(relative_tolerance=1e308))

    def test_slash_in_other_mesh_name_does_not_pollute_check(self):
        child_source, child_target = copy.deepcopy(self.s), copy.deepcopy(self.t)
        child_source["name"] = child_target["name"] = "Robot/Cloth"
        child_target["materials"] = ["Changed", "Graphite"]
        self.source["meshes"].append(child_source)
        self.target["meshes"].append(child_target)
        result = compare(self.source, self.target)
        statuses = {c["subject"]: c["status"] for c in result["checks"] if c["category"] == "materials"}
        self.assertEqual(statuses, {"Robot": "pass", "Robot/Cloth": "review"})


class ReportAndCliTests(unittest.TestCase):
    def test_html_escapes_untrusted_names(self):
        source, target = captures()
        source["asset_name"] = '<script>alert("x")</script>'
        result = render_html(compare(source, target))
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;", result)
        self.assertNotIn('src="http', result)

    def test_cli_exit_codes_and_report(self):
        source, target = captures()
        # Keep all test temporary output on F: when using this Windows workspace.
        temporary_root = Path("F:/CodexTemp/ExportLens") if Path("F:/CodexTemp/ExportLens").is_dir() else None
        with tempfile.TemporaryDirectory(dir=temporary_root) as temp, redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            root = Path(temp)
            a, b = root / "source.json", root / "target.json"
            a.write_text(json.dumps(source), encoding="utf-8-sig")
            b.write_text(json.dumps(target), encoding="utf-8")
            args = ["compare", str(a), str(b), "--output", str(root / "report")]
            self.assertEqual(main(args), 0)
            self.assertIn("Consistent within scope", (root / "report/report.html").read_text(encoding="utf-8"))
            self.assertEqual(json.loads((root / "report/report.json").read_text(encoding="utf-8"))["status"], "pass")
            target["meshes"][0]["bounds_size"] = [5, 5, 5]
            b.write_text(json.dumps(target), encoding="utf-8")
            self.assertEqual(main(args), 1)
            b.write_text("{}", encoding="utf-8")
            self.assertEqual(main(args), 2)
            b.write_text("not JSON", encoding="utf-8")
            self.assertEqual(main(args), 2)


if __name__ == "__main__":
    unittest.main()
