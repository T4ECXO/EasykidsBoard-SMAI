#!/usr/bin/env python3
"""Build EasyKidsRobotics boards-manager archives from the locally installed cores.

For each of the three platforms it:
  1. copies the installed core out of Arduino15 into staging/ (the installed
     copy is never modified),
  2. refreshes the third-party libraries vendored inside EasyKids3in1Robot from
     LIB_SRC -- only the vendored files listed in VENDORED, so every core keeps
     its own EasyKids_*.h set (AppControl / Gamepad / IMU / PID differ per core),
  3. zips it into dist/ and records SHA-256 + size in dist/archives.json,
     which make_index.py then turns into the boards-manager index.

Usage:  python tools/build_archives.py [--only esp32]
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile

VERSION = "4.3.5"

ARDUINO15 = os.path.expandvars(r"%LOCALAPPDATA%\Arduino15")
HARDWARE = os.path.join(ARDUINO15, "packages", "EasyKidsRobotics", "hardware")

# Working copy of the library that holds the updated vendored dependencies.
LIB_SRC = os.path.expanduser(
    r"~\Downloads\OcX-EasyKidsBoard-FNC\LibraryEdit\EasyKids3in1Robot"
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGING = os.path.join(REPO, "staging")
DIST = os.path.join(REPO, "dist")

# archive name -> (architecture, board name)
PLATFORMS = {
    "esp32": ("esp32", "EasyKids3in1 BT-WiFi"),
    "esp32-aicar": ("esp32-aicar", "EasyKids3in1 AI-Car"),
    "esp32-gamepad": ("esp32-gamepad", "EasyKids3in1 Gamepad"),
}

# Third-party files vendored inside EasyKids3in1Robot that this repo keeps in
# sync with upstream. Everything else in that folder (EasyKids_*.h, TFT_eSPI,
# Adafruit_PWMServoDriverE, Fonts, logo.h, ...) is left exactly as the core
# shipped it.
VENDORED = [
    "Adafruit_BNO055.h", "Adafruit_BNO055.cpp",
    "Adafruit_Sensor.h", "Adafruit_Sensor.cpp",
    "Adafruit_BusIO_Register.h", "Adafruit_BusIO_Register.cpp",
    "Adafruit_I2CDevice.h", "Adafruit_I2CDevice.cpp",
    "Adafruit_I2CRegister.h",
    "Adafruit_SPIDevice.h", "Adafruit_SPIDevice.cpp",
    "Adafruit_GenericDevice.h", "Adafruit_GenericDevice.cpp",
    "Adafruit_NeoPixelE.h", "Adafruit_NeoPixelE.cpp",
    "esp.c",
    "utility/imumaths.h", "utility/matrix.h",
    "utility/quaternion.h", "utility/vector.h",
]


def refresh_vendored(core_dir):
    """Copy the updated vendored dependencies into a staged core."""
    dst_lib = os.path.join(core_dir, "libraries", "EasyKids3in1Robot")
    if not os.path.isdir(dst_lib):
        sys.exit("no EasyKids3in1Robot in %s" % core_dir)
    copied = []
    for rel in VENDORED:
        src = os.path.join(LIB_SRC, rel)
        if not os.path.isfile(src):
            sys.exit("missing source file: %s" % src)
        dst = os.path.join(dst_lib, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)
    return copied


def zip_tree(src_dir, zip_path, root_name):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for dirpath, dirnames, filenames in os.walk(src_dir):
            dirnames.sort()
            for name in sorted(filenames):
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, src_dir)
                zf.write(full, os.path.join(root_name, rel))


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", choices=sorted(PLATFORMS))
    args = ap.parse_args()
    targets = args.only or sorted(PLATFORMS)

    os.makedirs(DIST, exist_ok=True)
    archives_file = os.path.join(DIST, "archives.json")
    archives = {}
    if os.path.isfile(archives_file):
        with open(archives_file, encoding="utf-8") as fh:
            archives = json.load(fh)

    for key in targets:
        arch, board = PLATFORMS[key]
        src = os.path.join(HARDWARE, arch, VERSION)
        if not os.path.isdir(src):
            sys.exit("core not installed: %s" % src)

        root_name = "%s-%s" % (key, VERSION)
        staged = os.path.join(STAGING, root_name)
        print("[%s] staging ..." % key, flush=True)
        if os.path.isdir(staged):
            shutil.rmtree(staged)
        os.makedirs(STAGING, exist_ok=True)
        shutil.copytree(src, staged)

        copied = refresh_vendored(staged)
        print("[%s] refreshed %d vendored files" % (key, len(copied)), flush=True)

        zip_name = "%s-%s.zip" % (key, VERSION)
        zip_path = os.path.join(DIST, zip_name)
        print("[%s] zipping -> %s" % (key, zip_name), flush=True)
        if os.path.exists(zip_path):
            os.remove(zip_path)
        zip_tree(staged, zip_path, root_name)

        size = os.path.getsize(zip_path)
        digest = sha256(zip_path)
        archives[key] = {
            "architecture": arch,
            "board": board,
            "archiveFileName": zip_name,
            "size": str(size),
            "checksum": "SHA-256:" + digest,
        }
        print("[%s] %s bytes  SHA-256:%s" % (key, size, digest), flush=True)

        shutil.rmtree(staged, ignore_errors=True)

    with open(archives_file, "w", encoding="utf-8") as fh:
        json.dump(archives, fh, indent=2)
        fh.write("\n")
    print("wrote %s" % archives_file)


if __name__ == "__main__":
    main()
