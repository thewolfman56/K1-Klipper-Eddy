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
- installs the validated cold-start Eddy clearance guard before any X/Y homing motion;
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

## Commands

| Command | Purpose |
|---|---|
| `doctor` | Read-only firmware/CFS/Eddy/preflight checks |
| `backup` | Create a timestamped rollback snapshot |
| `stage` | Install Eddy support for calibration while PRTouch/TMC still owns Z |
| `persist` | Save only pending Eddy calibration values into `btteddy_mcu.cfg` |
| `activate` | Enable native Eddy Z and the validated homing/CFS safety routing |
| `configure-wipe` | Generate the fixed napkin wipe from measured coordinates |
| `status` | Show firmware, calibration, native-Z, safety-guard and wipe state |
| `rollback <dir>` | Restore a helper-created backup |

## Important boundaries

- **Do not copy another printer's Eddy calibration curve, USB serial, or napkin-strip Z values.** They are intentionally absent from this repository.
- Do not run `activate` before drive-current and height-map calibration are persisted.
- Do not use this branch as proof of compatibility with `2.3.5.34`, `2.3.5.35`, the newer `1.1.x` K1 Max firmware line, or a different motherboard/CFS-C conversion.
- Creality firmware updates can overwrite patched Klipper files. Run `doctor`/`status` after any firmware change; this release should be treated as a `2.3.5.33` target only.
- The original upstream installer is retained as `legacy-install.sh` for reference and is **not** the recommended installation method for this fork.

See [`docs/VALIDATED-STATE.md`](docs/VALIDATED-STATE.md) for the exact behavior and regression state this helper was derived from.
