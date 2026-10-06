# Start Here — Complete K1 Max + Creality CFS + BTT Eddy Duo Installation

This is the **single start-to-finish installation guide** for the supported configuration:

- Creality K1 Max
- official Creality CFS upgrade
- **CrealityOS 2.3.5.33**
- BTT Eddy Duo over USB
- Moonraker + Nginx + Fluidd
- fixed CFS napkin-strip wipe
- OrcaSlicer CFS startup/tool-change configuration

The normal installation path is intentionally collected here so a new installer does not have to jump between several documents. The other documents in this repository remain deeper technical references.

> **Recommended starting point:** begin with a **factory-reset or freshly reflashed official CrealityOS 2.3.5.33 installation** before rooting the printer or installing Helper Script modifications. This is not mandatory for an already-clean, known installation, but it minimizes unknown leftovers from prior Klipper, macro, probe, Helper Script, or CFS modifications.
>
> A factory reset/reflash can erase configuration and user data. Preserve anything you need first. After the reset/reflash, confirm the printer is actually running **2.3.5.33** before continuing.

## Safety, warranty, and responsibility

**Use this project entirely at your own risk.** This is an unofficial community project. Rooting the printer, changing Klipper/configuration files, adding a third-party probe, and modifying CFS workflows may affect manufacturer warranty or service eligibility.

These procedures affect homing, probing, Z motion, bed meshing, nozzle wiping, and CFS operation. Incorrect hardware, measurements, calibration, firmware, or slicer G-code can cause collisions or damage. Keep immediate access to printer power during every first-motion test.

Do not copy another printer's Eddy USB serial, drive-current calibration, height map, probe offsets, or napkin-strip Z measurements.

The project is provided without warranty under GPLv3. See [`LICENSE`](../LICENSE).

---

# Part 1 — Establish the clean supported base

## Step 1 — Start with official CrealityOS 2.3.5.33

Recommended sequence:

1. Factory-reset the K1 Max and/or freshly install official **CrealityOS 2.3.5.33** using Creality's supported firmware procedure.
2. Complete normal printer startup.
3. Do **not** restore old custom Klipper or configuration files from another firmware revision.
4. Confirm the firmware version after root/SSH is enabled.

Do not continue on a different firmware revision. This release does not claim support for `2.3.5.34`, `2.3.5.35`, the newer `1.1.x` firmware line, another mainboard, or a CFS-C conversion.

## Step 2 — Install and validate the official CFS upgrade first

Before adding Eddy:

1. Install the official Creality CFS upgrade using Creality's instructions.
2. Confirm the CFS is detected and operates normally in the stock Creality configuration.
3. Confirm the printer has its CFS configuration, including:

~~~text
/usr/data/printer_data/config/box.cfg
~~~

Do not troubleshoot the initial CFS install and Eddy conversion at the same time. Get the stock CFS path working first.

## Step 3 — Enable root / SSH

On the printer screen:

1. Open **Settings → Root account information**.
2. Read and accept Creality's warning.
3. Wait for the required countdown.
4. Enable root access.
5. SSH to the printer as `root`.

On commonly documented K1 firmware in this line, the factory SSH password is:

~~~text
creality_2023
~~~

If your printer displays different credentials, use those instead.

Confirm the firmware:

~~~sh
grep -R "2.3.5.33" /etc/ota_info /usr/data/creality/userdata/config 2>/dev/null
~~~

**Gate:** stop here unless `2.3.5.33` is confirmed.

---

# Part 2 — Install the supported Helper Script base

CrealityOS 2.3.5.33 CFS systems may have a missing or unusable stock Git. The validated path installs Entware Git first.

## Step 4 — Install Entware

From SSH as `root`:

~~~sh
wget http://bin.entware.net/mipselsf-k3.4/installer/generic.sh -O - | sh
export PATH=/opt/bin:/opt/sbin:$PATH
/opt/bin/opkg --version
/opt/bin/opkg update
~~~

## Step 5 — Install Git from Entware

