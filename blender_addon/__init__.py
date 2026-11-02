"""ExportLens Blender source snapshot and audited FBX export.

The collector reads original/base geometry. It does not apply modifiers, rename
objects, or change the user's model. FBX export temporarily changes selection
and restores it even when the export fails.
"""

bl_info = {
    "name": "ExportLens — FBX Consistency Snapshot",
    "author": "ExportLens contributors",
    "version": (0, 1, 0),
    "blender": (4, 2, 0),
    "location": "View3D > Sidebar > ExportLens",
    "description": "Capture base geometry and export FBX with a comparison snapshot",
    "category": "Import-Export",
}

import hashlib
import json
from pathlib import Path

import bpy
from bpy.props import BoolProperty, StringProperty
from bpy_extras.io_utils import ExportHelper


EXPORT_SETTINGS = {
    "use_selection": True,
    "global_scale": 1.0,
    "apply_unit_scale": True,
    "apply_scale_options": "FBX_SCALE_ALL",
    "axis_forward": "-Z",
    "axis_up": "Y",
    "use_space_transform": True,
    "bake_space_transform": False,
    "object_types": {"EMPTY", "ARMATURE", "MESH"},
    "use_mesh_modifiers": False,
    "add_leaf_bones": False,
    "use_armature_deform_only": False,
    "bake_anim": False,
    "path_mode": "AUTO",
    "embed_textures": False,
}


def object_path(obj):
    names = []
    while obj:
        names.append(obj.name)
        obj = obj.parent
    return "/".join(reversed(names))


def export_objects(objects=None):
    """Expand selected roots and include armatures needed by selected meshes."""
    chosen = list(bpy.context.selected_objects if objects is None else objects)
    found = {obj.name: obj for obj in chosen}
    for obj in chosen:
        for child in obj.children_recursive:
            found[child.name] = child
    for obj in list(found.values()):
        if obj.type == "MESH":
            rig = obj.find_armature()
            if rig:
                found[rig.name] = rig
            ancestor = obj.parent
            while ancestor:
                found[ancestor.name] = ancestor
                ancestor = ancestor.parent
    return sorted((o for o in found.values() if o.type in {"MESH", "ARMATURE", "EMPTY"}),
                  key=object_path)


def collect_snapshot(objects=None, artifact_path=None, asset_name=None):
    """Return snapshot v1 of source/base meshes, in native Z-up scene units.

    `objects` is an explicit iterable or the current selection. Modifiers,
    posed bone deformation, shader appearance and shape-key deltas are outside
    v0.1; their presence is recorded as a limitation, never silently certified.
    """
    return _collect_snapshot_resolved(export_objects(objects), artifact_path, asset_name)


def _collect_snapshot_resolved(objects, artifact_path=None, asset_name=None):
    """Read an already resolved set without expanding auto-added parents again."""
    meshes = []
    warnings = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        data = obj.data
        if not data.vertices:
            warnings.append("Empty mesh: " + object_path(obj))
            continue
        basis = data.shape_keys.key_blocks[0] if data.shape_keys else None
        points = [obj.matrix_world @ (basis.data[v.index].co if basis else v.co)
                  for v in data.vertices]
        bounds = [max(p[i] for p in points) - min(p[i] for p in points) for i in range(3)]
        rig = obj.find_armature()
        bones = []
        if rig:
            bones = [{"name": bone.name, "parent": bone.parent.name if bone.parent else None}
                     for bone in rig.data.bones]
            if rig.pose and any(abs(v - expected) > 1e-6
                                for pb in rig.pose.bones
                                for row, expected_row in zip(pb.matrix_basis, ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)))
                                for v, expected in zip(row, expected_row)):
                warnings.append("Posed armature is not evaluated in base snapshot: " + rig.name)
        unsupported = [m.name for m in obj.modifiers if m.type != "ARMATURE" and m.show_viewport]
        if unsupported:
            warnings.append("Base snapshot ignores modifiers on %s: %s" % (obj.name, ", ".join(unsupported)))
        if obj.data.shape_keys and any(abs(k.value) > 1e-6 for k in list(obj.data.shape_keys.key_blocks)[1:]):
            warnings.append("Nonzero shape-key weights are ignored in base snapshot: " + obj.name)
        meshes.append({
            "name": obj.name,
            "path": object_path(obj),
            "bounds_size": bounds,
            "vertex_count": len(data.vertices),
            "materials": [slot.material.name if slot.material else None for slot in obj.material_slots],
            "blend_shapes": [k.name for k in list(data.shape_keys.key_blocks)[1:]] if data.shape_keys else [],
            "bones": bones,
        })
    if not meshes:
        raise ValueError("Select at least one non-empty mesh or a hierarchy containing meshes.")
    artifact = Path(artifact_path) if artifact_path else None
    return {
        "schema_version": 1,
        "producer": "blender",
        "producer_version": bpy.app.version_string,
        "asset_name": asset_name or (artifact.stem if artifact else Path(bpy.data.filepath).stem or "Untitled"),
        "source_file": artifact.name if artifact else (Path(bpy.data.filepath).name or "Untitled.blend"),
        "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest() if artifact and artifact.exists() else None,
        "units": {"meters_per_unit": bpy.context.scene.unit_settings.scale_length, "up_axis": "Z"},
        "meshes": meshes,
        "metadata": {"geometry_basis": "original base/basis vertices transformed to scene world space",
                     "warnings": warnings,
                     "scope": "structure and rest bounds only; not animation, weights, deformation, textures or shader fidelity"},
    }


