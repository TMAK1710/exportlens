using System;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace ExportLens.Editor
{
    public sealed class ExportLensWindow : EditorWindow
    {
        private UnityEngine.Object model;
        private string lastOutput;
        private string lastMessage;
        private bool failed;

        [MenuItem("Tools/ExportLens/Snapshot FBX")]
        public static void Open()
        {
            var window = GetWindow<ExportLensWindow>("ExportLens");
            window.minSize = new Vector2(400, 260);
            window.model = Selection.activeObject;
        }

        private void OnGUI()
        {
            EditorGUILayout.LabelField("Imported FBX snapshot", EditorStyles.boldLabel);
            EditorGUILayout.HelpBox("Capture imported rest dimensions, material slots, blend shapes and bone hierarchy. Compare this JSON with the Blender snapshot using ExportLens. Source assets and importer settings are read only.", MessageType.Info);
            model = EditorGUILayout.ObjectField("FBX model", model, typeof(GameObject), false);
            var path = model == null ? null : AssetDatabase.GetAssetPath(model);
            bool valid = !string.IsNullOrEmpty(path) && path.EndsWith(".fbx", StringComparison.OrdinalIgnoreCase);
            using (new EditorGUI.DisabledScope(!valid))
            {
                if (GUILayout.Button("Capture snapshot JSON", GUILayout.Height(30)))
                {
                    var destination = EditorUtility.SaveFilePanel("Save ExportLens Unity snapshot", "", Path.GetFileNameWithoutExtension(path) + ".unity.json", "json");
                    if (!string.IsNullOrEmpty(destination))
                    {
                        try
                        {
                            SnapshotCollector.Write(path, destination);
                            lastOutput = destination;
                            lastMessage = "Snapshot saved. Compare it with the matching Blender JSON.";
                            failed = false;
                        }
                        catch (Exception exception)
                        {
                            lastMessage = exception.Message;
                            failed = true;
                            Debug.LogException(exception);
                        }
                    }
                }
            }
            if (!valid) EditorGUILayout.HelpBox("Choose one .fbx model asset from the Project window.", MessageType.None);
            if (!string.IsNullOrEmpty(lastMessage)) EditorGUILayout.HelpBox(lastMessage, failed ? MessageType.Error : MessageType.Info);
            if (!string.IsNullOrEmpty(lastOutput))
            {
                EditorGUILayout.SelectableLabel(lastOutput, EditorStyles.wordWrappedLabel, GUILayout.Height(40));
                if (GUILayout.Button("Reveal snapshot")) EditorUtility.RevealInFinder(lastOutput);
            }
        }
    }
}
