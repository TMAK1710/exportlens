# Reuse research and scope decision

Research date: **2026-11-02**. These primary sources informed the initial scope. This is a focused comparison, not an exhaustive search or a claim that no similar checker exists.

| Existing project / API | What it provides | Decision for ExportLens |
| --- | --- | --- |
| [Unity MeshSync DCC Plugins](https://github.com/Unity-Technologies/MeshSyncDCCPlugins) | DCC plugins, including Blender, for live model synchronization with Unity. The repository documents supported synchronization features and caveats. | Useful adjacent workflow. A live synchronization stack is more than a small file-based before/after audit needs; no MeshSync dependency is required. |
| [nomand/BlenderToUnity](https://github.com/nomand/BlenderToUnity) | Prepares nested Blender hierarchies with axis compensation for Unity export. Its README limits intended use to static content, excluding tested/intended support for armatures and animated objects. | Useful context for axis-related failures. ExportLens measures the result instead of modifying the hierarchy, and explicitly includes source bone and shape-channel presence checks. |
| [ccd775/BlenderSafeAvatarFbxExporter](https://github.com/ccd775/BlenderSafeAvatarFbxExporter) | Unity Editor exporter for bringing baked VRChat avatars into Blender, preserving selected pose/shape/skin/texture information and validating its export. | A related safety-focused tool in the reverse direction. Its exporter and dependencies do not replace source/target snapshots for a Blender → Unity import, so it is not directly bundled. |
| [Blender FBX export operator](https://docs.blender.org/api/current/bpy.ops.export_scene.html#bpy.ops.export_scene.fbx) | Native FBX export controls for scale, units, axes, modifiers, armatures and animation. | Use Blender's exporter instead of implementing an FBX writer. Audit settings and hash the resulting file. Check the API for the installed Blender version. |
| [Unity ModelImporter](https://docs.unity3d.com/2022.3/Documentation/ScriptReference/ModelImporter.html) and [fileScale](https://docs.unity3d.com/2022.3/Documentation/ScriptReference/ModelImporter-fileScale.html) | Unity's model-import API and the file unit scale. | Read the actual imported model and preserve importer diagnostics. Compare physical extents after conversion, not raw scale settings. |
| [Unity Mesh](https://docs.unity3d.com/2022.3/Documentation/ScriptReference/Mesh.html) | Imported vertex data, blend shape channels and related mesh information. | Use built-in Editor APIs rather than a third-party FBX parser. |

The chosen implementation consists of two thin collectors, a documented JSON boundary, and a standard-library Python comparator. This keeps the failure evidence inspectable, avoids coupling the comparator to a live editor, and makes reports shareable after sensitive names have been reviewed.

No source from the listed third-party projects is bundled merely by linking to it. Their names and trademarks belong to their owners. Blender and Unity remain required to produce real integration captures.

## What would be useful next

Further work should begin with a reproducible failure and an assessment of available libraries. Candidate extensions include opt-in per-vertex geometry checks, face-to-material mapping, explicit transform checks and richer evaluated-mesh capture. Each requires a stronger schema and its own fixtures; it should not silently expand the meaning of a v1 pass.
