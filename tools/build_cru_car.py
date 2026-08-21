#!/usr/bin/env python3
"""Create the small CRU-CAR Arduino-library ZIP for a GitHub release.

Usage: python tools/build_cru_car.py
"""

import hashlib
import json
import os
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIBRARY = os.path.join(REPO, "CRU-CAR")
DIST = os.path.join(REPO, "dist")


def version():
    with open(os.path.join(LIBRARY, "library.properties"), encoding="utf-8") as source:
        for line in source:
            if line.startswith("version="):
                return line.strip().split("=", 1)[1]
    raise SystemExit("CRU-CAR/library.properties has no version")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def main():
    release_version = version()
    archive_name = "CRU-CAR-%s.zip" % release_version
    os.makedirs(DIST, exist_ok=True)
    archive = os.path.join(DIST, archive_name)

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for directory, _, files in os.walk(LIBRARY):
            for filename in sorted(files):
                full_path = os.path.join(directory, filename)
                relative_path = os.path.relpath(full_path, LIBRARY)
                output.write(full_path, os.path.join("CRU-CAR", relative_path))

    metadata = {
        "archiveFileName": archive_name,
        "size": str(os.path.getsize(archive)),
        "checksum": "SHA-256:" + sha256(archive),
    }
    with open(os.path.join(DIST, "cru-car.json"), "w", encoding="utf-8") as output:
        json.dump(metadata, output, indent=2)
        output.write("\n")
    print("wrote %s" % archive)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
