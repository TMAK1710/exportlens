"""Create local release archives, without publishing anything.

Usage: python tools/package_release.py --output <directory outside checkout>
"""
import argparse
import hashlib
import subprocess
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.1.0"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("Release output must stay outside the checkout.")
    output.mkdir(parents=True, exist_ok=True)
    paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT).decode("utf-8").split("\0")
    files = sorted({path for path in paths if path and (ROOT / path).is_file()})
    if not files:
        raise ValueError("No repository files found.")
    artifacts = []
    source = output / f"ExportLens-{VERSION}-source.zip"
    with zipfile.ZipFile(source, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(ROOT / path, "ExportLens/" + path)
    artifacts.append(source)
    addon = output / f"ExportLens-Blender-{VERSION}.zip"
    with zipfile.ZipFile(addon, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(ROOT / "blender_addon/__init__.py", "blender_addon/__init__.py")
        archive.write(ROOT / "LICENSE", "blender_addon/LICENSE")
    artifacts.append(addon)
    unity = output / f"com.exportlens.editor-{VERSION}.tgz"
    with tarfile.open(unity, "w:gz") as archive:
        for path in files:
            if path.startswith("unity/"):
                archive.add(ROOT / path, "package/" + path.removeprefix("unity/"), recursive=False)
        data = (ROOT / "LICENSE").read_bytes()
        info = tarfile.TarInfo("package/LICENSE.md")
        info.size = len(data)
        archive.addfile(info, BytesIO(data))
    artifacts.append(unity)
    app = output / f"exportlens-{VERSION}.pyz"
    with zipfile.ZipFile(app, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("__main__.py", "from exportlens.__main__ import main\nraise SystemExit(main())\n")
        for path in sorted((ROOT / "exportlens").glob("*.py")):
            archive.write(path, "exportlens/" + path.name)
        archive.write(ROOT / "LICENSE", "LICENSE")
    artifacts.append(app)
    sums = [f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}" for path in artifacts]
    (output / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    for path in artifacts:
        print(f"{path.name} ({path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