~~~sh
/opt/bin/opkg install git
/opt/bin/opkg install git-http
/opt/bin/git --version
~~~

Preserve the original Creality Git binary once if it exists:

~~~sh
if [ -e /usr/bin/git ] && [ ! -L /usr/bin/git ] && [ ! -e /usr/bin/git.creality.bak ]; then cp -a /usr/bin/git /usr/bin/git.creality.bak; fi
~~~

Point `/usr/bin/git` to Entware Git:

~~~sh
rm -f /usr/bin/git
ln -s /opt/bin/git /usr/bin/git
hash -r
ls -l /usr/bin/git
git --version
~~~

Expected:

~~~text
/usr/bin/git -> /opt/bin/git
~~~

## Step 6 — Clone the original Guilouz Creality Helper Script

~~~sh
git clone --depth 1 https://github.com/Guilouz/Creality-Helper-Script.git /usr/data/helper-script
sh /usr/data/helper-script/helper.sh
~~~

If Git reports a TLS/certificate problem, verify the printer's date/time first. Do not permanently disable certificate verification.

## Step 7 — Install only the required Helper Script items

From the Helper Script **Install** menu, install:

~~~text
1) Moonraker and Nginx
2) Fluidd (port 4408)
~~~

If Moonraker reports an unsafe Git repository:

~~~sh
git config --global --add safe.directory /usr/data/moonraker/moonraker
~~~

Then rerun the Moonraker operation.

Fluidd is normally available at:

~~~text
http://PRINTER_IP:4408/
~~~

Next open the Helper Script **Tools** menu and select:

~~~text
1) Prevent updating Klipper configuration files
~~~

This protection is required before the Eddy conversion so Creality's normal service behavior does not silently overwrite the custom configuration.

Do not later select **Allow updating Klipper configuration files** unless you intentionally want to return to Creality-managed configuration behavior.

### Optional add-ons

For the cleanest first installation, skip optional add-ons until the core K1 Max + CFS + Eddy path is working. The reference machine later validated Improved Shapers, Moonraker Timelapse, Camera Settings Control, OctoEverywhere, and Mobileraker Companion, but none are required for Eddy/CFS operation.

---

# Part 3 — Install the physical Eddy and wipe hardware

## Step 8 — Mount and flash BTT Eddy Duo

Use a rigid K1 Max Eddy Duo mount. BTT mounting guidance places the Eddy sensing board roughly **2–3 mm above the nozzle**.

The validated reference mount measured approximately:

~~~text
X offset: -23 mm
Y offset:   0 mm
~~~

**Measure your own mount.** Do not assume these values are correct for another mount.

Flash the Eddy Duo for Klipper USB operation using BTT's Eddy Duo procedure, connect it, then verify the USB device:

~~~sh
ls -l /dev/serial/by-id/
~~~

There should be one identifiable Klipper RP2040/Eddy serial for automatic detection.

## Step 9 — Install the fixed CFS napkin-strip holder

The validated setup used:

~~~text
K1 Max Napkin Strip Saver for use with CFS Upgrade Kit
Designer: Eric Sten (@EricSten_321774)
Printables model: 1286860
~~~

Install the holder securely.

The napkin is non-conductive, so Eddy cannot detect its surface. Wipe Z values must be measured on each printer later.

---

# Part 4 — Install this repository

## Step 10 — Clone the stable release

For the current documentation release, use `v1.0.1`:

~~~sh
cd /usr/data
git clone --branch v1.0.1 --depth 1 https://github.com/thewolfman56/K1-Klipper-Eddy.git
cd K1-Klipper-Eddy
~~~

If `/usr/data/K1-Klipper-Eddy` already exists from an earlier attempt, inspect or remove it intentionally instead of overwriting it blindly.

### Existing working installation — add the Eddy temperature graphs

Fresh installs created by the current helper already include both Eddy temperature objects. An older working installation may have the calibrated Eddy probe but lack the graphable temperature objects.

After updating the repository to a version that contains the migration command, run:

