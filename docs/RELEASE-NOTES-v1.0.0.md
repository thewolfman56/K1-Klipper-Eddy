# v1.0.0 release notes — K1 Max + CFS + BTT Eddy Duo

## Supported target

This release is validated for:

- Creality **K1 Max**
- official **Creality CFS upgrade**
- **CrealityOS 2.3.5.33**
- **BTT Eddy Duo** over USB
- fixed external CFS napkin-strip holder / saver
- Fluidd + Moonraker/Nginx from the Creality Helper Script

Do **not** treat this release as validated for 2.3.5.34, 2.3.5.35, the newer 1.1.x K1 Max firmware line, a different mainboard, or a CFS-C conversion.

## What v1.0.0 adds

This fork turns the manually validated K1 Max + CFS + Eddy conversion into a guarded, reversible installer.

Highlights:

- firmware/CFS/Eddy preflight checks;
- timestamped backups before write stages;
- isolated Eddy compatibility modules instead of replacing the entire Creality Klipper tree;
- preservation of Creality PRTouch/CFS compatibility;
- staged Eddy calibration before native-Z activation;
- native Eddy Z using `probe:z_virtual_endstop`;
- corrected off-bed cold-start homing model;
- deliberate two-pass X/Y sensorless homing retained;
- 20×20 / 400-point Eddy `rapid_scan`;
- fixed CFS napkin wipe with per-printer measured coordinates;
- corrected CFS startup order: `START_PRINT` keeps the napkin wipe but no longer purges before the slicer's first CFS `T...` load;
- validated OrcaSlicer 2.4.2 Machine Start / Change Filament G-code in `docs/ORCASLICER-CFS-GCODE.md`;
- Eddy-only calibration persistence instead of blind `SAVE_CONFIG`;
- rollback support;
- optional add-on compatibility auditing;
- production-state verification;
- pre-firmware-update snapshot and post-update audit;
- release-readiness gate;
- deterministic Git-free install ZIP builder.

## Corrected cold-start safety model

The final production testing demonstrated that Eddy must **not** be treated as a physical-clearance sensor while XY is unknown.

If the probe is physically off the bed, Eddy may report `CLEAR_SIDE` or an outside-calibration-range value. That proves the sensor is responding, but it does not prove the nozzle is safely clear of the bed.

The supported cold-start sequence is:

1. clear any mesh;
2. run `EDDY_HOME_STATUS SAMPLES=50 TIMEOUT=2` as a connectivity-only check;
3. use Creality's bounded unknown-Z-away move;
4. perform the intentional two-pass Y homing;
5. perform the intentional two-pass X homing;
6. move XY to the native-Z homing position;
7. synchronize motion with `M400` and settle;
8. run `EDDY_PREHOME_CLEAR MAX_TRAVEL=2.000` while Eddy is over the bed;
9. perform native Eddy `G28 Z`.

The superseded pre-XY `EDDY_PREHOME_CLEAR MARGIN=1.000 MAX_TRAVEL=5.000` path is explicitly rejected.

## Validated production reference

Reference snapshot:

```text
known-good-eddy-production-20261001-153849
```

Cleaned archive SHA256:

```text
11582373c6f9d3886afc58644851a8be1c987da3128618974c2e93091f01e408
```

Production `sensorless.cfg` SHA256:

```text
548fdaa7d19a0eaf5a943febe416bde97dd736987ecf7e2991a5bd61b0caa12c
```

The public repository locks the exact recovered production homing-safety sections in CI.

### Final operational baseline — 2026-10-05

After the installer/source baseline was established, the reference printer
completed a final end-to-end regression and was frozen again at:

```text
/usr/data/printer_data/backups/K1Max-CFS-BTT-Eddy-known-good-20261005-133356
```

The frozen snapshot passed a complete SHA256 manifest verification. Key exact
reference hashes include:

```text
gcode_macro.cfg
64c133a15c7b33fb916090b93eaac936ab9ac171fc12273588283f26ce2b73ac

sensorless.cfg
548fdaa7d19a0eaf5a943febe416bde97dd736987ecf7e2991a5bd61b0caa12c

eddy_nozzle_clear.cfg
5318022508d0a1a114e86ac8f4bfe7432ae3831ceb44d5be242dcf970a7661bf

custom_macro.py
b30722d58af3db0cad8db5248e9565338178cfa43ebe9e8eaddb39b2ed63a676
```

The final regression physically validated the normal CFS cutter and purge
paths, initial T0 load, T0 -> T1 material change, material flush, and
prime-tower continuation with the Eddy Duo mount.

The obsolete slicer-emitted side-brush commands are intentionally excluded:

```text
CFS_NOZZLE_CLEAR
CFS_NOZZLE_CLEAN
```

