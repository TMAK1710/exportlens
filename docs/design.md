# Design and limits

ExportLens separates editor-specific collection from comparison. Blender and Unity produce small JSON snapshots; the Python core compares those snapshots without importing either editor's libraries. Reports can therefore be regenerated and reviewed without opening the source project.

```text
Blender base geometry ── audited FBX export ── FBX ── Unity model importer
         │                                    │             │
         └── source.json + FBX hash             └── target.json + FBX hash
                            │                            │
                            └──── Python comparator ─────┘
                                      │
                                HTML + JSON report
```

## Identity before interpretation

Two similar filenames do not prove that the captures describe the same export. The audited Blender operation hashes the written FBX, and the Unity collector hashes the imported FBX. A mismatch fails. An absent hash requires review. A matching hash proves file identity between captures; it does not prove that the source scene was unchanged after export or that every property is represented in the snapshot.

## Dimensions and units

Source bounds are computed from base/Basis vertices transformed into Blender world space. Target bounds come from imported rest mesh geometry in Unity world space. Blender's `[x, y, z]` extent becomes `[x, z, y]`, then scene scale converts it to meters. Target values are also expressed in meters. The comparator deliberately does not compare native unit-scale settings for equality.

For example, 100 source units at 0.01 meters per unit and a 1-meter Unity extent agree. Reporting a mismatch solely because `0.01 != 1` would be incorrect.

An axis-aligned size is a coarse geometry measurement. A mirrored asset, a wrong pivot, an orientation error on symmetric geometry, or a vertex change that preserves the outer extent may pass this check. The permutation does not validate handedness or the whole transform matrix. Rotations are represented only through their effect on world bounds. Model origins are not compared.

The default additive tolerance is 1 mm + 1% of each source extent. Choose tighter settings only when the actual asset scale and pipeline precision justify them.

## Conservative matching

Meshes match by exact unique name, with an explicit one-to-one mapping for deliberate renames. The comparator does not pair equal-looking geometry by list index. If Unity merges, splits or renames renderers in an unexpected way, it reports missing/unmatched meshes or invalid names instead of inferring success.

Source bones match by name, with parent traversal through Unity wrapper transforms. Additional non-source nodes are tolerated. Duplicate relevant names, broken traversal or cycles prevent a trustworthy match. Structural success does not prove correct bone transforms, bind poses, weights, constraints or motion.

Shape matching checks channel presence. A unique dotted prefix can be normalized, and that action is reported. Extra target channels are informational. Channel names alone do not verify shape deltas, frame weights, expression quality or interaction between expressions.

Material slot count and ordered names are checked. A changed count is an error; names require review because intentional remaps are common. The snapshot does not contain face-to-slot indices, so identical slot lists do not prove that faces use the correct material. It also contains no shader graph, texture or color comparison.

## Base geometry, modifiers and pose

The Blender collector uses original/Basis geometry rather than the current deformed viewport result. Its audited exporter disables mesh modifier application to preserve shape channels, disables animation baking and exports the full armature bone list without generated leaf bones.

This has a deliberate boundary: a Subdivision, Mirror, Geometry Nodes or other geometry modifier is not certified. Nonzero shape weights and current bone poses are not baked into the source bounds. Collector metadata can describe such conditions; its warning strings appear as informational capture scope notes in the report, while metadata equality is not an implemented check. These notes do not automatically fail or require review. Read them and prepare a clean export copy when the evaluated result is the intended deliverable.

The Unity collector captures an imported FBX asset, not the user's scene arrangement. It does not change the import settings to make the audit pass. Optimized or stripped hierarchies and disabled blend-shape import can therefore be detected as missing data.

## Vertex counts

Blender and Unity may represent the same visible surface with different vertex counts. UV discontinuities, hard-normal edges and material boundaries can require vertex splitting. Counts are retained as evidence, but a difference is informational. Conversely, equal counts do not prove equal topology, normals or UVs.

## Privacy and supported use

There is no network client in the comparator and no upload step in the collectors. Source paths are reduced to basenames, while hierarchy/name data remains useful diagnostic information and can be sensitive. Review artifacts before publishing them. Do not attach a commercial avatar or a production model to a public issue without redistribution rights.

v0.1 targets local asset troubleshooting and reproducible export regression checks. It is not a model repair system, a visual-diff renderer, a runtime avatar validator, or a guarantee of FBX behavior across every Blender and Unity version. The [validation record](testing.md) lists the evidence that actually exists.
