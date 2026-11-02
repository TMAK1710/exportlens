# Security and privacy

The comparator reads local JSON and writes local HTML/JSON reports. The collectors read the selected Blender data or imported Unity FBX. They do not require credentials or upload asset data.

Treat models, add-ons, editor packages and JSON from unknown sources as untrusted. Install the source code you intend to run. Snapshot basenames avoid absolute source paths, but object names, hierarchy paths, bones and materials can still be confidential. Review outputs before sharing them.

If you find code execution, HTML injection, unintended file writes, path leakage or unexpected network behavior, report the minimal reproduction privately through the repository host's private security advisory feature when it is available. Do not attach private project assets or secrets to a public issue. If private reporting is unavailable, open a public issue requesting a private contact without posting exploit details or sensitive files.

v0.1 is the initial release line. There is no promised response SLA. Never use a report's pass state as a security, licensing or complete asset-fidelity guarantee.
