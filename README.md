# EasykidsBoard-SMAI

Boards Manager package for the EasyKids 3in1 robot boards (ESP32), rebuilt with
up-to-date vendored libraries.

## Install

Arduino IDE → **File ▸ Preferences ▸ Additional boards manager URLs**, add:

```
https://raw.githubusercontent.com/T4ECXO/EasykidsBoard-SMAI/main/package_easykidsrobotics_index.json
```

Then **Tools ▸ Board ▸ Boards Manager**, search `EasyKids`, install **4.3.7**.

> Remove the upstream `EasyKidsRoboticsDev` boards URL first if you have it.
> Both indexes declare the same package (`EasyKidsRobotics`) at the same version,
> so keeping both makes Boards Manager pick one at random.

`arduino-cli` equivalent:

```sh
arduino-cli core update-index --additional-urls https://raw.githubusercontent.com/T4ECXO/EasykidsBoard-SMAI/main/package_easykidsrobotics_index.json
arduino-cli core install EasyKidsRobotics:esp32 --additional-urls <same url>
```

## Boards

| Board | FQBN | Base |
|---|---|---|
| EasyKids3in1 BT-WiFi | `EasyKidsRobotics:esp32:esp32` | arduino-esp32 2.0.17 |
| EasyKids3in1 AI-Car | `EasyKidsRobotics:esp32-aicar:esp32` | arduino-esp32 2.0.17 |
| EasyKids3in1 Gamepad | `EasyKidsRobotics:esp32-gamepad:3in1easykids` | arduino-esp32 2.0.11 + Bluepad32 3.8.3 |

FQBNs are unchanged from the upstream package, so existing sketches and board
selections keep working.

## What differs from upstream 4.3.6

**The index is self-contained.** The upstream index lists its toolchains under
`packager: "esp32"` while declaring them under its own package name, and never
declares `openocd-esp32 v0.12.0-esp32-20230921` at all — so installing from that
URL alone fails unless the Espressif index is also configured. Here every tool
the platforms depend on is inlined under the `EasyKidsRobotics` packager, so the
one URL above is enough.

**Vendored libraries in `EasyKids3in1Robot` are updated.** Third-party
dependencies are refreshed while each core keeps its own `EasyKids_*.h` set
(`EasyKids_AppControl.h` on BT-WiFi, `EasyKids_Gamepad.h` on Gamepad, and so
on).

**Line following has an additional stable motor-mapping API.** `trackLine2`
accepts either two motor numbers (`"left:right"`) or four motor numbers
(`"left-top:left-bottom:right-top:right-bottom"`). For example:

```cpp
trackLine2(30, 1.0, 1.0, "1:2");
trackLine2(30, 1.0, 1.0, "1:2:3:4");
```

It reads the line sensors once per update, keeps derivative history separate
from `trackLine`, and suppresses derivative kick on the first update or after a
pause. Invalid, duplicate, or ambiguous motor lists are ignored.

| Library | Upstream 4.3.6 | Here |
|---|---|---|
| Adafruit BusIO | 1.15.0–1.16.1 | **1.17.4** |
| Adafruit Unified Sensor | ~1.1.14 | **1.1.15** |
| Adafruit BNO055 | 1.6.1 | **1.6.4** |
| Adafruit NeoPixel (`Adafruit_NeoPixelE`) | 1.11.0 | **1.15.5** |

Deliberately left alone:

- **TFT_eSPI** — the vendored copy reports `1.4.20` but is a fork of it, ~1,217
  lines longer, with `TFT_config.h`, `logo.h` and Thai fonts that upstream does
  not have. Moving to 2.5.x would have to be a port, not a version bump.
- **Adafruit PWM Servo Driver** (`Adafruit_PWMServoDriverE`, 2.4.1) — 3.0.x
  switches the I²C path to `Adafruit_I2CDevice`. It compiles, but this chip
  drives every motor and servo, so the change needs hardware testing first.

The `…E` suffix on the NeoPixel and PWM driver files is an EasyKids rename of
the filename and include guard only; the class names are stock Adafruit. The
rename is preserved.

## Rebuilding

Requires the cores already installed in `Arduino15` and Python 3.

```sh
python tools/build_archives.py      # stage cores, refresh vendored libs, zip, hash
python tools/make_index.py          # write package_easykidsrobotics_index.json
```

`build_archives.py` copies the installed cores into `staging/` before touching
anything, so `Arduino15` is never modified. Archives land in `dist/` with their
SHA-256 and size recorded in `dist/archives.json`.

Then attach the three zips from `dist/` to a GitHub release tagged `4.3.7` and
push the regenerated index. The archives are 230–320 MB each, over GitHub's
100 MB per-file limit for repository contents, so they have to be release
assets — `dist/` is gitignored for that reason.

## License

The EasyKids core and library are the work of EasyKidsRobotics; bundled
third-party components keep their own licenses (Adafruit — BSD/MIT/LGPL,
TFT_eSPI — FreeBSD, Bluepad32 — Apache-2.0, arduino-esp32 — LGPL-2.1).
