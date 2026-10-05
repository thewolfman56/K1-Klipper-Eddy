# K1 Max + CFS + BTT Eddy Duo — CrealityOS 2.3.5.33

This fork packages the **validated K1 Max + Creality CFS + BTT Eddy Duo** conversion into a guarded helper instead of a collection of one-off file edits.

> **Validated target:** Creality **K1 Max**, official CFS upgrade path, **CrealityOS 2.3.5.33**, BTT Eddy Duo over USB, and the fixed CFS napkin-strip wipe described below.
>
> Other firmware revisions are **not claimed as compatible**. The helper stops on anything other than `2.3.5.33` unless `--force-unsupported` is deliberately supplied.
>
> **Recommended clean starting point:** begin with a **factory-reset or freshly reflashed official CrealityOS 2.3.5.33 installation** before rooting the printer or installing Helper Script/Klipper modifications. This is not strictly required for an already-clean, known installation, but it reduces the chance that old macros, probe files, Helper Script changes, or other customizations interfere with the validated installation path. A reset/reflash may erase configuration and user data, so preserve anything you need first and confirm the printer is actually running `2.3.5.33` before proceeding.

## Important safety, warranty, and liability notice

> **Use this project entirely at your own risk.** This is an unofficial community project and is not supported, endorsed, or warranted by Creality, BIGTREETECH, or any other printer or hardware manufacturer.
>
> This repository modifies a rooted printer's configuration and Klipper environment, including homing, probing, Z-axis behavior, bed meshing, nozzle wiping, and CFS-related workflows. Differences in hardware, assembly, probe mounting, calibration, firmware, slicer settings, or user-entered measurements can cause unexpected motion or failures, including nozzle/bed/probe collisions, toolhead crashes, damaged electronics or mechanical parts, failed prints, data loss, or other property damage.
>
> **You are responsible for deciding whether these modifications are appropriate for your printer, making and verifying your own backups, checking every machine-specific value, validating motion carefully, and maintaining immediate access to printer power during first-use testing.**
>
> To the maximum extent permitted by applicable law, the repository owner and contributors provide this project **without warranty** and are **not responsible or liable for damage to your printer or other property, personal injury, loss of data, loss of use, failed prints, downtime, or other losses arising from use or misuse of this repository.**
>
> Rooting the printer, replacing or modifying firmware/configuration files, installing third-party hardware, or otherwise altering the machine **may affect or void manufacturer warranty or service eligibility**. Warranty rights vary by manufacturer, seller, jurisdiction, and applicable consumer-protection law. You are responsible for reviewing the terms that apply to your printer before proceeding.
>
> This project remains licensed under GPLv3. See [`LICENSE`](LICENSE), including its **NO WARRANTY** provisions.

