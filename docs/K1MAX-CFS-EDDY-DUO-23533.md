# Installation guide — K1 Max + CFS + BTT Eddy Duo on 2.3.5.33

This guide documents the configuration validated on a Creality K1 Max with the official CFS upgrade. It is intentionally conservative: the helper stages Eddy first, requires calibration, and only then enables native Eddy Z homing.

## 1. Firmware target

**Supported and validated: CrealityOS 2.3.5.33.**

The helper refuses a different version by default. Do not assume a newer firmware is interchangeable: Creality changes its Klipper/Python/CFS files between releases.

If your printer is not already on 2.3.5.33, obtain the appropriate official firmware image from a trusted Creality source and use Creality's USB firmware-update procedure. Preserve a copy of your current configuration before changing firmware.

## 2. Enable root / SSH

On firmware that exposes Creality's root option:

1. On the printer screen open **Settings → Root account information**.
2. Read and accept the disclaimer.
3. Wait for the required countdown and enable root access.
4. SSH to the printer as `root`.
5. On the commonly documented rooted K1 firmware line, the factory SSH password is `creality_2023`. If your printer displays different credentials, use what the printer shows instead.

Reference: Guilouz's Creality Helper Script Wiki, “Install & Update Rooted Firmware.”

After logging in, confirm the firmware before doing anything else:

```sh
grep -R "2.3.5.33" /etc/ota_info /usr/data/creality/userdata/config 2>/dev/null
```

## 3. Install the physical CFS upgrade first

The CFS upgrade should be working in the Creality configuration before adding Eddy. In particular, the printer should already have its CFS/box configuration and the normal CFS start-print workflow.

The helper checks for `/usr/data/printer_data/config/box.cfg` and refuses to continue when the expected CFS configuration is absent.

## 4. Mount and flash BTT Eddy Duo

Use a rigid Eddy Duo mount appropriate to your toolhead. BIGTREETECH recommends the Eddy sensing board be mounted approximately **2–3 mm above the nozzle**. That is the physical mounting height; it is **not** the 20 mm distance used temporarily during drive-current calibration.

For the validated K1 Max mount, the probe center was approximately:

- X offset: `-23 mm`
- Y offset: `0 mm`

Measure your own mount. The helper makes X/Y offsets explicit instead of embedding one printer's values.

Flash Eddy Duo for Klipper/USB using the current BIGTREETECH Eddy Duo instructions. After connection, verify the printer sees one Eddy/RP2040 serial:

```sh
ls -l /dev/serial/by-id/
```

The helper can auto-detect a single Klipper RP2040/Eddy entry, or you can provide it with `--eddy-serial`.

## 5. Install the CFS napkin-strip saver

The validated setup uses a fixed napkin-strip holder rather than relying on a napkin attached to the removable build plate:

**K1 Max Napkin Strip Saver for use with CFS Upgrade Kit**  
Designer: **Eric Sten (@EricSten_321774)**  
Printables model: **1286860**

The napkin is non-conductive. Eddy cannot infer the wipe surface height, so **never copy another machine's wipe Z coordinates**. This repository intentionally ships with `NOZZLE_CLEAR` blocked until the individual printer is measured.

## 6. Prepare Moonraker / Fluidd and put this branch on the printer

Before continuing, follow **[Creality Helper Script, Entware and Git — supported profile](CREALITY-HELPER-SCRIPT.md)**.

For the supported configuration:

- **Moonraker and Nginx are required** from the Creality Helper Script.
- **Fluidd is required** for this guide.
- Entware/Git are optional infrastructure if you want to clone/update repositories directly on the printer.
- All other Helper Script items are optional, explicitly unsupported, or blocked as documented in the compatibility matrix.
- Enable **Tools → Prevent updating Klipper configuration files** before installing the Eddy conversion.

After Git is working, clone this branch:

```sh
cd /usr/data
git clone -b k1max-cfs-eddy-duo-2.3.5.33 \
  https://github.com/thewolfman56/K1-Klipper-Eddy.git
cd K1-Klipper-Eddy
```

If you prefer not to install Git, a release ZIP/USB copy can be used instead.

Before any write:

```sh
sh install.sh doctor
```

## 7. Stage Eddy — do not enable native Z yet

Example for the validated mount geometry:

```sh
sh install.sh stage --x-offset -23 --y-offset 0
```

If auto-detection cannot uniquely identify Eddy:

```sh
sh install.sh stage \
  --eddy-serial /dev/serial/by-id/usb-Klipper_rp2040_YOUR_ID-if00 \
  --x-offset -23 --y-offset 0
```

Stage does all of the following without sending motion G-code:

- creates a timestamped rollback snapshot;
- preserves Creality's original bed-mesh implementation;
- installs the Eddy-compatible Klipper modules and conditional bed-mesh router;
- creates `btteddy_mcu.cfg`;
- creates a fail-closed CFS wipe macro;
- adds the Eddy includes;
- preserves Creality's bounded unhomed-Z safety move while Eddy is only staged; the probe is not trusted for off-bed clearance before XY is known.

Review the changed files, then issue **`FIRMWARE_RESTART` from Fluidd**.

Do not print during the staging/calibration phase.

## 8. Eddy drive-current calibration

BIGTREETECH's documented sequence starts with Eddy approximately **20 mm above the bed**. This 20 mm position is only for drive-current calibration.

With the machine positioned safely, run from Fluidd:

```text
LDC_CALIBRATE_DRIVE_CURRENT CHIP=btt_eddy
```

