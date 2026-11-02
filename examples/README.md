# Recorded integration examples

All model files here are an original procedural block robot, created for ExportLens and covered by the repository's MIT license. No purchased avatar or production project assets are included.

- `fixtures/`: actual exported FBX files, paired Blender snapshots, a source `.blend`, and the generator manifest.
- `captures/`: actual Unity 2022.3.22f1 snapshots of those FBX files.
- `reports/`: offline HTML/JSON comparison results and the asserted integration summary.

From the checkout root, replay the recorded results without either editor:

```sh
python tools/verify_integration.py --fixtures examples/fixtures --captures examples/captures --output reports/replay
```

`ordered_slots` and `cm_ordered_slots` are pass controls. The original `good` and `cm_units` names are retained for provenance: their material slots actually reordered on import, so their correct result is review. `subset_selection` checks that selecting one skinned mesh does not export or capture an unselected sibling attached to the same rig.

`lost_shapes`, `reparented_bone` and `changed_material` deliberately retain the pre-change expected properties in their source JSON while hashing a genuinely altered FBX. These model baseline-versus-deliverable changes. They are not evidence that Unity caused the changes. `wrong_scale` and `missing_blend_shapes` use `ordered_slots.fbx` with actual changed Unity import settings; their matching source snapshot is `ordered_slots.source.json`.

Full reproduction steps and validation boundaries are in [the test record](../docs/testing.md).
