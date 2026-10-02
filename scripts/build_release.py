#!/usr/bin/env python3
"""Build a clean, deterministic install ZIP for K1 Max + CFS + BTT Eddy."""

import argparse
import json
from pathlib import Path
import subprocess
import zipfile

TARGET_FIRMWARE = "2.3.5.33"
PRODUCTION_REFERENCE = "known-good-eddy-production-20261001-153849"

ROOT = Path(__file__).resolve().parent.parent

TOP_LEVEL = (
    "README.md",
    "LICENSE",
    "install.sh",
    "legacy-install.sh",
)

DIRECTORIES = (
    "scripts",
    "klippy",
    "config",
    "docs",
)

EXCLUDED_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}

EXCLUDED_SUFFIXES = {
    ".pyc",
    ".pyo",
}


def source_commit():
    try:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            timeout=5,
        )
        if proc.returncode == 0:
            value = proc.stdout.strip()
            if value:
                return value
    except Exception:
        pass
    return None


def should_include(path):
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDED_NAMES for part in rel.parts):
        return False
    if path.suffix in EXCLUDED_SUFFIXES:
        return False
    if path.is_dir():
        return False
    return True


def release_files():
    files = []
    for rel in TOP_LEVEL:
        path = ROOT / rel
        if not path.exists():
            raise SystemExit("Required release file is missing: %s" % rel)
        files.append(path)

    for rel in DIRECTORIES:
        base = ROOT / rel
        if not base.exists():
            raise SystemExit("Required release directory is missing: %s" % rel)
        for path in base.rglob("*"):
            if should_include(path):
                files.append(path)

    # Tests, CI configuration, Git metadata, local backups and bytecode are
    # deliberately not shipped to the printer.
    return sorted(set(files), key=lambda p: str(p.relative_to(ROOT)))


def zip_info(name):
    info = zipfile.ZipInfo(name)
    # Fixed timestamp makes the archive deterministic for identical source.
    info.date_time = (2026, 10, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    # Regular file mode 0644; install.sh gets 0755 below.
    mode = 0o100644
    if name in ("install.sh", "legacy-install.sh") or name.startswith("scripts/"):
        mode = 0o100755
    info.external_attr = mode << 16
    return info


def build(version, output):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)

    prefix = "K1-Klipper-Eddy-%s/" % version
    manifest = {
        "project": "K1 Max + CFS + BTT Eddy Duo",
        "version": version,
        "target_firmware": TARGET_FIRMWARE,
        "production_reference": PRODUCTION_REFERENCE,
        "source_commit": source_commit(),
        "entrypoint": "install.sh",
    }

    with zipfile.ZipFile(output, "w") as zf:
        for path in release_files():
            rel = str(path.relative_to(ROOT)).replace("\\", "/")
            zf.writestr(
                zip_info(prefix + rel),
                path.read_bytes(),
            )

        zf.writestr(
            zip_info(prefix + "RELEASE-MANIFEST.json"),
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode(),
        )

    print(output)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    output = args.output or (
        ROOT / "dist" / ("K1-Klipper-Eddy-%s.zip" % args.version)
    )
    build(args.version, output)


if __name__ == "__main__":
    main()