~~~sh
cd /usr/data/K1-Klipper-Eddy
sh install.sh status
sh install.sh upgrade-temperatures
~~~

The migration is intentionally narrow:

- it requires the existing `[mcu eddy]` and `[probe_eddy_current btt_eddy]` layout;
- it creates a helper rollback backup before changing the config;
- it does **not** rewrite the Eddy probe section, drive current, calibration curve, offsets, Z routing, homing macros, CFS macros, or wipe configuration;
- it adds only missing `[temperature_sensor btt_eddy_mcu]` and `[temperature_probe btt_eddy]` sections;
- it refuses to overwrite a conflicting existing temperature section;
- running it again after a successful upgrade makes no change.

Review `/usr/data/printer_data/config/btteddy_mcu.cfg`, then in Fluidd issue:

~~~text
FIRMWARE_RESTART
~~~

Verify:

~~~sh
sh install.sh status
~~~

Expected status lines:

~~~text
Eddy probe temp:       present
Eddy MCU temp:         present
~~~

Fluidd can then expose **BTT Eddy** and **BTT Eddy MCU** as temperature traces/cards. This upgrade does not require Eddy drive-current or height-map recalibration because the calibrated `[probe_eddy_current btt_eddy]` section is preserved.

## Step 11 — Run the read-only preflight

~~~sh
sh install.sh doctor
~~~

Confirm the core preflight identifies:

- firmware `2.3.5.33`;
- `printer.cfg`;
- `sensorless.cfg`;
- CFS `box.cfg`;
- one Eddy USB serial.

Resolve any core failure before continuing.

## Step 12 — Create a manual starting backup

`stage` creates its own backup, but an extra starting snapshot is recommended:

~~~sh
sh install.sh backup
~~~

Record the printed backup directory.

---

# Part 5 — Stage Eddy without enabling native Z

## Step 13 — Stage the Eddy configuration

Use the X/Y offsets measured from **your** mount.

Example matching the validated mount:

~~~sh
sh install.sh stage --x-offset -23 --y-offset 0
~~~

If automatic serial detection is ambiguous:

~~~sh
sh install.sh stage --eddy-serial /dev/serial/by-id/usb-Klipper_rp2040_YOUR_ID-if00 --x-offset -23 --y-offset 0
~~~

`stage`:

- creates a rollback backup;
- preserves Creality's original bed-mesh implementation;
- installs isolated Eddy compatibility modules;
- creates the Eddy MCU configuration;
- adds the required includes;
- creates a fail-closed wipe macro;
- leaves native Eddy Z disabled until calibration is complete.

Review the changes.

From Fluidd issue:

~~~text
FIRMWARE_RESTART
~~~

Do not print during staging/calibration.

---

# Part 6 — Calibrate Eddy

## Step 14 — Calibrate drive current

Position the toolhead safely with Eddy/nozzle approximately **20 mm above the bed** for the drive-current calibration procedure.

In Fluidd:

~~~text
LDC_CALIBRATE_DRIVE_CURRENT CHIP=btt_eddy
~~~

When calibration produces pending values, do **not** blindly use `SAVE_CONFIG` on this Creality build.

From SSH:

~~~sh
sh install.sh persist
~~~

Review `btteddy_mcu.cfg`, then in Fluidd:

~~~text
FIRMWARE_RESTART
~~~

Check:

~~~sh
sh install.sh status
sh install.sh verify-production
~~~

The drive-current value should now be present.

## Step 15 — Calibrate Eddy height/frequency mapping

Use BTT's Eddy height-mapping procedure.

Automatic command:

~~~text
PROBE_EDDY_CURRENT_CALIBRATE_AUTO CHIP=btt_eddy
~~~

or manual mapping:

~~~text
PROBE_EDDY_CURRENT_CALIBRATE CHIP=btt_eddy
~~~

Follow the paper-test prompts carefully.

When Klipper reports the mapping is ready to save:

~~~sh
sh install.sh persist
~~~

