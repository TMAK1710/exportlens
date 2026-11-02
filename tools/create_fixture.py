"""Create original ExportLens integration fixtures in background Blender.

Run with Blender --background --factory-startup -t 2 --python this_file --
--output-dir F:/CodexTemp/ExportLens/fixtures --render. Never run on a user scene.
The block robot is authored procedurally here; no external artwork is used.
"""

import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("exportlens_blender", ROOT / "blender_addon" / "__init__.py")
addon = importlib.util.module_from_spec(spec)
spec.loader.exec_module(addon)


def build_robot(meters_per_unit=1.0, ordered_slots=False):
    """Build a 1 x 0.6 x 2m robot with two materials and three weighted bones."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = meters_per_unit
    scale = 1.0 / meters_per_unit
    vertices, faces, assignments, parts = [], [], [], {}

    def box(name, center, size, material, bone):
        start = len(vertices)
        for x, y, z in ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
                        (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)):
            vertices.append(tuple((center[i] + size[i] * (x, y, z)[i] / 2) * scale for i in range(3)))
        # Consistent outward winding: six faces per cuboid, all in one mesh.
        faces.extend(tuple(start + index for index in face) for face in
                     ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                      (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)))
        assignments.extend([material] * 6)
        parts[name] = {"indices": list(range(start, start + 8)), "bone": bone}

    if ordered_slots:
        box("body", (0, 0, 1.06), (.54, .34, .5), 0, "Chest")
    box("left_foot", (-.19, -.05, .06), (.24, .5, .12), 1, "Base")
    box("right_foot", (.19, .05, .06), (.24, .5, .12), 1, "Base")
    box("left_leg", (-.19, 0, .42), (.15, .19, .6), 0, "Base")
    box("right_leg", (.19, 0, .42), (.15, .19, .6), 0, "Base")
    box("hips", (0, 0, .73), (.5, .28, .18), 1, "Base")
    if not ordered_slots:
        box("body", (0, 0, 1.06), (.54, .34, .5), 0, "Chest")
    box("chest_badge", (0, -.185, 1.13), (.18, .035, .16), 1, "Chest")
    box("left_arm", (-.43, 0, 1.02), (.14, .22, .58), 0, "Chest")
    box("right_arm", (.43, 0, 1.02), (.14, .22, .58), 0, "Chest")
    box("neck", (0, 0, 1.36), (.16, .17, .1), 1, "Chest")
    box("head", (0, 0, 1.65), (.58, .5, .5), 0, "Head")
    box("left_eye", (-.14, -.263, 1.70), (.12, .026, .13), 1, "Head")
    box("right_eye", (.14, -.263, 1.70), (.12, .026, .13), 1, "Head")
    box("mouth", (0, -.263, 1.53), (.22, .026, .04), 1, "Head")
    box("antenna", (0, 0, 1.95), (.07, .07, .1), 1, "Head")

    data = bpy.data.meshes.new("RobotMesh")
    data.from_pydata(vertices, [], faces)
    data.update()
    robot = bpy.data.objects.new("Robot", data)
    scene.collection.objects.link(robot)
    for name, color in (("Mint", (.055, .56, .44, 1)), ("Graphite", (.022, .035, .047, 1))):
        material = bpy.data.materials.new(name)
        material.diffuse_color = color
        material.use_nodes = True
        shader = material.node_tree.nodes.get("Principled BSDF")
        shader.inputs["Base Color"].default_value = color
        shader.inputs["Roughness"].default_value = .37
        shader.inputs["Metallic"].default_value = .18
        data.materials.append(material)
    for polygon, material in zip(data.polygons, assignments):
        polygon.material_index = material

    rig_data = bpy.data.armatures.new("RobotRig")
    rig = bpy.data.objects.new("Rig", rig_data)
    scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    last = None
    for name, bottom, top in (("Base", 0, .75), ("Chest", .75, 1.38), ("Head", 1.38, 2)):
        bone = rig_data.edit_bones.new(name)
        bone.head = (0, 0, bottom * scale)
        bone.tail = (0, 0, top * scale)
        bone.parent = last
        bone.use_connect = last is not None
        last = bone
    bpy.ops.object.mode_set(mode="OBJECT")
    robot.parent = rig
    for name in ("Base", "Chest", "Head"):
        group = robot.vertex_groups.new(name=name)
        indices = [index for part in parts.values() if part["bone"] == name for index in part["indices"]]
        group.add(indices, 1.0, "REPLACE")
    modifier = robot.modifiers.new("Skin", "ARMATURE")
    modifier.object = rig
    robot.shape_key_add(name="Basis")
    smile = robot.shape_key_add(name="Smile")
    for index in parts["mouth"]["indices"]:
        smile.data[index].co.z += abs(smile.data[index].co.x) / (.11 * scale) * .055 * scale
    blink = robot.shape_key_add(name="Blink")
    for eye in ("left_eye", "right_eye"):
        for index in parts[eye]["indices"]:
            blink.data[index].co.z = 1.70 * scale + (blink.data[index].co.z - 1.70 * scale) * .08
    smile.value = blink.value = 0
    robot.active_shape_key_index = 0
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    robot.select_set(True)
    rig.select_set(True)
    bpy.context.view_layer.objects.active = robot
    return robot, rig


def mutate(robot, rig, variant):
    if variant == "lost_shapes":
        robot.shape_key_clear()
    elif variant == "reparented_bone":
        bpy.context.view_layer.objects.active = rig
        bpy.ops.object.mode_set(mode="EDIT")
        rig.data.edit_bones["Head"].use_connect = False
        rig.data.edit_bones["Head"].parent = rig.data.edit_bones["Base"]
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.view_layer.objects.active = robot
    elif variant == "changed_material":
        robot.data.materials[1].name = "Graphite_Replaced"


def add_preview_scene(robot, path):
    """Render a modest CPU-only original model image, never open a UI."""
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 2
    scene.render.resolution_x = scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(path)
    scene.world = bpy.data.worlds.new("StudioWorld")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs[0].default_value = (.12, .16, .21, 1)
    scene.world.node_tree.nodes["Background"].inputs[1].default_value = .4
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -.006))
    floor = bpy.context.object
    floor.name = "PreviewFloor_NotExported"
    material = bpy.data.materials.new("PreviewFloorMaterial")
    material.diffuse_color = (.045, .065, .09, 1)
    floor.data.materials.append(material)
    for name, position, energy, size in (("Key", (2, -3, 4), 450, 4), ("Rim", (-2, 1, 3), 550, 3)):
        light_data = bpy.data.lights.new(name, "AREA")
        light_data.energy = energy
        light_data.shape = "DISK"
        light_data.size = size
        light = bpy.data.objects.new(name, light_data)
        scene.collection.objects.link(light)
        light.location = position
        light.rotation_euler = (Vector((0, 0, 1)) - light.location).to_track_quat("-Z", "Y").to_euler()
    camera_data = bpy.data.cameras.new("PreviewCamera")
    camera = bpy.data.objects.new("PreviewCamera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (3.1, -5.3, 2.8)
    camera.rotation_euler = (Vector((0, 0, .98)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 2.7
    scene.camera = camera
    bpy.ops.render.render(write_still=True)


def create_subset_selection_fixture(output_dir):
    """A selected mesh must not capture a sibling via its auto-added rig."""
    robot, rig = build_robot(ordered_slots=True)
    sibling = robot.copy()
    sibling.data = robot.data.copy()
    sibling.name = "Sibling_NotSelected"
    sibling.location.x = 3
    bpy.context.scene.collection.objects.link(sibling)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action="DESELECT")
    robot.select_set(True)
    bpy.context.view_layer.objects.active = robot
    before = addon.collect_snapshot([robot], asset_name="subset_selection")
    assert [mesh["name"] for mesh in before["meshes"]] == ["Robot"]
    whole_hierarchy = addon.collect_snapshot([rig])
    assert {mesh["name"] for mesh in whole_hierarchy["meshes"]} == {"Robot", "Sibling_NotSelected"}
    target = output_dir / "subset_selection.fbx"
    actual = addon.export_audited(target, [robot], overwrite=True)
    assert [mesh["name"] for mesh in actual["meshes"]] == ["Robot"], "Snapshot captured an unselected sibling"
    assert addon.collect_snapshot([robot], asset_name="subset_selection") == before
    assert [obj.name for obj in bpy.context.selected_objects] == ["Robot"]
    assert bpy.context.view_layer.objects.active == robot
    actual["metadata"]["fixture"] = "Original procedural robot; unselected sibling shares the same armature"
    actual["metadata"]["regression"] = "Resolve export selection once before collecting the snapshot"
    addon.write_snapshot(actual, target.with_suffix(".source.json"))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(target), use_anim=False)
    imported_meshes = sorted(obj.name for obj in bpy.data.objects if obj.type == "MESH")
    assert imported_meshes == ["Robot"], "Actual FBX contains an unselected sibling: " + repr(imported_meshes)
    row = {"variant": "subset_selection", "fbx": target.name, "source": target.with_suffix(".source.json").name,
           "size_m": [1.0, .6, 2.0], "sha256": actual["artifact_sha256"],
           "round_trip_meshes": imported_meshes}
    print("EXPORTLENS_SUBSET_REGRESSION_PASSED " + json.dumps(row), flush=True)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("F:/CodexTemp/ExportLens/fixtures"))
    parser.add_argument("--blend-dir", type=Path, default=Path("F:/BlenderOutput/ExportLens"))
    parser.add_argument("--render", action="store_true")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--additional-controls", action="store_true",
                      help="Only add ordered material controls; preserve existing artifacts and hashes")
    mode.add_argument("--subset-selection-only", action="store_true",
                      help="Only add the shared-rig selection regression; preserve other artifacts")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.blend_dir.mkdir(parents=True, exist_ok=True)
    addon.register()
    assert hasattr(bpy.types, "EXPORTLENS_PT_panel"), "Add-on registration failed"
    addon.unregister()
    assert not hasattr(bpy.types, "EXPORTLENS_PT_panel"), "Add-on unregistration failed"
    results = []
    if args.additional_controls or args.subset_selection_only:
        manifest_path = args.output_dir / "fixture_manifest.json"
        if manifest_path.exists():
            results = json.loads(manifest_path.read_text(encoding="utf-8"))["fixtures"]
        variants = () if args.subset_selection_only else ("ordered_slots", "cm_ordered_slots")
    else:
        variants = ("good", "cm_units", "lost_shapes", "reparented_bone", "changed_material", "ordered_slots", "cm_ordered_slots")
    for variant in variants:
        unit = .01 if variant in {"cm_units", "cm_ordered_slots"} else 1.0
        robot, rig = build_robot(unit, ordered_slots=variant in {"ordered_slots", "cm_ordered_slots"})
        baseline = addon.collect_snapshot([rig], asset_name=variant)
        assert len(baseline["meshes"]) == 1
        mesh = baseline["meshes"][0]
        assert mesh["name"] == "Robot"
        assert mesh["blend_shapes"] == ["Smile", "Blink"]
        assert mesh["materials"] == ["Mint", "Graphite"]
        assert mesh["bones"] == [{"name": "Base", "parent": None}, {"name": "Chest", "parent": "Base"}, {"name": "Head", "parent": "Chest"}]
        physical_size = [round(value * unit, 6) for value in mesh["bounds_size"]]
        assert physical_size == [1.0, .6, 2.0], physical_size
        if variant in {"good", "cm_units"}:
            blend_path = args.blend_dir / ("ExportLens_Robot" + ("_Centimeters" if unit == .01 else "") + ".blend")
            bpy.ops.wm.save_as_mainfile(filepath=str(blend_path), check_existing=False)
        mutate(robot, rig, variant)
        source_before = addon.collect_snapshot([rig], asset_name=variant)
        selection_before = sorted(obj.name for obj in bpy.context.selected_objects)
        active_before = bpy.context.view_layer.objects.active
        target = args.output_dir / (variant + ".fbx")
        actual = addon.export_audited(target, [rig], overwrite=True)
        try:
            addon.export_audited(target, [rig], overwrite=False)
        except FileExistsError:
            pass
        else:
            raise AssertionError("Export overwrote existing output without authorization")
        source_after = addon.collect_snapshot([rig], asset_name=variant)
        assert source_before == source_after, "Export changed model data"
        assert selection_before == sorted(obj.name for obj in bpy.context.selected_objects), "Export changed selection"
        assert active_before == bpy.context.view_layer.objects.active, "Export changed active object"
        # The pipeline defect is deliberately introduced after baseline capture.
        # Associate the unchanged expected source with the actual defective FBX.
        actual["meshes"] = copy.deepcopy(baseline["meshes"])
        actual["metadata"]["fixture"] = "Original procedural block robot; no third-party assets"
        actual["metadata"]["intentional_pipeline_defect"] = variant if variant in {"lost_shapes", "reparented_bone", "changed_material"} else None
        addon.write_snapshot(actual, target.with_suffix(".source.json"))
        assert actual["artifact_sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
        row = {"variant": variant, "fbx": target.name, "source": target.with_suffix(".source.json").name,
               "size_m": physical_size, "sha256": actual["artifact_sha256"]}
        results = [old for old in results if old["variant"] != variant] + [row]
        print("EXPORTLENS_FIXTURE " + json.dumps(row), flush=True)
    if not args.additional_controls:
        row = create_subset_selection_fixture(args.output_dir)
        results = [old for old in results if old["variant"] != "subset_selection"] + [row]
    if args.render:
        robot, rig = build_robot()
        add_preview_scene(robot, args.blend_dir / "robot_preview.png")
    manifest = {"generator": "tools/create_fixture.py", "blender": bpy.app.version_string,
                "tests": ["addon_register_unregister", "baseline_contract", "physical_dimensions", "export_preserves_source_data",
                          "export_restores_selection", "overwrite_guard", "artifact_hash_matches"]
                         + (["subset_selection_real_fbx_round_trip"] if any(row["variant"] == "subset_selection" for row in results) else []),
                "fixtures": results}
    addon.write_snapshot(manifest, args.output_dir / "fixture_manifest.json")
    print("EXPORTLENS_FIXTURE_TESTS_PASSED " + str(len(results)), flush=True)


if __name__ == "__main__":
    main()
