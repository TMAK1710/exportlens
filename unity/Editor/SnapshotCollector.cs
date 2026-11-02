using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace ExportLens.Editor
{
    /// <summary>Read-only extraction from a model imported by Unity. Never reimports or modifies its importer.</summary>
    public static class SnapshotCollector
    {
        public sealed class BoneRecord
        {
            public string Name;
            public string Parent;
        }

        public sealed class MeshRecord
        {
            public string Name;
            public string Path;
            public float[] BoundsSize;
            public int VertexCount;
            public string[] Materials;
            public string[] BlendShapes;
            public BoneRecord[] Bones;
        }

        public sealed class Snapshot
        {
            public string AssetName;
            public string SourceFile;
            public string ArtifactSha256;
            public MeshRecord[] Meshes;
            public float GlobalScale;
            public float FileScale;
            public bool UseFileScale;
            public bool ImportBlendShapes;
            public bool OptimizeGameObjects;
            public bool BakeAxisConversion;
            public string AnimationType;

            public string ToJson()
            {
                var json = new StringBuilder();
                json.Append("{\n  \"schema_version\": 1,\n  \"producer\": \"unity\",\n  \"producer_version\": ");
                AppendString(json, Application.unityVersion);
                json.Append(",\n  \"asset_name\": "); AppendString(json, AssetName);
                json.Append(",\n  \"source_file\": "); AppendString(json, SourceFile);
                json.Append(",\n  \"artifact_sha256\": "); AppendString(json, ArtifactSha256);
                json.Append(",\n  \"units\": {\"meters_per_unit\": 1, \"up_axis\": \"Y\"},\n  \"meshes\": [");
                for (int index = 0; index < Meshes.Length; index++)
                {
                    var mesh = Meshes[index];
                    if (index > 0) json.Append(',');
                    json.Append("\n    {\"name\": "); AppendString(json, mesh.Name);
                    json.Append(", \"path\": "); AppendString(json, mesh.Path);
                    json.Append(", \"bounds_size\": [");
                    for (int axis = 0; axis < 3; axis++)
                    {
                        if (axis > 0) json.Append(", ");
                        json.Append(mesh.BoundsSize[axis].ToString("R", CultureInfo.InvariantCulture));
                    }
                    json.Append("], \"vertex_count\": ").Append(mesh.VertexCount);
                    json.Append(", \"materials\": "); AppendStrings(json, mesh.Materials);
                    json.Append(", \"blend_shapes\": "); AppendStrings(json, mesh.BlendShapes);
                    json.Append(", \"bones\": [");
                    for (int boneIndex = 0; boneIndex < mesh.Bones.Length; boneIndex++)
                    {
                        if (boneIndex > 0) json.Append(", ");
                        json.Append("{\"name\": "); AppendString(json, mesh.Bones[boneIndex].Name);
                        json.Append(", \"parent\": "); AppendString(json, mesh.Bones[boneIndex].Parent);
                        json.Append('}');
                    }
                    json.Append("]}");
                }
                json.Append("\n  ],\n  \"metadata\": {\n    \"collector\": \"ExportLens 0.1.0\",\n    \"bounds_method\": \"rest_mesh_vertices_world_matrix\",\n    \"mesh_name_source\": \"renderer_game_object_name\",\n    \"import_settings\": {\"global_scale\": ");
                json.Append(GlobalScale.ToString("R", CultureInfo.InvariantCulture));
                json.Append(", \"file_scale\": ").Append(FileScale.ToString("R", CultureInfo.InvariantCulture));
                json.Append(", \"use_file_scale\": ").Append(UseFileScale ? "true" : "false");
                json.Append(", \"import_blend_shapes\": ").Append(ImportBlendShapes ? "true" : "false");
                json.Append(", \"optimize_game_objects\": ").Append(OptimizeGameObjects ? "true" : "false");
                json.Append(", \"bake_axis_conversion\": ").Append(BakeAxisConversion ? "true" : "false");
                json.Append(", \"animation_type\": "); AppendString(json, AnimationType);
                json.Append("}\n  }\n}\n");
                return json.ToString();
            }
        }

        public static Snapshot Collect(string assetPath)
        {
            if (string.IsNullOrWhiteSpace(assetPath) || !assetPath.EndsWith(".fbx", StringComparison.OrdinalIgnoreCase))
                throw new ArgumentException("Select an imported .fbx asset in the Project window.", nameof(assetPath));
            var importer = AssetImporter.GetAtPath(assetPath) as ModelImporter;
            var model = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
            if (importer == null || model == null)
                throw new InvalidOperationException("The selected path is not an imported FBX model: " + assetPath);
            if (importer.optimizeGameObjects)
                throw new InvalidOperationException("Optimize Game Objects hides transform hierarchy. ExportLens cannot verify bones on this asset. Disable it on a test copy if hierarchy checks are needed.");

            var preview = EditorSceneManager.NewPreviewScene();
            GameObject instance = null;
            try
            {
                instance = (GameObject)PrefabUtility.InstantiatePrefab(model, preview);
                if (instance == null) throw new InvalidOperationException("Could not instantiate the imported FBX in a preview scene.");
                var allNodes = instance.GetComponentsInChildren<Transform>(true);
                var boneCandidates = allNodes.Select(node => new BoneRecord
                {
                    Name = node.name,
                    Parent = node == instance.transform || node.parent == null ? null : node.parent.name
                }).ToArray();
                var records = new List<MeshRecord>();
                foreach (var renderer in instance.GetComponentsInChildren<Renderer>(true))
                {
                    Mesh mesh;
                    var skinned = renderer as SkinnedMeshRenderer;
                    if (skinned != null) mesh = skinned.sharedMesh;
                    else
                    {
                        var filter = renderer.GetComponent<MeshFilter>();
                        mesh = filter == null ? null : filter.sharedMesh;
                    }
                    if (mesh == null) continue;
                    var vertices = mesh.vertices;
                    if (vertices.Length == 0)
                        throw new InvalidOperationException("Mesh has no readable rest vertices: " + renderer.name);
                    var first = renderer.localToWorldMatrix.MultiplyPoint3x4(vertices[0]);
                    var bounds = new Bounds(first, Vector3.zero);
                    foreach (var vertex in vertices)
                        bounds.Encapsulate(renderer.localToWorldMatrix.MultiplyPoint3x4(vertex));
                    var size = bounds.size;
                    if (!Finite(size.x) || !Finite(size.y) || !Finite(size.z))
                        throw new InvalidOperationException("Mesh bounds contain non-finite values: " + renderer.name);
                    var shapes = new string[mesh.blendShapeCount];
                    for (int i = 0; i < shapes.Length; i++) shapes[i] = mesh.GetBlendShapeName(i);
                    records.Add(new MeshRecord
                    {
                        Name = renderer.gameObject.name,
                        Path = HierarchyPath(renderer.transform, instance.transform),
                        BoundsSize = new[] { size.x, size.y, size.z },
                        VertexCount = mesh.vertexCount,
                        Materials = renderer.sharedMaterials.Select(material => material == null ? null : material.name).ToArray(),
                        BlendShapes = shapes,
                        Bones = skinned == null ? Array.Empty<BoneRecord>() : boneCandidates
                    });
                }
                if (records.Count == 0) throw new InvalidOperationException("The selected FBX contains no mesh renderers.");
                return new Snapshot
                {
                    AssetName = Path.GetFileNameWithoutExtension(assetPath),
                    SourceFile = Path.GetFileName(assetPath),
                    ArtifactSha256 = HashFile(PhysicalAssetPath(assetPath)),
                    Meshes = records.OrderBy(record => record.Path, StringComparer.Ordinal).ToArray(),
                    GlobalScale = importer.globalScale,
                    FileScale = importer.fileScale,
                    UseFileScale = importer.useFileScale,
                    ImportBlendShapes = importer.importBlendShapes,
                    OptimizeGameObjects = importer.optimizeGameObjects,
                    BakeAxisConversion = importer.bakeAxisConversion,
                    AnimationType = importer.animationType.ToString()
                };
            }
            finally
            {
                if (instance != null) UnityEngine.Object.DestroyImmediate(instance);
                EditorSceneManager.ClosePreviewScene(preview);
            }
        }

        public static void Write(string assetPath, string destination)
        {
            var snapshot = Collect(assetPath);
            var folder = Path.GetDirectoryName(Path.GetFullPath(destination));
            Directory.CreateDirectory(folder);
            File.WriteAllText(destination, snapshot.ToJson(), new UTF8Encoding(false));
        }

        private static bool Finite(float value) => !float.IsNaN(value) && !float.IsInfinity(value);

        private static string PhysicalAssetPath(string assetPath)
        {
            if (assetPath.StartsWith("Packages/", StringComparison.Ordinal))
            {
                var package = UnityEditor.PackageManager.PackageInfo.FindForAssetPath(assetPath);
                if (package == null) throw new FileNotFoundException("Could not resolve the selected package asset.", assetPath);
                return Path.Combine(package.resolvedPath, assetPath.Substring(package.assetPath.Length).TrimStart('/', '\\'));
            }
            return Path.GetFullPath(Path.Combine(Application.dataPath, "..", assetPath));
        }

        private static string HierarchyPath(Transform node, Transform root)
        {
            var parts = new List<string>();
            for (var current = node; current != null; current = current.parent)
            {
                parts.Add(current.name);
                if (current == root) break;
            }
            parts.Reverse();
            return string.Join("/", parts);
        }

        private static string HashFile(string path)
        {
            using (var stream = File.OpenRead(path))
            using (var algorithm = SHA256.Create())
                return BitConverter.ToString(algorithm.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
        }

        private static void AppendStrings(StringBuilder json, string[] values)
        {
            json.Append('[');
            for (int i = 0; i < values.Length; i++)
            {
                if (i > 0) json.Append(", ");
                AppendString(json, values[i]);
            }
            json.Append(']');
        }

        private static void AppendString(StringBuilder json, string value)
        {
            if (value == null) { json.Append("null"); return; }
            json.Append('"');
            foreach (char character in value)
            {
                switch (character)
                {
                    case '"': json.Append("\\\""); break;
                    case '\\': json.Append("\\\\"); break;
                    case '\b': json.Append("\\b"); break;
                    case '\f': json.Append("\\f"); break;
                    case '\n': json.Append("\\n"); break;
                    case '\r': json.Append("\\r"); break;
                    case '\t': json.Append("\\t"); break;
                    default:
                        if (character < 32) json.Append("\\u").Append(((int)character).ToString("x4"));
                        else json.Append(character);
                        break;
                }
            }
            json.Append('"');
        }
    }
}