Then issue:

~~~text
FIRMWARE_RESTART
~~~

Verify:

~~~sh
sh install.sh status
~~~

Do not activate native Eddy Z until `status` shows both a persisted drive current and a populated height map.

---

# Part 7 — Activate native Eddy Z

## Step 16 — Activate

~~~sh
sh install.sh activate
~~~

Activation installs the validated safety routing, including:

- `probe:z_virtual_endstop` for Z;
- corrected unknown-Z cold-start handling;
- Eddy connectivity-only checking while XY is unknown;
- Creality's bounded unknown-Z-away move before XY homing;
- intentional two-pass Y and X sensorless homing;
- live Eddy clearance checking only after XY is over the bed;
- `EDDY_PREHOME_CLEAR MAX_TRAVEL=2.000` immediately before native Z homing;
- Eddy-aware `ACCURATE_G28`;
- removal of Creality's pre-CFS `CX_PRINT_DRAW_ONE_LINE` purge from `START_PRINT`.

Review the configuration, then issue:

~~~text
FIRMWARE_RESTART
~~~

---

# Part 8 — First-motion validation

## Step 17 — Confirm Eddy communication

Keep immediate access to printer power.

In Fluidd:

~~~text
EDDY_HOME_STATUS SAMPLES=50 TIMEOUT=2
~~~

Confirm plausible live data.

Do **not** interpret off-bed `CLEAR_SIDE` as physical nozzle clearance while XY is unknown.

## Step 18 — Validate homing progressively

Use a mechanically safe starting position.

First:

~~~text
G28 Y
~~~

Confirm Y homes correctly.

Then:

~~~text
G28 X
~~~

Confirm X homes correctly.

Then:

~~~text
G28 Z
~~~

Confirm native Eddy Z homing completes safely.

Only after those individual checks pass:

~~~text
G28
~~~

Confirm the complete homing path.

Repeat a full `G28` after a full Klippy/Firmware restart so the unknown-XYZ cold-start path is exercised.

**Cut power immediately if motion is unexpected.**

---

# Part 9 — Measure and enable the fixed napkin wipe

## Step 19 — Measure the napkin surface on this printer

`NOZZLE_CLEAR` intentionally remains blocked until real measurements are provided.

Measure the napkin surface near the beginning and end of the intended wipe and record:

~~~text
start X
start Y
start surface Z
end X
end Y
end surface Z
~~~

Do not copy the reference printer's Z measurements.

## Step 20 — Configure the wipe

~~~sh
sh install.sh configure-wipe --start-x <x> --start-y <y> --start-surface-z <z> --end-x <x> --end-y <y> --end-surface-z <z> --confirm-measured
~~~

Default relative geometry:

~~~text
approach clearance: +0.20 mm
wipe end depth:      0.30 mm below measured end surface
~~~

Review the generated macro, then:

~~~text
FIRMWARE_RESTART
~~~

## Step 21 — Physically test the wipe

With immediate access to power, verify:

- approach clears the napkin;
- contact occurs only on the intended napkin surface;
- pressure is acceptable;
- the Eddy mount clears the chute/holder;
- the final lift clears safely.

Do not proceed to printing until the wipe is physically safe.

---

# Part 10 — Verify the installed printer

## Step 22 — Run the read-only checks

~~~sh
sh install.sh status
sh install.sh verify-production
sh install.sh release-readiness
~~~

A valid machine-specific installation may show `EXPECTED CUSTOM` for printer-specific files.

`verify-production` should finish with:

~~~text
0 DRIFT
Result: production safety profile accepted
~~~

`release-readiness` must contain no `FAIL`.

---

# Part 11 — Configure OrcaSlicer

The slicer setup is part of the supported installation. The reference machine was validated with OrcaSlicer 2.4.2.

## Step 23 — Machine Start G-code

Open:

~~~text
Printer preset → Machine G-code → Machine start G-code
~~~

Use exactly:

~~~gcode
M140 S0
M104 S0

