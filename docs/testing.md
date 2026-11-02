# Validation record

Record date: **2026-11-02**.

Local environment: Windows, Python **3.13.12**, Blender **5.2.3 LTS**, Unity **2022.3.22f1**. Other declared-compatible versions are not automatically covered by these results; Unity 6 was not tested in this run.

This file separates comparator cases from real editor integration. A test is recorded as passed only after its command returns and its output is inspected. Screenshots are evidence of generated reports; they do not replace the underlying capture or test logs.

## Current run

The Python test run and all ten public FBX capture comparisons have returned with the expected results. Report screenshots were rendered and visually reviewed. This record covers rest-data export/import checks, not runtime deformation or visual fidelity.

| Layer | Environment / case | Result | Evidence |
| --- | --- | --- | --- |
| Python comparator | 37 unit and failure-mode cases | Passed | `python -m unittest discover -s tests -v`; includes meter conversion, bone-wrapper ambiguity, shapes/hash/slots, malformed input, numeric overflow, slash-containing mesh names, metadata scope notes, HTML escaping and CLI exit codes. |
| Blender source capture | Blender **5.2.3 LTS**, original block robot, 8 exported fixtures | Passed assertion families | [Fixture manifest](../examples/fixtures/fixture_manifest.json); 5 initial variants, 2 controls and the subset-selection case. Initial `EXPORTLENS_FIXTURE_TESTS_PASSED 5` and normal `Blender quit` log ending; the initial process exit code was not retained. Later control/subset runs retained exit code `0`. |
| Unity import/capture | Unity **2022.3.22f1**, isolated project, 10 cases | Passed | Real FBX import and snapshot capture; source `.meta` content and active scene were preserved. See [capture invariants](../examples/capture-evidence.json) and the recorded snapshots in `examples/captures`. |
| Pass controls | `ordered_slots`, `cm_ordered_slots`, `subset_selection` | All pass | Physical dimensions agree at meter and centimeter source scales; channels, bones and slots match. Subset selection excludes the unrelated sibling mesh. |
| Review controls | `good`, `cm_units`, `changed_material` | All expected review | Original material-order changes are retained as evidence; deliberate material rename also requires review. |
| Negative integration | `lost_shapes`, `reparented_bone`, `wrong_scale`, `missing_blend_shapes` | All expected fail | Exact expected non-informational finding sets are asserted by `tools/verify_integration.py`; see the [returned integration summary](../examples/reports/integration-summary.json). |
| Subset-selection regression | Two sibling meshes on one rig; select only `Robot` | Passed | Blender reimport and Unity capture contain only the selected mesh, two shape channels and matching FBX identity. Comparison passes with only the expected vertex-count note. |
| Report rendering | Overview, pass-control HTML, failure HTML | Passed visual review | [Overview](images/01-overview.png) (1280 × 960); [pass report](images/02-good-report.png) and [failure report](images/03-failure-report.png) are actual full-page HTML renders. No page JavaScript errors were observed. |

Screenshots use the original synthetic robot and actual report output. The overview combines the rendered fixture with the audit workflow; the report screenshots retain the real findings and scope limits.

The returned Blender run covers add-on registration/unregistration, the baseline snapshot contract, physical dimensions at meter and centimeter scene scales, preservation of model data, restoration of selection/active object, refusal to overwrite without the explicit overwrite option, and matching written-FBX SHA-256. The synthetic mesh is 1.0 × 0.6 × 2.0 meters in Blender axes, has `Smile`/`Blink`, three bones and two material slots. The optional preview was rendered with CPU Cycles at 720 × 720. These results establish source collection and export behavior, not Unity import fidelity.

The fixture command is:

```powershell
& "<Blender executable>" --background --factory-startup -t 2 --python tools/create_fixture.py -- --render
```

Omit `--render` for the faster assertion/export run. Set `--output-dir` and `--blend-dir` after the `--` separator when the default F-drive locations are unsuitable. Logs and generated test projects are working artifacts, not required dependencies of the distributed tool.

Two extra controls, `ordered_slots` and `cm_ordered_slots`, were generated in a subsequent Blender run with process exit code `0`. Original fixture hashes were retained and checked. The original `good`/`cm_units` files are preserved as observed material-order review cases rather than rewritten to look like a pass. Both extra controls passed the final Unity comparison.

The imported robot measured approximately `[1.0, 1.99999988, 0.6]` meters in Unity axes, matching Blender's `[1.0, 0.6, 2.0]` after normalization. The centimeter case reported FBX `file_scale = 0.01` and the same physical extent. The importer split 120 source vertices into 360 imported vertices; this was correctly informational. `Smile`/`Blink` and the `Base → Chest → Head` bone chain were retained.

The additional subset-selection run verifies that automatically including a required armature does not also export an unrelated sibling mesh. Its Blender process returned exit code `0`; the final Unity capture and comparison passed. The collector's metadata-file and active-scene preservation checks also passed.

The original material order `[Mint, Graphite]` arrived as `[Graphite, Mint]`, yielding `MATERIAL_SLOT_NAMES_CHANGED` and review. This is observed slot reordering, not evidence that surface appearance broke. The pass controls use source face/slot ordering that survives this pipeline. Slot comparison does not inspect face assignments.

