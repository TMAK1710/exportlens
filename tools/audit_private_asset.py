"""Read a private Blender asset and export an isolated local audit artifact.

This command never saves the input .blend. All outputs must be outside the
repository and are not distributable fixtures. Auto-running file scripts is
disabled; textures, shader appearance and live deformation are not audited.
"""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import traceback

import bpy


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exportlens_private_blender", ROOT / "blender_addon" / "__init__.py")
addon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(addon)


def sha256(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    source = args.source.resolve()
    output = args.output_dir.resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("Private asset outputs must stay outside the public repository")
    if source.suffix.lower() != ".blend" or not source.is_file():
        raise ValueError("--source must be an existing .blend")
    output.mkdir(parents=True, exist_ok=True)
    input_hash = sha256(source)
    working = output / "private_working_copy.blend"
    if working == source:
        raise ValueError("Working copy must differ from source")
    shutil.copy2(source, working)
    bpy.ops.wm.open_mainfile(filepath=str(working), load_ui=False, use_scripts=False)
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    view_meshes = [obj for obj in bpy.context.view_layer.objects if obj.type == "MESH" and len(obj.data.vertices)]
    if not view_meshes:
        raise ValueError("No non-empty meshes in active view layer")
    visible_meshes = [mesh for mesh in view_meshes if mesh.visible_get()]
    if not visible_meshes:
        raise ValueError("No visible meshes; explicit private audit scope cannot be inferred")
    rig_groups = {}
    for mesh in visible_meshes:
        rig = mesh.find_armature()
        if rig:
            rig_groups.setdefault(rig, []).append(mesh)
    score = lambda meshes: sum(len(mesh.data.vertices) + (1000 * len(mesh.data.shape_keys.key_blocks) if mesh.data.shape_keys else 0) for mesh in meshes)
    if rig_groups:
        rig = max(rig_groups, key=lambda item: score(rig_groups[item]))
        # Keep original mesh roots. Adding the rig here would intentionally
        # expand every hidden sibling and audit more than the visible model.
        roots = rig_groups[rig]
    else:
        roots = [max(visible_meshes, key=lambda mesh: score([mesh]))]
    chosen = addon.export_objects(roots)
    snapshot = addon.collect_snapshot(roots, asset_name="private_asset")
    visibility = []
    warnings = list(snapshot["metadata"]["warnings"])
    for obj in chosen:
        if obj.name not in bpy.context.view_layer.objects:
            raise ValueError("Principal hierarchy contains objects excluded from active view layer: " + obj.name)
        visibility.append((obj, obj.hide_get(), obj.hide_viewport, obj.hide_select))
        if obj.hide_get() or obj.hide_viewport or obj.hide_select:
            warnings.append("Working copy temporarily unhides for export: " + obj.name)
        obj.hide_set(False)
        obj.hide_viewport = False
        obj.hide_select = False
    target = output / "private_asset.fbx"
    try:
        result = addon.export_audited(target, roots, overwrite=True)
    finally:
        for obj, hidden, hidden_viewport, hidden_select in visibility:
            obj.hide_set(hidden)
            obj.hide_viewport = hidden_viewport
            obj.hide_select = hidden_select
    result["metadata"]["warnings"] = sorted(set(warnings + result["metadata"]["warnings"]))
    result["metadata"]["private_asset"] = True
    result["metadata"]["scope_selection"] = "Visible meshes attached to highest scoring armature; hidden siblings excluded; fallback largest visible mesh"
    result["metadata"]["input_view_layer_meshes"] = len(view_meshes)
    result["metadata"]["input_visible_meshes"] = len(visible_meshes)
    result["metadata"]["excluded_hidden_meshes"] = len(view_meshes) - len(visible_meshes)
    result["metadata"]["external_libraries"] = [library.filepath for library in bpy.data.libraries]
    addon.write_snapshot(result, target.with_suffix(".source.json"))
    assert sha256(source) == input_hash, "Original input changed"
    assert sha256(working) == input_hash, "Working .blend was saved or modified on disk"
    summary = {
        "status": "exported", "blender": bpy.app.version_string,
        "input_sha256": input_hash, "original_file_unchanged": True,
        "working_blend_unchanged": True, "private_outputs_only": True,
        "mesh_count": len(result["meshes"]),
        "input_view_layer_meshes": len(view_meshes),
        "input_visible_meshes": len(visible_meshes),
        "excluded_hidden_meshes": len(view_meshes) - len(visible_meshes),
        "vertices": sum(mesh["vertex_count"] for mesh in result["meshes"]),
        "blend_shape_count": sum(len(mesh["blend_shapes"]) for mesh in result["meshes"]),
        "unique_bones": len({bone["name"] for mesh in result["meshes"] for bone in mesh["bones"]}),
        "material_slots": sum(len(mesh["materials"]) for mesh in result["meshes"]),
        "warnings": result["metadata"]["warnings"],
        "artifact_sha256": result["artifact_sha256"],
    }
    addon.write_snapshot(summary, output / "runlog.json")
    print("EXPORTLENS_PRIVATE_AUDIT " + json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