start_print EXTRUDER_TEMP=[nozzle_temperature_initial_layer] BED_TEMP=[bed_temperature_initial_layer_single] CHAMBER_TEMP=[chamber_temperature]

T{current_extruder}
RESPOND TYPE=command MSG="Loading Filament from CFS Slot "{current_extruder+1}

M109 S[nozzle_temperature_initial_layer]

M204 S2000
G1 Z3 F600
M83
G1 Y150 F12000
G1 X0 F12000
G1 Z0.2 F600
G1 X0 Y150 F6000
G1 X0 Y0 E15 F6000
G1 X150 Y0 E15 F6000
G92 E0
G1 Z1 F600
~~~

Required order:

~~~text
START_PRINT
  → home
  → Eddy-safe napkin wipe
  → Eddy mesh
  → return to Orca without purging

T{current_extruder}
  → CFS loads selected filament

M109
  → return to first-layer temperature

Orca purge
  → purge the filament that is actually loaded
~~~

## Step 24 — Change Filament G-code

Open:

~~~text
Printer preset → Machine G-code → Change filament G-code
~~~

Use exactly:

~~~gcode
G2 Z{z_after_toolchange + 0.8} I0.86 J0.86 P1 F10000
G1 X0 Y245 F30000
{if z_after_toolchange > 0}
G1 Z{z_after_toolchange} F600
{endif}
~~~

The conditional Z restore is important. An unconditional `G1 Z{z_after_toolchange} F600` can generate `G1 Z0 F600` during the initial redundant tool selection.

## Step 25 — Keep your own filament/spool IDs

If your filament profile uses:

~~~text
SET_ACTIVE_SPOOL ID=...
~~~

use your own spool IDs. Do not copy the reference printer's IDs.

## Step 26 — Reslice after changing Machine G-code

Old G-code files retain old startup commands. **Reslice the model.**

Inspect the new G-code. It must contain zero executable occurrences of:

~~~gcode
CFS_NOZZLE_CLEAR
CFS_NOZZLE_CLEAN
CX_PRINT_DRAW_ONE_LINE
~~~

The validated reference slice also contained no standalone:

~~~gcode
BOX_NOZZLE_CLEAN
~~~

`CX_NOZZLE_CLEAR` remains an internal printer-side call from `START_PRINT` and should not be added separately to slicer startup G-code.

Expected beginning:

~~~gcode
start_print EXTRUDER_TEMP=230 BED_TEMP=60 CHAMBER_TEMP=0
T0
RESPOND TYPE=command MSG="Loading Filament from CFS Slot "1
M109 S230
~~~

---

# Part 12 — First controlled print

## Step 27 — Use a small CFS test print

Choose a small model with a simple first layer. For full CFS validation, include at least one real color/tool change.

Keep immediate access to power.

## Step 28 — Observe the startup path

Expected path:

~~~text
START_PRINT
  → BOX_START_PRINT
  → CX_ROUGH_G28
  → protected homing
  → CX_NOZZLE_CLEAR
  → fixed-height Eddy-safe napkin wipe
  → ACCURATE_G28
  → Eddy-aware redundant-Z handling
  → CX_PRINT_LEVELING_CALIBRATION
  → CHECK_BED_MESH
  → 20×20 / 400-point rapid_scan
  → return to Orca WITHOUT CX_PRINT_DRAW_ONE_LINE

T{current_extruder}
  → selected CFS filament loads

M109
  → nozzle returns to first-layer temperature

Orca custom purge
  → purge occurs after CFS load

print
~~~

Confirm:

- wipe is physically safe;
- homing is correct;
- 20×20 Eddy mesh completes;
- CFS loads the selected first tool;
- purge occurs only after the CFS load;
- first-layer Z is correct.

## Step 29 — Validate a real tool change

For a multi-color test verify:

- normal CFS cutter path completes;
- normal purge/flush path clears the Eddy Duo mount;
- the next tool loads;
- prime-tower/wipe continuation resumes;
- printing returns to the intended Z.

