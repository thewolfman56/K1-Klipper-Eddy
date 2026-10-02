# K1 Max + CFS + BTT Eddy Duo — CrealityOS 2.3.5.33

This fork packages the **validated K1 Max + Creality CFS + BTT Eddy Duo** conversion into a guarded helper instead of a collection of one-off file edits.

> **Validated target:** Creality **K1 Max**, official CFS upgrade path, **CrealityOS 2.3.5.33**, BTT Eddy Duo over USB, and the fixed CFS napkin-strip wipe described below.
>
> Other firmware revisions are **not claimed as compatible**. The helper stops on anything other than `2.3.5.33` unless `--force-unsupported` is deliberately supplied.

The project is derived from [`vsevolod-volkov/K1-Klipper-Eddy`](https://github.com/vsevolod-volkov/K1-Klipper-Eddy) and its SimpleAF-derived Eddy compatibility work. That repository is archived; this fork preserves GPLv3 licensing and adds the K1 Max/CFS/2.3.5.33 integration that was validated on a real printer.

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

Read the full guide first: [`docs/K1MAX-CFS-EDDY-DUO-23533.md`](docs/K1MAX-CFS-EDDY-DUO-23533.md).

Before using the Creality Helper Script on 2.3.5.33, read [`docs/CREALITY-HELPER-SCRIPT.md`](docs/CREALITY-HELPER-SCRIPT.md) for the Entware/Git bootstrap commands and the supported/blocked Helper Script add-on matrix.

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


## Reference documentation

- Creality K1 root/SSH workflow: https://guilouz.github.io/Creality-Helper-Script-Wiki/firmwares/install-and-update-rooted-firmware-k1/
- BIGTREETECH Eddy hardware/mounting: https://neo.bttwiki.com/zh/docs/accessories-docs/sensor/eddy/eddy-hardware
- BIGTREETECH Eddy calibration reference: https://github.com/bigtreetech/Eddy
