using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace ExportLens.Editor
{
    /// <summary>Only run inside a disposable project. Produces evidence without opening an Editor window.</summary>
    public static class BatchIntegration
    {
        [Serializable]
        private sealed class CaptureEvidence
        {
            public string fixture;
            public string asset_path;
            public string snapshot;
            public int mesh_count;
            public bool importer_unchanged;
            public bool active_scene_unchanged;
        }

        [Serializable]
        private sealed class BatchEvidence
        {
            public bool success;
            public string unity_version;
            public string utc_finished;
            public string error;
            public CaptureEvidence[] captures;
        }

        public static void Run()
        {
            string output = Argument("-exportLensOutput");
            var evidence = new BatchEvidence { unity_version = Application.unityVersion };
            var captures = new List<CaptureEvidence>();
            int exitCode = 1;
            try
            {
                string fixtures = Argument("-exportLensFixtures");
                string baselineName = Argument("-exportLensBaseline", "ordered_slots.fbx");
                if (string.IsNullOrEmpty(output) || string.IsNullOrEmpty(fixtures))
                    throw new ArgumentException("Required arguments: -exportLensFixtures <folder> -exportLensOutput <folder>.");
                if (!Directory.Exists(fixtures)) throw new DirectoryNotFoundException(fixtures);
                Directory.CreateDirectory(output);
                string[] sourceFiles = Directory.GetFiles(fixtures, "*.fbx", SearchOption.TopDirectoryOnly).OrderBy(path => path, StringComparer.Ordinal).ToArray();
                if (sourceFiles.Length == 0) throw new InvalidOperationException("No .fbx fixtures were found.");
                foreach (string source in sourceFiles)
                {
                    string name = Path.GetFileNameWithoutExtension(source);
                    string assetPath = CopyFixture(source, name);
                    Capture(name, assetPath, output, captures);
                }
                if (!string.Equals(Argument("-exportLensCaptureOnly"), "true", StringComparison.OrdinalIgnoreCase))
                {
                    string baseline = Path.Combine(fixtures, baselineName);
                    if (!File.Exists(baseline)) throw new FileNotFoundException("Baseline FBX was not found.", baseline);

                    string scalePath = CopyFixture(baseline, "wrong_scale");
                    var scaleImporter = (ModelImporter)AssetImporter.GetAtPath(scalePath);
                    scaleImporter.globalScale = 0.01f;
                    scaleImporter.SaveAndReimport();
                    Capture("wrong_scale", scalePath, output, captures);

                    string shapesPath = CopyFixture(baseline, "missing_blend_shapes");
                    var shapesImporter = (ModelImporter)AssetImporter.GetAtPath(shapesPath);
                    shapesImporter.importBlendShapes = false;
                    shapesImporter.SaveAndReimport();
                    Capture("missing_blend_shapes", shapesPath, output, captures);
                }

                evidence.success = true;
                exitCode = 0;
                Debug.Log("EXPORTLENS_BATCH_SUCCESS: " + captures.Count + " imported FBX snapshots captured.");
            }
            catch (Exception exception)
            {
                evidence.error = exception.ToString();
                Debug.LogException(exception);
            }
            finally
            {
                evidence.utc_finished = DateTime.UtcNow.ToString("O");
                evidence.captures = captures.ToArray();
                if (!string.IsNullOrEmpty(output))
                {
                    Directory.CreateDirectory(output);
                    File.WriteAllText(Path.Combine(output, "unity-batch-result.json"), JsonUtility.ToJson(evidence, true), new UTF8Encoding(false));
                }
                EditorApplication.Exit(exitCode);
            }
        }

        private static string CopyFixture(string source, string caseName)
        {
            string folder = "Assets/ExportLensFixtures/" + caseName;
            string absoluteFolder = Path.GetFullPath(Path.Combine(Application.dataPath, "..", folder));
            Directory.CreateDirectory(absoluteFolder);
            string destination = folder + "/" + Path.GetFileName(source);
            File.Copy(source, Path.Combine(absoluteFolder, Path.GetFileName(source)), true);
            AssetDatabase.ImportAsset(destination, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
            return destination;
        }

        private static void Capture(string name, string assetPath, string output, List<CaptureEvidence> captures)
        {
            string metaPath = Path.GetFullPath(Path.Combine(Application.dataPath, "..", assetPath + ".meta"));
            string beforeImporter = File.ReadAllText(metaPath);
            int beforeScene = SceneManager.GetActiveScene().handle;
            var snapshot = SnapshotCollector.Collect(assetPath);
            if (beforeImporter != File.ReadAllText(metaPath))
                throw new InvalidOperationException("Collection unexpectedly changed importer metadata: " + assetPath);
            if (beforeScene != SceneManager.GetActiveScene().handle)
                throw new InvalidOperationException("Collection unexpectedly changed the active scene.");
            string destination = Path.Combine(output, name + ".unity.json");
            File.WriteAllText(destination, snapshot.ToJson(), new UTF8Encoding(false));
            captures.Add(new CaptureEvidence
            {
                fixture = name,
                asset_path = assetPath,
                snapshot = Path.GetFileName(destination),
                mesh_count = snapshot.Meshes.Length,
                importer_unchanged = true,
                active_scene_unchanged = true
            });
            Debug.Log("EXPORTLENS_CAPTURED: " + name + " (" + snapshot.Meshes.Length + " meshes)");
        }

        private static string Argument(string name, string fallback = null)
        {
            string[] arguments = Environment.GetCommandLineArgs();
            for (int i = 0; i < arguments.Length - 1; i++)
                if (arguments[i] == name) return arguments[i + 1];
            return fallback;
        }
    }
}