The reference machine physically completed this T0 → T1 path.

---

# Part 13 — Freeze the working installation

## Step 30 — Final health commands

After a successful test print:

~~~sh
sh install.sh doctor
sh install.sh status
sh install.sh verify-production
sh install.sh release-readiness
~~~

Resolve any `DRIFT` or `FAIL` before considering the install complete.

## Step 31 — Create a final helper backup

~~~sh
sh install.sh backup
~~~

Record the backup directory.

## Step 32 — Create a firmware-update snapshot

~~~sh
sh install.sh pre-update-snapshot
~~~

Record the snapshot directory.

This snapshot preserves the full printer config, firmware version, and the relevant Klipper/system/service files and metadata.

---

# Part 14 — Future firmware updates

Before any future Creality firmware update:

~~~sh
sh install.sh pre-update-snapshot
~~~

After updating and rebooting, **do not blindly restore old 2.3.5.33 files**.

Run:

~~~sh
sh install.sh audit-after-update <snapshot-directory>
~~~

Review every `CHANGED`, `MISSING`, and `NEW` item before restoring anything.

A newer firmware is not supported merely because the old configuration appears to start.

---

# Part 15 — Recovery

To restore a helper-created backup:

~~~sh
sh install.sh rollback <backup-directory>
~~~

Rollback first creates a safety snapshot of the current state, then restores the helper-managed config and Klipper files. It does not automatically issue `FIRMWARE_RESTART`.

Review the result before restarting Klipper.

---

# Final completion checklist

- [ ] Began from a known clean/factory-reset or freshly reflashed official `2.3.5.33` base.
- [ ] Official CFS worked before Eddy changes.
- [ ] Root/SSH works.
- [ ] Entware Git works.
- [ ] Moonraker/Nginx installed.
- [ ] Fluidd installed.
- [ ] **Prevent updating Klipper configuration files** enabled.
- [ ] Eddy Duo rigidly mounted and detected over USB.
- [ ] Probe X/Y offsets measured for this mount.
- [ ] Fixed CFS napkin holder installed.
- [ ] `doctor` core preflight passes.
- [ ] Starting helper backup created.
- [ ] Eddy staged.
- [ ] Drive current calibrated and persisted.
- [ ] Eddy height map calibrated and persisted.
- [ ] Native Eddy Z activated.
- [ ] Y, X, Z, and full cold-start homing validated.
- [ ] Napkin surface measured on this printer.
- [ ] Fixed wipe configured and physically validated.
- [ ] `verify-production` reports `0 DRIFT`.
- [ ] `release-readiness` reports no `FAIL`.
- [ ] Orca Machine Start G-code replaced.
- [ ] Orca Change Filament G-code replaced.
- [ ] Model resliced.
- [ ] New G-code contains no `CFS_NOZZLE_CLEAR`.
- [ ] New G-code contains no `CFS_NOZZLE_CLEAN`.
- [ ] New G-code contains no `CX_PRINT_DRAW_ONE_LINE`.
- [ ] Controlled first print passes.
- [ ] Real CFS tool change passes if multi-color operation is required.
- [ ] Final helper backup created.
- [ ] Pre-firmware-update snapshot created.

When every applicable item is complete, the printer is at the supported K1 Max + official CFS + BTT Eddy Duo CrealityOS 2.3.5.33 configuration documented by this repository.

## Deeper technical reference

This guide is intended to be sufficient for the normal install. These files remain available for troubleshooting and technical detail:

- [`K1MAX-CFS-EDDY-DUO-23533.md`](K1MAX-CFS-EDDY-DUO-23533.md)
- [`CREALITY-HELPER-SCRIPT.md`](CREALITY-HELPER-SCRIPT.md)
- [`ORCASLICER-CFS-GCODE.md`](ORCASLICER-CFS-GCODE.md)
- [`VALIDATED-STATE.md`](VALIDATED-STATE.md)
- [`RELEASE-CHECKLIST.md`](RELEASE-CHECKLIST.md)