def write_snapshot(snapshot, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def export_audited(filepath, objects=None, snapshot_path=None, overwrite=False):
    """Export fixed FBX settings plus baseline JSON without changing model data."""
    if bpy.context.mode != "OBJECT":
        raise ValueError("Switch to Object Mode before capturing or exporting.")
    target = Path(filepath)
    if target.suffix.lower() != ".fbx":
        raise ValueError("Audited export currently supports .fbx only.")
    snapshot_path = Path(snapshot_path) if snapshot_path else target.with_suffix(".source.json")
    if target.resolve() == snapshot_path.resolve():
        raise ValueError("FBX and JSON must use different output paths.")
    if not overwrite and (target.exists() or snapshot_path.exists()):
        raise FileExistsError("Output exists. Choose a new name or explicitly enable overwrite.")
    chosen = export_objects(objects)
    snapshot = _collect_snapshot_resolved(chosen, asset_name=target.stem)
    previous_selection = list(bpy.context.selected_objects)
    previous_active = bpy.context.view_layer.objects.active
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in chosen:
            if obj.name not in bpy.context.view_layer.objects:
                raise ValueError("Object not present in active view layer: " + obj.name)
            obj.select_set(True)
        actual_selection = {obj.name for obj in bpy.context.selected_objects}
        expected_selection = {obj.name for obj in chosen}
        if actual_selection != expected_selection:
            missing = sorted(expected_selection - actual_selection)
            raise ValueError("Export objects cannot be selected, possibly hidden by a collection: " + ", ".join(missing))
        bpy.context.view_layer.objects.active = next((o for o in chosen if o.type == "MESH"), chosen[0])
        outcome = bpy.ops.export_scene.fbx(filepath=str(target), check_existing=False, **EXPORT_SETTINGS)
        if "FINISHED" not in outcome or not target.is_file():
            raise RuntimeError("FBX exporter did not produce a finished artifact.")
    finally:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in previous_selection:
            if obj.name in bpy.context.view_layer.objects:
                obj.select_set(True)
        bpy.context.view_layer.objects.active = previous_active
    snapshot["source_file"] = target.name
    snapshot["artifact_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    snapshot["metadata"]["export_settings"] = {k: sorted(v) if isinstance(v, set) else v for k, v in EXPORT_SETTINGS.items()}
    write_snapshot(snapshot, snapshot_path)
    return snapshot


class EXPORTLENS_OT_snapshot(bpy.types.Operator, ExportHelper):
    bl_idname = "exportlens.snapshot"
    bl_label = "Save Source Snapshot"
    bl_description = "Read selected base geometry without exporting or modifying it"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            write_snapshot(collect_snapshot(), self.filepath)
            self.report({"INFO"}, "Source snapshot saved")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class EXPORTLENS_OT_export(bpy.types.Operator, ExportHelper):
    bl_idname = "exportlens.export_fbx"
    bl_label = "Export FBX + Snapshot"
    bl_description = "Export selected hierarchy and save a paired .source.json for Unity comparison"
    filename_ext = ".fbx"
    filter_glob: StringProperty(default="*.fbx", options={"HIDDEN"})
    overwrite: BoolProperty(name="Overwrite Existing Files", default=False)

    def execute(self, context):
        try:
            export_audited(self.filepath, overwrite=self.overwrite)
            self.report({"INFO"}, "FBX and source snapshot saved")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class EXPORTLENS_PT_panel(bpy.types.Panel):
    bl_label = "ExportLens"
    bl_idname = "EXPORTLENS_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ExportLens"

    def draw(self, context):
        layout = self.layout
        layout.label(text="Blender → Unity consistency")
        layout.label(text="Select mesh or root hierarchy")
        layout.operator("exportlens.snapshot", icon="FILE_TEXT")
        layout.operator("exportlens.export_fbx", icon="EXPORT")
        box = layout.box()
        box.label(text="v0.1: base geometry + structure")
        box.label(text="Not a shader/deformation check")


_CLASSES = (EXPORTLENS_OT_snapshot, EXPORTLENS_OT_export, EXPORTLENS_PT_panel)


def register():
    for cls in _CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(_CLASSES):
        bpy.utils.unregister_class(cls)


if __name__ == "__main__":
    register()
