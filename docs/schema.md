# Snapshot v1

Both collectors write UTF-8 JSON. The comparator expects a Blender source followed by a Unity target. Names are case-sensitive. Collectors write diagnostic metadata; the comparator does not compare that metadata for equality.

## Root fields

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | Exactly `1`. |
| `producer` | string | `blender` for the source; `unity` for the target. |
| `producer_version` | nonempty string | Actual application version. |
| `asset_name` | nonempty string | Human-readable asset label. |
| `source_file` | nonempty string | Input filename only, without the absolute directory. |
| `artifact_sha256` | 64-character hex string or `null` | Hash of the exported/imported FBX bytes. A missing hash cannot establish that both captures describe the same artifact. |
| `units` | object | Native dimension interpretation, below. |
| `meshes` | nonempty array | Mesh records. An empty capture cannot pass. |
| `metadata` | object, optional | Producer diagnostics such as exporter/importer options. Not compared for equality. Optional `warnings` must be an array of strings and is shown as informational capture scope notes. |

`units.meters_per_unit` is a finite positive number. Blender records its scene scale; Unity records `1` because the target collector measures imported world dimensions in meters. `units.up_axis` is `Z` for Blender and `Y` for Unity. Other axes are unsupported by v1.

`source_file` must be written as a basename by a collector. Consumers should still review third-party snapshots before sharing them: manually authored JSON can contain arbitrary strings.

## Mesh records

| Field | Type | Meaning |
| --- | --- | --- |
| `name` | nonempty string | Logical object/renderer name, unique within a snapshot. Primary match key. |
| `path` | string | Hierarchy path for diagnostics. Not a match key and not an absolute filesystem path. |
| `bounds_size` | array of three numbers | Nonnegative finite axis-aligned world extent in the producer's native axes and units. |
| `vertex_count` | positive integer | Base/imported mesh vertex count. Informational when different. |
| `materials` | ordered array of string or `null` | Material slot names; `null` means an empty slot. Order matters. |
| `blend_shapes` | array of nonempty unique strings | Channel names excluding Blender's Basis shape. |
| `bones` | array of bone records | Source armature bones or Unity import hierarchy candidates. Empty for unrigged meshes. |

A bone record is `{"name": "Spine", "parent": "Root"}`. A root has `"parent": null`.

Blender bone names must be unique for each mesh. Each source parent must exist in the same record list, and the hierarchy must be acyclic. Unity may include non-bone wrapper transforms. The comparator walks these parent links to the nearest known source bone. Ambiguity involving a source bone or its parent chain is an error; it does not guess between same-named nodes.

Example source snapshot (illustrative; `null` identity will produce a review finding):

```json
{
  "schema_version": 1,
  "producer": "blender",
  "producer_version": "5.2.3",
  "asset_name": "SyntheticRig",
  "source_file": "SyntheticRig.blend",
  "artifact_sha256": null,
  "units": {"meters_per_unit": 1.0, "up_axis": "Z"},
  "meshes": [
    {
      "name": "Body",
      "path": "SyntheticRig/Body",
      "bounds_size": [1.0, 0.4, 2.0],
      "vertex_count": 8,
      "materials": ["BodyMaterial", null],
      "blend_shapes": ["Smile"],
      "bones": [
        {"name": "Root", "parent": null},
        {"name": "Spine", "parent": "Root"}
      ]
    }
  ],
  "metadata": {"note": "Synthetic example; not a complete model"}
}
```

The equivalent Unity bounds would be `[1.0, 2.0, 0.4]` when no physical dimension changed. That axis permutation is expected.

## Comparison configuration

All fields are optional. Unknown fields are rejected to catch misspellings.

| Field | Default | Constraint |
| --- | --- | --- |
| `mesh_map` | `{}` | Source-name → target-name object; known source names and one-to-one target mapping. |
| `absolute_tolerance_m` | `0.001` | Finite nonnegative meters. |
| `relative_tolerance` | `0.01` | Finite nonnegative fraction, so `0.01` means 1%. |

For each normalized source axis `s` and target axis `t`, a size difference fails when:

```text
abs(s - t) > absolute_tolerance_m + relative_tolerance * abs(s)
```

The additive absolute allowance helps near-zero dimensions. It is not an angle or deformation tolerance.

## Report JSON

The report contains `schema_version`, `status`, `summary`, source/target identity summaries, `tolerances`, `checks`, `findings`, and explicit `limitations`.

A finding has `severity` (`error`, `warning`, or `info`), a stable-style uppercase `code`, `subject`, `message`, `expected`, `actual`, a remediation `hint`, and `mesh`. The mesh key is the source name for matched/expected meshes, the target name for an unmatched added mesh, or `null` for artifact/capture-wide findings. This explicit key prevents slash-containing mesh names from being mistaken for bone-path prefixes. `CAPTURE_SCOPE_NOTE` carries collector warnings as information; it does not certify the omitted property or automatically change the report to review. Report states are:

- `fail`: at least one error.
- `review`: warnings exist without errors.
- `pass`: neither errors nor warnings. Informational findings are allowed.

Consumers should check the overall state and exit code. A green dimensions row cannot override a failed FBX identity check elsewhere in the report. v0.1 report fields should be treated as an initial API; preserve the schema version when archiving evidence.