| Recorded case | Expected state | Exact non-informational findings |
| --- | --- | --- |
| `ordered_slots`, `cm_ordered_slots` | `pass` | None |
| `subset_selection` | `pass` | None |
| `good`, `cm_units`, `changed_material` | `review` | `MATERIAL_SLOT_NAMES_CHANGED` |
| `lost_shapes` | `fail` | `BLEND_SHAPE_MISSING`, `MATERIAL_SLOT_NAMES_CHANGED` |
| `reparented_bone` | `fail` | `BONE_PARENT_CHANGED`, `MATERIAL_SLOT_NAMES_CHANGED` |
| `wrong_scale` | `fail` | `BOUNDS_SIZE_CHANGED` |
| `missing_blend_shapes` | `fail` | `BLEND_SHAPE_MISSING` |

## Comparator tests

Run from the repository root:

```powershell
python -m unittest discover -s tests -v
```

Important cases include unit conversion, Z/Y axis mapping, tolerance boundaries, missing meshes/bones/shapes, bone parent changes, import wrapper traversal, ambiguous names, material slot changes, informational vertex splitting, missing/mismatched FBX hashes, malformed snapshots and invalid configuration. Unit tests can demonstrate comparator behavior; they do not demonstrate that an editor collector reads the intended data.

The repository includes a minimal [GitHub Actions workflow](../.github/workflows/ci.yml) for Python 3.10 and 3.13. Its presence is configuration, not evidence of a completed hosted run. It runs the comparator tests and replays the ten published snapshot pairs without installing runtime dependencies; it does not launch Blender or a licensed Unity Editor.

Replay the actual recorded captures locally:

```powershell
python tools/verify_integration.py --fixtures examples/fixtures --captures examples/captures --output reports/verification
```

The verification succeeds only when each expected state and its exact non-informational finding set agree. Informational notes are retained but do not make a correct pass control fail.

## Local real-asset smoke test

An additional user-owned asset was tested locally without adding its model, snapshots, reports or screenshots to the public repository. The audited scope comprised **2 visible meshes**, **509 shape channels** in total, and **239 unique source bones**. The captured source and Unity target matched within the implemented checks, and the original model file's SHA-256 was unchanged.

Collector scope notes were retained, including ignored viewport modifiers and nonzero shape weights measured as Basis geometry. Hidden meshes were outside this capture. This is a check of that visible export subset, not validation of an entire character, its animation, skin weights or actual deformation. The public synthetic fixtures remain the reproducible evidence distributed with the project.

## Real integration procedure

1. Generate only self-created synthetic geometry with `tools/create_fixture.py`, using background Blender. Preserve the `.blend`, exported FBX and source snapshot as a paired set.
2. Use a new, isolated Unity project. Install this repository's `unity` package and import the exact FBX.
3. Record the Unity version and importer settings; collect its snapshot without changing those settings to fit the expected answer.
4. Compare both snapshots and inspect the FBX hashes, normalized meter extents, bone parent mapping, shape channels and ordered material slots.
5. Reimport a second case with a deliberate, documented change such as disabled blend-shape import or a changed scale factor. Capture again and confirm the relevant check detects the change.
6. Generate the final HTML/JSON reports and screenshots from those actual results. Record the exact change and whether it is a real importer test or a comparator-only JSON mutation.

The fixture generator also exports intentional source-change cases: `lost_shapes`, `reparented_bone`, and `changed_material`. For these negative fixtures, it retains the expected pre-change mesh data in the source JSON while hashing the actually exported changed FBX. This models an expected baseline versus a deliberately altered deliverable. These are real FBX import tests, but they do **not** demonstrate that Unity caused the change or that the negative source JSON is an untouched audited capture. Separately disabling blend-shape import or changing Unity's scale factor tests an importer-induced difference.

The Windows integration runner is available for an isolated reproduction:

```powershell
powershell -NoProfile -File tools/run_unity_integration.ps1 -FixtureDir F:\CodexTemp\ExportLens\fixtures -BaselineFbx ordered_slots.fbx
```

The runner has local Windows defaults for the Unity executable and scratch directories; override `-UnityEditor`, `-ProjectDir` and `-OutputDir` as needed. The final control run used `-BaselineFbx ordered_slots.fbx`. For capturing your own FBX without generating deliberate importer variants, add `-CaptureOnly`. The current safety guard requires the disposable project below `F:\CodexTemp\ExportLens`. The runner refuses to start alongside another Unity Editor. Do not point it at a production project. On other operating systems, use the manual workflow or adapt the runner before executing it.

Use background, low-priority Blender and `Unity -batchmode -nographics` when the machine is in use. Keep expensive runs sequential and use temporary projects outside a user's production workspace. Do not open or modify an unrelated project for demonstration.

## Reproduction details to retain

- OS, Python, Blender and Unity versions.
- Fixture generation command and the synthetic fixture's origin/license.
- Export and import options that affect scale, blend shapes and hierarchy.
- Both snapshot files and the matching FBX SHA-256.
- Comparator command, exit code and report state.
- Log location and any known failure or test skipped.

The repository license covers its self-created synthetic fixture. Purchased avatars, store assets and production project files must not be added as public test material without explicit redistribution rights.
