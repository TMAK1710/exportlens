# Contributing

Start with a reproducible export/import difference and say which part you are changing: Blender collection, Unity collection, comparison, or reporting. Keep snapshot v1 compatible unless the change explicitly introduces and documents a new schema version.

For a bug report, include application versions, the comparator command, the report finding code, and minimal source/target JSON with sensitive names removed. State whether the FBX hashes match. A synthetic reproduction is preferable to a production asset.

For code changes:

1. Read `AGENTS.md` and [the schema](docs/schema.md).
2. Add or adjust a meaningful regression case for the observed behavior. Do not turn an expected importer difference into a failure without evidence.
3. Run `python -m unittest discover -s tests -v`.
4. For collector changes, run a real Blender → FBX → Unity test when available, and record exact editor versions. If you could only run Python tests, say so.
5. Update both README languages and the limits when behavior changes.

The Python runtime should remain dependency-free. Editor collectors should read source assets rather than silently repair or rewrite them. Avoid absolute machine paths in public examples, snapshots or logs. HTML report content derived from names must be escaped.

Only contribute assets you created or have permission to redistribute under a compatible license. The bundled synthetic fixture is intentionally small, original and replaceable. Do not commit commercial avatars, Unity `Library` directories, secrets, large caches, or temporary editor projects.

This project has no guaranteed support response time. Discuss substantial schema or matching-policy changes before investing in a large implementation.