The project is derived from [`vsevolod-volkov/K1-Klipper-Eddy`](https://github.com/vsevolod-volkov/K1-Klipper-Eddy) and its SimpleAF-derived Eddy compatibility work. That repository is archived; this fork preserves GPLv3 licensing and adds the K1 Max/CFS/2.3.5.33 integration that was validated on a real printer.

## Start here — one complete installation guide

For a new installation, use **[START-HERE-COMPLETE-INSTALL.md](docs/START-HERE-COMPLETE-INSTALL.md)**.

That document puts the entire supported procedure in one ordered walkthrough: clean 2.3.5.33 starting state, root/SSH, Entware/Git, required Creality Helper Script items, CFS verification, Eddy mounting and calibration, staging/activation, progressive homing tests, measured napkin wipe setup, exact OrcaSlicer Machine G-code, controlled print validation, backups, and the firmware-update audit workflow.

The other documents in `docs/` remain available as deeper technical references and troubleshooting material, but they are **not required to be read in sequence** when following the Start Here guide.

## What the helper does

The workflow is intentionally split into **calibration staging** and **native Eddy activation**:

- checks firmware, CFS files, root environment, printer idle state, and the Eddy USB serial;
- creates timestamped rollback snapshots before every write stage;
- preserves Creality's original `bed_mesh.py` and routes between Creality/PRTouch and Eddy implementations;
- keeps the proprietary PRTouch object available for CFS while allowing Eddy to own the global probe;
- stages Eddy while PRTouch/TMC still owns Z so Eddy can be calibrated safely;
- persists only Eddy calibration values instead of blindly saving unrelated Creality `SAVE_CONFIG` state;
- switches `[stepper_z]` to `probe:z_virtual_endstop` only after calibration is present;
- uses Eddy only as a connectivity check while XY is unknown, preserves Creality's bounded unhomed-Z-away move, and only trusts Eddy clearance after XY is centered over the bed;
- retains Creality's deliberate two-pass sensorless X/Y homing;
- routes CFS leveling to a fresh 20×20 `rapid_scan` Eddy mesh;
- removes Creality's pre-CFS `CX_PRINT_DRAW_ONE_LINE` from `START_PRINT` while retaining the Eddy-safe napkin wipe, so the slicer can load the selected CFS filament before purging;
- blocks nozzle wiping until the fixed napkin strip has been measured on that printer;
- can restore the full configuration and every Klipper file it touched from a helper backup.

The helper itself **never sends `G28`, `PROBE`, wipe moves, heater commands, or print commands**.

## Hardware / physical prerequisites

1. Creality K1 Max with the CFS upgrade installed and working on stock Creality CFS firmware.
2. BTT Eddy Duo mounted rigidly and flashed with Klipper-compatible firmware. BTT recommends mounting Eddy roughly **2–3 mm above the nozzle**.
3. The validated probe geometry used an Eddy offset of approximately **X = -23 mm, Y = 0 mm**. Verify your own mount before using those values.
4. A fixed napkin-strip holder compatible with the K1 Max CFS conversion. The validated build used **“K1 Max Napkin Strip Saver for use with CFS Upgrade Kit” by Eric Sten (@EricSten_321774), Printables model 1286860**. Search by that exact title if the model URL changes.
5. SSH access to the rooted printer and a way to stop power quickly during first motion tests.

The napkin strip is not conductive, so Eddy **cannot measure the wipe surface directly**. The wipe path is stored as fixed, printer-specific coordinates after manual measurement.

## Fast path

For the complete ordered install, follow **[`docs/START-HERE-COMPLETE-INSTALL.md`](docs/START-HERE-COMPLETE-INSTALL.md)** from top to bottom.

The focused documents remain useful when you want additional detail about a specific subsystem:

- [`docs/K1MAX-CFS-EDDY-DUO-23533.md`](docs/K1MAX-CFS-EDDY-DUO-23533.md) — Eddy/CFS installation internals and safety model;
- [`docs/CREALITY-HELPER-SCRIPT.md`](docs/CREALITY-HELPER-SCRIPT.md) — full Helper Script compatibility matrix and optional add-ons;
- [`docs/ORCASLICER-CFS-GCODE.md`](docs/ORCASLICER-CFS-GCODE.md) — validated OrcaSlicer G-code and reference-slice analysis.

> **Final reference regression (2026-10-05):** the normal CFS cutter/purge path,
> initial T0 load, real T0 -> T1 change, material flush, and prime-tower
> continuation were physically validated with the mounted Eddy Duo. The frozen
> reference snapshot is
> `/usr/data/printer_data/backups/K1Max-CFS-BTT-Eddy-known-good-20261005-133356`.
> The obsolete slicer-emitted `CFS_NOZZLE_CLEAR` / `CFS_NOZZLE_CLEAN`
> side-brush path is intentionally excluded; a fresh slice must also not
> reintroduce `CX_PRINT_DRAW_ONE_LINE`.

Validated optional Helper Script add-ons on the reference machine include **Improved Shapers Calibrations, Moonraker Timelapse, Camera Settings Control, OctoEverywhere, and Mobileraker Companion**. OctoEverywhere and Mobileraker required the K1-specific stock-Python/service-wrapper fixes documented in that guide.

`sh install.sh doctor` now audits those optional components without changing them. It reports `PASS`, `INFO`, or `WARN` for Camera Settings Control, OctoEverywhere, and Mobileraker, including stock-vs-Entware Python, K1 `exec` wrappers, process counts, and PID-file consistency.

After rooting, mounting/flashing Eddy, and putting this repository on the printer:

```sh
sh install.sh doctor
sh install.sh stage --x-offset -23 --y-offset 0
```

Review the generated config, then issue `FIRMWARE_RESTART` from Fluidd. Perform Eddy drive-current and height-map calibration as described in the guide. After each calibration operation that creates a pending Eddy setting:

```sh
sh install.sh persist
```

Once `sh install.sh status` shows a drive current and a populated height map:

```sh
sh install.sh activate
```

After reviewing the changes, issue `FIRMWARE_RESTART`, validate homing, then measure the CFS napkin strip and install its fixed wipe path:

```sh
sh install.sh configure-wipe \
  --start-x <measured-x> --start-y <measured-y> --start-surface-z <measured-z> \
  --end-x <measured-x> --end-y <measured-y> --end-surface-z <measured-z> \
  --confirm-measured
```

Until `configure-wipe` is completed, `NOZZLE_CLEAR` intentionally raises an error instead of guessing a wipe height.

After activation and wipe configuration, the live printer can be checked against the final reference without changing anything:

```sh
sh install.sh verify-production
```

`EXACT` means the file SHA256 matches the final reference snapshot. `EXPECTED CUSTOM` means bytes differ for an allowed printer-specific reason (for example USB serial, calibration curve, includes, or measured napkin coordinates) while the required safety structure still validates. `DRIFT` means a required file is missing or its validated safety/compatibility contract no longer matches.

For one final release-candidate check, run:

```sh
sh install.sh release-readiness
```

The readiness command is also read-only. Core safety/integrity problems produce `FAIL` and exit code 5. Optional add-on or repository-working-tree concerns produce `WARN` without turning an otherwise safe printer into a false failure. Because the public `eddy_z_acquire.py` is safety-contract validated but is not falsely claimed to be byte-identical to the unrecovered production helper, the current public build may legitimately report `READY WITH WARNINGS`.

Before any future Creality firmware update, create a separate update baseline:

```sh
sh install.sh pre-update-snapshot
```

After the firmware update and reboot, **do not immediately restore old files**. Audit the new firmware first:

```sh
sh install.sh audit-after-update <snapshot-directory>
```

The audit reports `UNCHANGED`, `CHANGED`, `MISSING`, and `NEW` files and rechecks the production homing safety contract. It performs no repair and can be run even when the new firmware is no longer `2.3.5.33`.

## Commands

| Command | Purpose |
|---|---|
| `doctor` | Read-only firmware/CFS/Eddy preflight plus validated optional add-on audit |
| `backup` | Create a timestamped rollback snapshot |
| `stage` | Install Eddy support for calibration while PRTouch/TMC still owns Z |
| `persist` | Save only pending Eddy calibration values into `btteddy_mcu.cfg` |
| `activate` | Enable native Eddy Z and the validated homing/CFS safety routing |
| `configure-wipe` | Generate the fixed napkin wipe from measured coordinates |
| `status` | Show firmware, calibration, native-Z, corrected off-bed safety guards, exact production-safety contract (`PASS`/`DRIFT`), and wipe state |
| `verify-production` | Read-only comparison against the final production snapshot; reports `EXACT`, `EXPECTED CUSTOM`, or `DRIFT` and exits nonzero on drift |
| `release-readiness` | Read-only aggregate PASS/WARN/INFO/FAIL release audit across firmware, calibration, homing safety, native Z, wipe, compatibility sources, optional add-ons, update-snapshot readiness, and repository integrity |
| `pre-update-snapshot` | Verify the working installation, then preserve the full printer config and update-sensitive Klipper/service files before a firmware update |
| `audit-after-update <snapshot>` | Read-only post-update comparison showing exactly which captured files were changed, removed, or added; performs no repair |
| `rollback <dir>` | Restore a helper-created backup |

## Important boundaries

- **Do not copy another printer's Eddy calibration curve, USB serial, or napkin-strip Z values.** They are intentionally absent from this repository.
- **Do not use Eddy `CLEAR_SIDE` as proof of physical clearance while XY is unknown.** The probe may be hanging off the bed; the validated cold-start path uses a connectivity-only Eddy check plus Creality's bounded Z-away move until XY is centered.
- Do not run `activate` before drive-current and height-map calibration are persisted.
- Do not use this branch as proof of compatibility with `2.3.5.34`, `2.3.5.35`, the newer `1.1.x` K1 Max firmware line, or a different motherboard/CFS-C conversion.
- Creality firmware updates can overwrite patched Klipper files. Create a `pre-update-snapshot` first, then use `audit-after-update` after reboot. **Do not blindly restore `.33` Klipper files onto a newer firmware.** This release should be treated as a `2.3.5.33` target only.
- The original upstream installer is retained as `legacy-install.sh` for reference and is **not** the recommended installation method for this fork.

See [`docs/VALIDATED-STATE.md`](docs/VALIDATED-STATE.md) for the exact behavior and regression state this helper was derived from.

Before merging/tagging a release, use [`docs/RELEASE-CHECKLIST.md`](docs/RELEASE-CHECKLIST.md) for the live-printer, CI, recovery, documentation, and physical-motion release gates.
Draft v1.0.0 release text is maintained in [`docs/RELEASE-NOTES-v1.0.0.md`](docs/RELEASE-NOTES-v1.0.0.md).

A Git-free install archive can be built reproducibly with:

```sh
python3 scripts/build_release.py \
  --version v1.0.0 \
  --output dist/K1-Klipper-Eddy-v1.0.0.zip
```

The ZIP contains the installer, required Klipper compatibility files, configuration templates, license, and user documentation. It intentionally excludes Git metadata, CI files, tests, caches, and Python bytecode. A `RELEASE-MANIFEST.json` inside the archive records the target firmware, production reference, entrypoint, version, and source commit when available.


## Reference documentation

- Creality K1 root/SSH workflow: https://guilouz.github.io/Creality-Helper-Script-Wiki/firmwares/install-and-update-rooted-firmware-k1/
- BIGTREETECH Eddy hardware/mounting: https://neo.bttwiki.com/zh/docs/accessories-docs/sensor/eddy/eddy-hardware
- BIGTREETECH Eddy calibration reference: https://github.com/bigtreetech/Eddy