Normally BIGTREETECH instructs users to run `SAVE_CONFIG`. On this Creality build, use the helper instead so unrelated Creality pending state is not blindly written:

```sh
sh install.sh persist
```

Then review `btteddy_mcu.cfg` and issue `FIRMWARE_RESTART`.

Check:

```sh
sh install.sh status
sh install.sh verify-production
```

The drive-current line should now be present.

## 9. Map Eddy frequency to nozzle height

Use BIGTREETECH's Eddy height-mapping procedure. The current BTT documentation offers the automatic command:

```text
PROBE_EDDY_CURRENT_CALIBRATE_AUTO CHIP=btt_eddy
```

or the manual mapping command:

```text
PROBE_EDDY_CURRENT_CALIBRATE CHIP=btt_eddy
```

Follow the paper-test prompts carefully. When Klipper reports that the mapping is ready to be saved, persist only the Eddy pending values:

```sh
sh install.sh persist
```

Review, restart firmware, and verify:

```sh
sh install.sh status
```

The helper requires a substantial mapping table before it will enable native Eddy Z.

## 10. Activate native Eddy Z

When `status` shows both drive-current calibration and the height map:

```sh
sh install.sh activate
```

Activation:

- changes `[stepper_z]` to `endstop_pin: probe:z_virtual_endstop`;
- removes the TMC `position_endstop`;
- keeps the Creality PRTouch object available for CFS compatibility;
- when XY/Z are unknown, clears the mesh and runs `EDDY_HOME_STATUS SAMPLES=50 TIMEOUT=2` as a **connectivity-only** check; `CLEAR_SIDE` is not interpreted as nozzle clearance while the probe may be off-bed;
- preserves Creality's bounded unhomed-Z-away move before XY homing: `+z_safe_g28` when `z_pos <= 20` or `power_loss == 1`, otherwise `+0.1 mm`;
- disables Creality's persisted-`z_pos` blind `-8 mm` move toward the nozzle for Eddy systems, while preserving it for non-Eddy probes;
- centers XY, waits for motion with `M400` plus settle time, then runs `EDDY_PREHOME_CLEAR MAX_TRAVEL=2.000` immediately before native Z homing;
- keeps the original deliberate two-pass Y and two-pass X sensorless homing sequence;
- changes `ACCURATE_G28` so Eddy systems do not perform Creality's redundant second Z home.

Review the files and issue `FIRMWARE_RESTART`.

### First homing validation

Keep a hand on printer power.

1. Start with the toolhead/bed in a mechanically safe position.
2. Use `EDDY_HOME_STATUS` to confirm the sensor is producing plausible data.
3. Validate X/Y homing.
4. Validate Z homing.
5. Only after those pass, validate a full `G28`.
6. Repeat once after a full Klippy restart so the unknown-Z cold-start path is exercised.

The corrected production validation showed why Eddy must **not** be used as a pre-XY clearance sensor: with XY unknown, the probe can be physically off the bed and report `CLEAR_SIDE` / outside-calibration-range even though that says nothing about nozzle-to-bed clearance. The supported path therefore uses Creality's bounded unknown-Z move before XY, then uses live Eddy clearance only after XY has been centered over the bed. Do not use this fork as a generic motion-platform installer.

## 11. Measure and enable the fixed napkin wipe

The helper intentionally blocks `NOZZLE_CLEAR` until this step.

Measure the napkin strip surface near the beginning and end of the wipe path on **your printer**. Then:

```sh
sh install.sh configure-wipe \
  --start-x <x> --start-y <y> --start-surface-z <z> \
  --end-x <x> --end-y <y> --end-surface-z <z> \
  --confirm-measured
```

Defaults reproduce the validated wipe geometry relative to your measurements:

- approach clearance: `+0.20 mm` above the measured start surface;
- wipe depth at the end: `0.30 mm` below the measured end surface.

Those deltas can be changed with `--approach-clearance` and `--wipe-depth`, but the surface Z values themselves must come from your printer.

Review the generated macro, issue `FIRMWARE_RESTART`, and test the wipe with immediate access to power.

## 12. Final validation

```sh
sh install.sh status
```

Expected state:

- firmware `2.3.5.33`;
- Eddy drive current present;
- Eddy mapping populated;
- native Eddy Z active;
- pre-XY Eddy connectivity-only check present;
- bounded Creality unknown-Z move present;
- unsafe off-bed `MARGIN=1.000 MAX_TRAVEL=5.000` Eddy-clearance block absent;
- pre-Z-home Eddy clearance guard present;
- fixed napkin wipe configured.

Then validate the full CFS print path. The known-good machine completed:

```text
BOX_START_PRINT
  → CX_ROUGH_G28
  → protected G28
  → CX_NOZZLE_CLEAR
  → fixed-height napkin wipe
  → ACCURATE_G28 (second Z skipped for Eddy)
  → CX_PRINT_LEVELING_CALIBRATION
  → CHECK_BED_MESH
  → 20×20 rapid_scan
  → CX_PRINT_DRAW_ONE_LINE
```

## 13. Rollback

Every write stage prints the backup path it created. To return to one of those snapshots:

```sh
sh install.sh rollback 20261001-120000-pre-stage
```

or pass the full backup path.

Rollback first creates a safety snapshot of the current state, then restores the complete printer config directory and every Klipper Python file the helper touched. It does not issue `FIRMWARE_RESTART` automatically.

## Firmware updates

Assume a Creality firmware update can replace patched Klipper files. After any firmware change, do **not** simply re-run `activate`. Start with `doctor` and treat the new firmware as unsupported until its Creality CFS files and homing behavior have been reviewed.
