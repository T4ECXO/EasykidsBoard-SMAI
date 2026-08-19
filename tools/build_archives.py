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
import stat
import zipfile

VERSION = "4.3.6"
SOURCE_VERSION = os.environ.get("EASYKIDS_SOURCE_VERSION", "4.3.5")

ARDUINO15 = os.path.expandvars(r"%LOCALAPPDATA%\Arduino15")
HARDWARE = os.path.join(ARDUINO15, "packages", "EasyKidsRobotics", "hardware")

# Working copy of the library that holds the updated vendored dependencies.
DEFAULT_LIB_SRC = os.path.expanduser(
    r"~\Downloads\OcX-EasyKidsBoard-FNC\LibraryEdit\EasyKids3in1Robot"
)
LIB_SRC = os.environ.get("EASYKIDS_LIB_SRC", DEFAULT_LIB_SRC)

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

TRACK_LINE2 = r'''
// Motor selects one physical motor (1 to 4).
// Example: trackLine2(25, 1.0, 1.0, 1);  // command M1 only
void trackLine2(int Speed, float iKP, float DP, int Motor)
{
    if (Motor < 1 || Motor > 4)
    {
        return;
    }

    KP = iKP / 10;
    KD = DP / 10;
    errors = readline() - setPoint;
    derivative = errors - previous_error;
    output = (KP * errors) + (KD * derivative);
    previous_error = errors;
    leftMotor = clamp(Speed - output, -100, 100);

    motor(Motor, leftMotor);
}

// A colon-separated list selects only those motors.
// The first half is the left side and the remaining motors are the right side.
// Examples: trackLine2(25, 1.0, 1.0, "1:3"); or "1:2:3:4".
void trackLine2(int Speed, float iKP, float DP, const char *Motors)
{
    int selected[4];
    int count = 0;
    const char *cursor = Motors;

    while (*cursor && count < 4)
    {
        int motorNumber = 0;
        bool hasDigit = false;
        while (*cursor >= '0' && *cursor <= '9')
        {
            hasDigit = true;
            motorNumber = motorNumber * 10 + (*cursor - '0');
            cursor++;
        }
        if (!hasDigit || motorNumber < 1 || motorNumber > 4)
        {
            return;
        }
        selected[count++] = motorNumber;
        if (*cursor == ':')
        {
            cursor++;
        }
        else if (*cursor)
        {
            return;
        }
    }

    if (count < 1 || count > 4)
    {
        return;
    }

    KP = iKP / 10;
    KD = DP / 10;
    errors = readline() - setPoint;
    derivative = errors - previous_error;
    output = (KP * errors) + (KD * derivative);
    previous_error = errors;
    leftMotor = clamp(Speed - output, -100, 100);
    rightMotor = clamp(Speed + output, -100, 100);

    int leftCount = (count == 1) ? 1 : count / 2;
    for (int i = 0; i < count; i++)
    {
        motor(selected[i], (i < leftCount) ? leftMotor : rightMotor);
    }
}
'''

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

def add_track_line2(core_dir):
    """Add the custom motor-mapping line follower to the staged core."""
    pid_path = os.path.join(core_dir, "libraries", "EasyKids3in1Robot", "EasyKids_PID.h")
    if not os.path.isfile(pid_path):
        return False  # This board variant has no line-follower implementation.

    with open(pid_path, encoding="utf-8") as fh:
        source = fh.read()
    if "void trackLine2(" in source:
        return False

    marker = "\nvoid trackDashedLine("
    if marker not in source:
        sys.exit("trackLine insertion point not found: %s" % pid_path)
    with open(pid_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(source.replace(marker, "\n" + TRACK_LINE2 + marker, 1))
    return True

def remove_readonly(func, path, exc_info):
    """Let staging cleanup remove read-only files copied from Arduino15."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

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
        src = os.path.join(HARDWARE, arch, SOURCE_VERSION)
        if not os.path.isdir(src):
            sys.exit("core not installed: %s" % src)

        root_name = "%s-%s" % (key, VERSION)
        staged = os.path.join(STAGING, root_name)
        print("[%s] staging ..." % key, flush=True)
        if os.path.isdir(staged):
            shutil.rmtree(staged, onerror=remove_readonly)
        os.makedirs(STAGING, exist_ok=True)
        shutil.copytree(src, staged)

        copied = refresh_vendored(staged)
        added_track_line2 = add_track_line2(staged)
        print("[%s] refreshed %d vendored files" % (key, len(copied)), flush=True)
        if added_track_line2:
            print("[%s] added trackLine2 custom motor mapping" % key, flush=True)

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

        shutil.rmtree(staged, onerror=remove_readonly)

    with open(archives_file, "w", encoding="utf-8") as fh:
        json.dump(archives, fh, indent=2)
        fh.write("\n")
    print("wrote %s" % archives_file)


if __name__ == "__main__":
    main()
