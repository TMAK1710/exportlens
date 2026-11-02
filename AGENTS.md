# ExportLens workspace

Build a small open-source Blender -> Unity FBX consistency checker. Read only the files necessary for the change. Do not touch existing production projects or foreground desktop apps. Use background Blender and Unity -batchmode -nographics in isolated temporary projects. Run expensive processes sequentially with low priority and limited workers. Honor the user's output/temp locations. No publication or account changes are implicit in a local build request.

## Snapshot v1 contract

JSON root: schema_version=1, producer="blender"|"unity", producer_version, asset_name, source_file (basename only), artifact_sha256 (FBX hash or null), units={meters_per_unit:number, up_axis:"Z"|"Y"}, meshes:[...], metadata:{... optional}.

Each mesh: name (logical object/renderer name), path (hierarchy diagnostic string), bounds_size:[x,y,z] in producer-native axes/units, vertex_count:int, materials:[string|null] ordered slots, blend_shapes:[string], bones:[{name:string,parent:string|null}]. Blender collects source base/basis geometry, world dimensions and all bones of its armature. Unity collects imported rest meshes, world bounds, ordered sharedMaterials, blendShape names, and candidate bone transforms under the model. Names must be unique per mesh; comparison fails closed on duplicate/ambiguous names. Blender Z-up bounds are mapped to Unity Y-up as [x,z,y] then converted to meters. Unity uses meters_per_unit=1. Do not compare raw native unit scales for equality. Geometry checks use 1mm + 1% relative default tolerance. Vertex count changes are informational due to UV/normal splits. Shader/color/texture fidelity, animation, skin weights and actual deformation are explicitly outside v0.1.

Core matches exact unique mesh names; optional config.mesh_map maps Blender names to Unity names. It may normalize unique blend shape prefixes ending in .<source name> and record that normalization. Bone comparison uses source bone names, ignoring Unity wrapper nodes when finding parent (collector should provide candidate parent links; comparator walks ancestors until a known source name). Added unused bone wrappers are informational. Material names/slots are compared exactly.

## Repository layout and validation

`exportlens/` contains zero-dependency Python comparison, CLI and escaped offline HTML. `blender_addon/` collects original geometry and paired FBX exports. `unity/` is the Editor-only UPM package. `examples/` contains original MIT fixtures and actual captures; altered baseline fixtures must stay explicitly identified. `tools/` contains isolated integration and local release helpers.

Resolve Blender selection once, preserve source data and selection, and refuse output overwrites by default. Unity collection must not modify import settings or the active scene. Run `python -m unittest discover -s tests -v` and `python tools/verify_integration.py --fixtures examples/fixtures --captures examples/captures --output reports/verification`. Code-only checks cannot replace real editor validation of collector changes. Do not publish private assets, raw machine logs, credentials or production snapshots.
