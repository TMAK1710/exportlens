"""Pure comparison logic. This module does not launch or modify either editor."""
import math
import re
from collections import Counter


class SnapshotError(ValueError):
    pass


def _number(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def validate(snapshot, producer):
    if not isinstance(snapshot, dict) or type(snapshot.get("schema_version")) is not int or snapshot["schema_version"] != 1:
        raise SnapshotError("Expected snapshot schema_version 1.")
    if snapshot.get("producer") != producer:
        raise SnapshotError("Expected a %s snapshot." % producer)
    for key in ("producer_version", "asset_name", "source_file"):
        if not isinstance(snapshot.get(key), str) or not snapshot[key]:
            raise SnapshotError("Missing or invalid %s." % key)
    digest = snapshot.get("artifact_sha256")
    if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", digest)):
        raise SnapshotError("artifact_sha256 must be a SHA-256 hex digest or null.")
    units = snapshot.get("units", {})
    if not isinstance(units, dict) or not _number(units.get("meters_per_unit")) or units["meters_per_unit"] <= 0:
        raise SnapshotError("units.meters_per_unit must be finite and positive.")
    if units.get("up_axis") != ("Z" if producer == "blender" else "Y"):
        raise SnapshotError("Unsupported up axis; v1 expects Blender Z-up and Unity Y-up.")
    meshes = snapshot.get("meshes")
    if not isinstance(meshes, list) or not meshes:
        raise SnapshotError("Snapshot has no meshes; an empty capture cannot pass.")
    names = []
    for mesh in meshes:
        if not isinstance(mesh, dict) or not isinstance(mesh.get("name"), str) or not mesh["name"]:
            raise SnapshotError("Each mesh needs a nonempty name.")
        names.append(mesh["name"])
        size = mesh.get("bounds_size")
        if not isinstance(size, list) or len(size) != 3 or not all(_number(n) and n >= 0 for n in size):
            raise SnapshotError("%s: bounds_size needs three finite nonnegative values." % mesh["name"])
        n = mesh.get("vertex_count")
        if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
            raise SnapshotError("%s: vertex_count must be positive." % mesh["name"])
        if not isinstance(mesh.get("path"), str):
            raise SnapshotError("%s: path must be a string." % mesh["name"])
        mats = mesh.get("materials")
        if not isinstance(mats, list) or not all(n is None or isinstance(n, str) for n in mats):
            raise SnapshotError("%s: invalid material slots." % mesh["name"])
        shapes = mesh.get("blend_shapes")
        if not isinstance(shapes, list) or not all(isinstance(n, str) and n for n in shapes):
            raise SnapshotError("%s: invalid blend shape names." % mesh["name"])
        if len(set(shapes)) != len(shapes):
            raise SnapshotError("%s: duplicate blend shape names." % mesh["name"])
        bones = mesh.get("bones")
        if not isinstance(bones, list):
            raise SnapshotError("%s: bones must be an array." % mesh["name"])
        for bone in bones:
            if not isinstance(bone, dict) or not isinstance(bone.get("name"), str) or not bone["name"]:
                raise SnapshotError("Invalid bone entry.")
            if "parent" not in bone or (bone["parent"] is not None and not isinstance(bone["parent"], str)):
                raise SnapshotError("Invalid bone parent.")
        if producer == "blender":
            bone_names = [b["name"] for b in bones]
            if len(set(bone_names)) != len(bone_names):
                raise SnapshotError("Source bone names must be unique per mesh.")
            parents = {b["name"]: b["parent"] for b in bones}
            for name in parents:
                seen = set()
                while name is not None:
                    if name not in parents:
                        raise SnapshotError("Source bone parent is missing from snapshot.")
                    if name in seen:
                        raise SnapshotError("Source bone hierarchy contains a cycle.")
                    seen.add(name)
                    name = parents[name]
    if len(set(names)) != len(names):
        raise SnapshotError("Mesh names must be unique; rename or capture a smaller selection.")
    metadata = snapshot.get("metadata", {})
    if not isinstance(metadata, dict):
        raise SnapshotError("metadata must be an object.")
    notes = metadata.get("warnings", [])
    if not isinstance(notes, list) or not all(isinstance(note, str) for note in notes):
        raise SnapshotError("metadata.warnings must be an array of strings.")


def compare(source, target, config=None):
    validate(source, "blender")
    validate(target, "unity")
    config = {} if config is None else config
    if not isinstance(config, dict) or set(config) - {"mesh_map", "absolute_tolerance_m", "relative_tolerance"}:
        raise SnapshotError("Unknown comparison configuration fields.")
    atol = config.get("absolute_tolerance_m", 0.001)
    rtol = config.get("relative_tolerance", 0.01)
    if not all(_number(v) and v >= 0 for v in (atol, rtol)):
        raise SnapshotError("Tolerances must be finite and nonnegative.")
    mapping = config.get("mesh_map", {})
    if not isinstance(mapping, dict) or not all(isinstance(a, str) and isinstance(b, str) for a, b in mapping.items()):
        raise SnapshotError("mesh_map must map source names to target names.")
    src_names = {m["name"] for m in source["meshes"]}
    if set(mapping) - src_names:
        raise SnapshotError("mesh_map contains unknown source meshes.")
    desired = [mapping.get(m["name"], m["name"]) for m in source["meshes"]]
    if len(set(desired)) != len(desired):
        raise SnapshotError("mesh_map must be one-to-one.")
    findings, checks = [], []
    current_mesh = None

    def add(severity, code, subject, message, expected=None, actual=None, hint=""):
        findings.append(dict(severity=severity, code=code, subject=subject, message=message,
                             expected=expected, actual=actual, hint=hint, mesh=current_mesh))

    for producer, snapshot in (("Blender", source), ("Unity", target)):
        for note in snapshot.get("metadata", {}).get("warnings", []):
            add("info", "CAPTURE_SCOPE_NOTE", producer + " capture", note)

    a, b = source.get("artifact_sha256"), target.get("artifact_sha256")
    checks.append(dict(category="identity", subject="FBX", status="pass", detail="SHA-256 matches", expected=a, actual=b))
    if not a or not b:
        checks[-1].update(status="review", detail="FBX identity is unverified")
        add("warning", "ARTIFACT_UNBOUND", "FBX identity", "One capture is not bound to the exported FBX.", hint="Use the audited Blender FBX export and capture that exact file in Unity.")
    elif a.lower() != b.lower():
        checks[-1].update(status="fail", detail="Different FBX bytes")
        add("error", "ARTIFACT_MISMATCH", "FBX identity", "The captures refer to different FBX bytes.", a, b, "Import the FBX paired with the source snapshot; do not compare stale captures.")
    target_meshes = {m["name"]: m for m in target["meshes"]}
    used = set()
    for sm in source["meshes"]:
        name = sm["name"]
        current_mesh = name
        tn = mapping.get(name, name)
        tm = target_meshes.get(tn)
        if tm is None:
            checks.append(dict(category="mesh", subject=name, status="fail", detail="Mesh missing in Unity", expected=tn, actual=None))
            add("error", "MESH_MISSING", name, "Source mesh was not found in Unity.", tn, sorted(target_meshes), "Check export selection or use an explicit mesh_map for an intentional rename.")
            continue
        used.add(tn)
        for category in ("dimensions", "bones", "blend_shapes", "materials"):
            checks.append(dict(category=category, subject=name, status="pass", detail=""))
        expected = [sm["bounds_size"][i] * source["units"]["meters_per_unit"] for i in (0, 2, 1)]
        actual = [v * target["units"]["meters_per_unit"] for v in tm["bounds_size"]]
        thresholds = [atol + rtol * v for v in expected]
        if not all(_number(v) for v in expected + actual + thresholds):
            raise SnapshotError("Normalized dimensions or tolerances overflowed; check unit scale and bounds.")
        checks[-4].update(detail="X / Y / Z in meters, Unity axes", expected=expected, actual=actual)
        checks[-3].update(detail="Source bone hierarchy; import wrappers ignored", expected=sm["bones"], actual=tm["bones"])
        checks[-2].update(detail="Channel names; unique FBX prefixes accepted", expected=sm["blend_shapes"], actual=tm["blend_shapes"])
        checks[-1].update(detail="Ordered material slots", expected=sm["materials"], actual=tm["materials"])
        if any(abs(a-b) > threshold for a, b, threshold in zip(expected, actual, thresholds)):
            add("error", "BOUNDS_SIZE_CHANGED", name, "Axis-aligned rest bounds changed after meter / up-axis normalization.", expected, actual, "Check Blender export unit settings and Unity Scale Factor / Convert Units. Bounds do not prove orientation or deformation fidelity.")
        if sm["vertex_count"] != tm["vertex_count"]:
            add("info", "VERTEX_COUNT_CHANGED", name, "Imported vertex count differs; UV, normal and material seams may split vertices.", sm["vertex_count"], tm["vertex_count"])
        t_shapes = tm["blend_shapes"]
        matched_shapes = set()
        for shape in sm["blend_shapes"]:
            candidates = [n for n in t_shapes if n == shape or n.endswith("." + shape)]
            if shape in candidates:
                candidates = [shape]
            if not candidates:
                add("error", "BLEND_SHAPE_MISSING", name, "Shape key did not arrive as a blend shape.", shape, t_shapes, "Check FBX Apply Modifiers and Unity Import BlendShapes; inspect the source export settings.")
            elif len(candidates) > 1 or candidates[0] in matched_shapes:
                add("error", "BLEND_SHAPE_AMBIGUOUS", name, "Cannot match shape names unambiguously.", shape, candidates)
            else:
                matched_shapes.add(candidates[0])
                if candidates[0] != shape:
                    add("info", "BLEND_SHAPE_PREFIX", name, "Recognized a unique FBX blend shape name prefix.", shape, candidates[0])
        extras = sorted(set(t_shapes) - matched_shapes)
        if extras:
            add("info", "BLEND_SHAPE_ADDED", name, "Unity contains additional blend shape channels.", [], extras)
        s_bones = {bone["name"]: bone["parent"] for bone in sm["bones"]}
        counts = Counter(bone["name"] for bone in tm["bones"])
        t_bones = {bone["name"]: bone["parent"] for bone in tm["bones"] if counts[bone["name"]] == 1}
        for bone, parent in s_bones.items():
            if not counts[bone]:
                add("error", "BONE_MISSING", name + "/" + bone, "Source bone is missing from the imported hierarchy.", bone, None, "Check deform-only export, Optimize Game Objects and export selection.")
                continue
            if counts[bone] > 1:
                add("error", "BONE_AMBIGUOUS", name + "/" + bone, "Multiple imported nodes have this source bone name.", 1, counts[bone])
                continue
            actual_parent = t_bones[bone]
            seen = {bone}
            ambiguous = False
            while actual_parent is not None and actual_parent not in s_bones:
                if actual_parent in seen or counts[actual_parent] != 1:
                    ambiguous = True
                    break
                seen.add(actual_parent)
                actual_parent = t_bones.get(actual_parent)
            if ambiguous:
                add("error", "BONE_PARENT_UNRESOLVED", name + "/" + bone, "Cannot resolve imported parent chain without ambiguity or cycles.")
            elif parent != actual_parent:
                add("error", "BONE_PARENT_CHANGED", name + "/" + bone, "Bone parent changed (non-bone import wrappers are ignored).", parent, actual_parent)
        if len(sm["materials"]) != len(tm["materials"]):
            add("error", "MATERIAL_SLOT_COUNT_CHANGED", name, "Material slot count changed.", sm["materials"], tm["materials"], "Check material export/import settings. This does not inspect face-to-slot assignments.")
        elif sm["materials"] != tm["materials"]:
            add("warning", "MATERIAL_SLOT_NAMES_CHANGED", name, "Ordered material slot names changed; appearance is not evaluated.", sm["materials"], tm["materials"], "Review deliberate remaps or renamed imported materials.")
    for name in sorted(set(target_meshes) - used):
        current_mesh = name
        add("warning", "MESH_ADDED", name, "Unity contains an unmatched mesh.")
    code_category = {"BOUNDS": "dimensions", "BONE": "bones", "BLEND_SHAPE": "blend_shapes", "MATERIAL": "materials"}
    for check in checks:
        relevant = [f for f in findings if f["mesh"] == check["subject"]
                    and any(f["code"].startswith(prefix) and check["category"] == cat for prefix, cat in code_category.items())]
        if any(f["severity"] == "error" for f in relevant):
            check["status"] = "fail"
        elif any(f["severity"] == "warning" for f in relevant):
            check["status"] = "review"
    counts = Counter(f["severity"] for f in findings)
    status = "fail" if counts["error"] else "review" if counts["warning"] else "pass"
    return dict(schema_version=1, status=status,
                summary=dict(errors=counts["error"], warnings=counts["warning"], info=counts["info"], checks=len(checks)),
                source={k: source.get(k) for k in ("producer", "producer_version", "asset_name", "source_file", "artifact_sha256")},
                target={k: target.get(k) for k in ("producer", "producer_version", "asset_name", "source_file", "artifact_sha256")},
                tolerances=dict(absolute_m=atol, relative=rtol), checks=checks, findings=findings,
                limitations=["Rest axis-aligned dimensions only: not orientation, handedness or pivot validation.",
                             "Bone names/parents only: not skin weights, bind poses, animation or deformation.",
                             "Shape channel presence only: not vertex deltas or expression quality.",
                             "Material slot count/names only: not face assignments, shaders, colors or textures."])