The final reference slice also contained no standalone `BOX_NOZZLE_CLEAN` and
no `CX_PRINT_DRAW_ONE_LINE`. Exact OrcaSlicer Machine Start and Change
Filament G-code is documented in `docs/ORCASLICER-CFS-GCODE.md`.

## Installation paths

### Git / Entware

The documentation includes the full Entware → Git bootstrap for CrealityOS 2.3.5.33.

After Git is working:

```sh
cd /usr/data
git clone -b k1max-cfs-eddy-duo-2.3.5.33 \
  https://github.com/thewolfman56/K1-Klipper-Eddy.git
cd K1-Klipper-Eddy
```

### Git-free ZIP

A deterministic printer-install ZIP can be built with:

```sh
python3 scripts/build_release.py \
  --version v1.0.0 \
  --output dist/K1-Klipper-Eddy-v1.0.0.zip
```

The ZIP excludes repository/CI/test/cache content and contains a `RELEASE-MANIFEST.json`.

## Required Creality Helper Script profile

Required:

- Moonraker and Nginx
- Fluidd
- Tools → **Prevent updating Klipper configuration files**

Entware/Git are optional infrastructure if a ZIP install is used.

## Validated optional add-ons

Validated on the reference installation:

- Klipper Gcode Shell Command when required by another optional feature
- Improved Shapers Calibrations
- Moonraker Timelapse
- Camera Settings Control
- OctoEverywhere
- Mobileraker Companion

OctoEverywhere and Mobileraker required documented K1-specific stock-Python/service-wrapper fixes on the validated source revisions.

## Explicitly unsupported/conflicting Helper Script items for v1.0.0

Do not install as part of the supported profile:

- Klipper Adaptive Meshing & Purging (KAMP)
- Nozzle Cleaning Fan Control
- Useful Macros
- Save Z-Offset Macros
- Screws Tilt Adjust Support
- M600 Support
- Guppy Screen
- removal of the Creality web interface

These overlap, replace, or were not validated against the CFS/Eddy motion/probe/config path.

## Main commands

```text
doctor
backup
stage
persist
activate
configure-wipe
status
verify-production
release-readiness
pre-update-snapshot
audit-after-update
rollback
```

The installer itself does **not** issue homing, probing, wipe motion, heater, or print G-code.

## Production verification

Run:

```sh
sh install.sh verify-production
```

Results:

- `EXACT` — active bytes exactly match the recorded production reference;
- `EXPECTED CUSTOM` — machine-specific bytes differ but required safety structure validates;
- `DRIFT` — required file/structure is missing or changed unexpectedly.

Any `DRIFT` exits with code 3.

## Release-readiness

Run:

```sh
sh install.sh release-readiness
```

Results:

- `PASS`
- `WARN`
- `INFO`
- `FAIL`

Any `FAIL` exits with code 5 and reports `NOT READY`.

A healthy public build may report `READY WITH WARNINGS` because the final production checksum for `eddy_z_acquire.py` is known, while the exact original production bytes were not preserved as a retrievable repository artifact. The public helper is therefore safety-contract validated rather than falsely labeled byte-identical.

## Firmware updates

Before a Creality firmware update:

```sh
sh install.sh pre-update-snapshot
```

After the update and reboot:

```sh
sh install.sh audit-after-update <snapshot>
```

The post-update audit is read-only and can run on a firmware version other than 2.3.5.33.

It intentionally performs **no automatic repair**. If a captured file changed or disappeared, review is required before restoring anything. Never copy 2.3.5.33 Klipper/CFS files blindly onto a newer firmware.

## Machine-specific values

Do not copy these from the reference printer:

- Eddy USB serial
- drive-current calibration
- Eddy frequency/height calibration curve
- temperature compensation values
- measured napkin-strip surface Z coordinates

## Physical validation requirement

The corrected load-before-purge startup sequence and a real mid-print CFS tool
change were physically validated successfully on 2026-10-02 using OrcaSlicer
2.4.2.

CI cannot prove real nozzle/bed clearance, sensorless homing forces, napkin contact pressure, or CFS material motion.

Before publishing v1.0.0, complete `docs/RELEASE-CHECKLIST.md` on the physical K1 Max, including:

- cold-start unknown-XYZ homing;
- Eddy fail-stop/disconnect behavior;
- fixed napkin wipe;
- 20×20 rapid scan;
- full CFS start-print path;
- backup/update-snapshot creation.

## License / upstream

This repository preserves the upstream GPLv3 licensing and derives from the archived `vsevolod-volkov/K1-Klipper-Eddy` / SimpleAF-derived Eddy compatibility work.

The project is provided for the documented hardware/firmware profile; users should keep immediate access to printer power during first physical motion validation.
