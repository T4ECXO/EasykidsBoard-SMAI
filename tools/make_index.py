#!/usr/bin/env python3
"""Generate the boards-manager index for the EasyKidsRobotics package.

The index this produces is self-contained: every toolchain the platforms need is
declared inside it under the EasyKidsRobotics packager, so a user only has to
paste one URL into Preferences. (The stock EasyKids index declares its tools
under `packager: "esp32"` and omits openocd-esp32 v0.12.0 entirely, so it only
installs if the Espressif index happens to be present too.)

Tool definitions are copied verbatim -- URLs, checksums, per-host archives --
from the Espressif and Arduino indexes already cached in Arduino15, so no
download is required to build the index.

Usage:  python tools/make_index.py
"""

import json
import os
import sys

VERSION = "4.3.6"
SOURCE_VERSION = os.environ.get("EASYKIDS_SOURCE_VERSION", "4.3.5")
PACKAGE_NAME = "EasyKidsRobotics"
RELEASE_BASE = "https://github.com/T4ECXO/EasykidsBoard-SMAI/releases/download/" + VERSION
REPO_URL = "https://github.com/T4ECXO/EasykidsBoard-SMAI"

ARDUINO15 = os.path.expandvars(r"%LOCALAPPDATA%\Arduino15")
HARDWARE = os.path.join(ARDUINO15, "packages", "EasyKidsRobotics", "hardware")
ESP32_INDEX = os.path.join(ARDUINO15, "package_esp32_index.json")
ARDUINO_INDEX = os.path.join(ARDUINO15, "package_index.json")

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVES = os.path.join(REPO, "dist", "archives.json")
OUT = os.path.join(REPO, "package_easykidsrobotics_index.json")

# Packagers whose tools we inline into our own package. `arduino` is left
# alone: its index ships with the IDE, so arduino:dfu-util always resolves.
INLINE_FROM = {"esp32"}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def tool_pool(index_path):
    """name -> version -> tool definition, for every packager in an index."""
    pool = {}
    for pkg in load(index_path).get("packages", []):
        for tool in pkg.get("tools", []):
            pool.setdefault(pkg["name"], {}).setdefault(tool["name"], {})[
                tool["version"]
            ] = tool
    return pool


def main():
    if not os.path.isfile(ARCHIVES):
        sys.exit("run tools/build_archives.py first (missing %s)" % ARCHIVES)
    archives = load(ARCHIVES)

    pools = {}
    pools.update(tool_pool(ESP32_INDEX))
    for name, tools in tool_pool(ARDUINO_INDEX).items():
        pools.setdefault(name, {}).update(tools)

    platforms = []
    needed = {}  # (packager, name, version) -> definition

    for key in sorted(archives):
        meta = archives[key]
        arch = meta["architecture"]
        installed = load(os.path.join(HARDWARE, arch, SOURCE_VERSION, "installed.json"))
        src = installed["packages"][0]["platforms"][0]

        deps = []
        for dep in src.get("toolsDependencies", []):
            packager = dep["packager"]
            if packager in INLINE_FROM:
                found = pools.get(packager, {}).get(dep["name"], {}).get(dep["version"])
                if found is None:
                    sys.exit(
                        "tool %s:%s@%s not found in the cached indexes"
                        % (packager, dep["name"], dep["version"])
                    )
                needed[(packager, dep["name"], dep["version"])] = found
                packager = PACKAGE_NAME
            deps.append(
                {
                    "packager": packager,
                    "name": dep["name"],
                    "version": dep["version"],
                }
            )

        platforms.append(
            {
                "name": PACKAGE_NAME,
                "architecture": arch,
                "version": VERSION,
                "category": "Contributed",
                "url": "%s/%s" % (RELEASE_BASE, meta["archiveFileName"]),
                "archiveFileName": meta["archiveFileName"],
                "checksum": meta["checksum"],
                "size": meta["size"],
                "help": {"online": REPO_URL},
                "boards": [{"name": meta["board"]}],
                "toolsDependencies": deps,
            }
        )

    tools = [needed[k] for k in sorted(needed)]

    index = {
        "packages": [
            {
                "name": PACKAGE_NAME,
                "maintainer": "EasyKidsRobotics / SMAI",
                "websiteURL": REPO_URL,
                "email": "",
                "help": {"online": REPO_URL},
                "platforms": platforms,
                "tools": tools,
            }
        ]
    }

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print("wrote %s" % OUT)
    for pl in platforms:
        print("  %-14s %s  (%s bytes)" % (pl["architecture"], pl["archiveFileName"], pl["size"]))
    print("  inlined %d tool definitions under packager %s" % (len(tools), PACKAGE_NAME))


if __name__ == "__main__":
    main()
