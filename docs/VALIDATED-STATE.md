# Validated reference state

This branch now follows the **corrected final production snapshot** created on **2026-10-01** after off-bed cold-start behavior was explicitly tested.

Production snapshot:

```text
known-good-eddy-production-20261001-153849
```

The cleaned archive contains no Python bytecode/cache files and has final SHA256:

```text
11582373c6f9d3886afc58644851a8be1c987da3128618974c2e93091f01e408
```

## Platform

- Creality K1 Max
- official CFS upgrade
- CrealityOS 2.3.5.33
- BTT Eddy Duo over USB
- Eddy used as the native Z virtual endstop
- Creality PRTouch object retained for proprietary CFS compatibility
- fixed external CFS napkin-strip holder

## Corrected cold-start / unknown-Z model

The important correction is that an Eddy reading is **not a reliable physical-clearance measurement until XY geometry is known**.

When XY is unknown, the probe may be physically outside the bed. In that state a low Eddy frequency, `CLEAR_SIDE`, or an outside-calibration-range result can prove the sensor is responding, but it cannot prove that the nozzle is safely clear of the bed.

The validated cold-start sequence is therefore:

1. Z and XY are unknown.
2. `BED_MESH_CLEAR`.
3. Run `EDDY_HOME_STATUS SAMPLES=50 TIMEOUT=2` as a **connectivity-only** test.
   - no intentional motion;
   - failure to communicate stops homing;
   - `CLEAR_SIDE` is **not** interpreted as physical clearance.
4. Use Creality's bounded unknown-Z move before lateral homing.
   - when `z_pos <= 20` or `power_loss == 1`: move `+z_safe_g28`;
   - the validated machine's `z_safe_g28` was 3.0 mm;
   - otherwise move only +0.1 mm.
5. Perform deliberate two-pass Y sensorless homing.
6. Perform deliberate two-pass X sensorless homing.
7. Move XY to the center / native-Z homing position.
8. Synchronize queued XY motion with `M400`, then settle.
9. Run `EDDY_PREHOME_CLEAR MAX_TRAVEL=2.000` while Eddy is now over the bed.
10. Perform native Eddy `G28 Z`.

## Off-bed cold-start validation

This sequence was tested with XY unknown and Eddy physically off the bed.

Observed reference result:

- initial Eddy state: `CLEAR_SIDE` / outside calibration range;
- that state was deliberately **not** treated as nozzle clearance;
- bounded safety lift: +3.000 mm away from the nozzle;
- native final Z: approximately 2.499219 mm;
- independent Eddy height after home: approximately 2.492394 mm;
- difference from configured 2.500000 mm trigger height: approximately -0.007606 mm;
- final Eddy state after homing: `TRIGGERED_SIDE`.

Other validated native-Z results included approximately 2.496875 mm.

## Persisted Z position limitation

Creality's persisted `z_pos` is a coarse remembered commanded position, not an absolute physical bed-position sensor.

The validated investigation found that the stored position is updated only in specific normal toolhead-move conditions; low-level `FORCE_MOVE` does not make it an absolute encoder.

Therefore the installation must not infer exact physical nozzle/bed clearance from `z_pos` alone.

## High-Z Eddy safety

Creality's original high-Z logic can perform a blind `-8 mm` movement based on persisted `z_pos`.

For BTT Eddy systems this blind movement toward the nozzle is disabled. Once XY is centered, live Eddy feedback and native Eddy homing establish the real Z relationship.

The original `-8 mm` behavior remains available for non-Eddy probe configurations.

## Eddy USB disconnect / reconnect behavior

Hot-unplug behavior was validated:

- Klipper remained Ready;
- the main printer MCU remained responsive;
- `GET_POSITION` remained available;
- Klipper reported the Eddy MCU disconnected;
- Eddy operations failed rather than returning stale sensor data.

After hot reconnect:

- Linux redetected the RP2040;
- the persistent `/dev/serial/by-id` path returned;
- the existing Klipper Eddy session did not silently reconnect;
- `FIRMWARE_RESTART` restored Eddy communication.

This fail-stop behavior is preferable to continuing with stale probe data.

## Other validated behaviors

- G28 from a normal homed state
- G28 from an unhomed state
- G28 after a full Klippy restart
- native Eddy Z homing
- post-XY pre-Z Eddy clearance
- deliberate two-pass sensorless Y homing retained
- deliberate two-pass sensorless X homing retained
- M400 synchronization before Eddy sampling at the Z-home XY location
- 20×20 / 400-point Eddy `rapid_scan`
- runtime mesh compensation during the purge line
- complete Creality CFS start-print path

The corrected end-to-end path completed:

```text
BOX_START_PRINT
  → CX_ROUGH_G28
  → corrected protected homing
  → CX_NOZZLE_CLEAR
  → Eddy-safe fixed-height napkin wipe
  → ACCURATE_G28
  → Eddy-aware redundant Z-home handling
  → CX_PRINT_LEVELING_CALIBRATION
  → Eddy CHECK_BED_MESH
  → 20×20 / 400-point rapid_scan
  → eddy_runtime session mesh
  → CX_PRINT_DRAW_ONE_LINE
  → successful purge
```

The final purge state also showed a difference between requested G-code Z and actual toolhead Z, confirming active runtime mesh compensation.

## Intentional Creality behavior retained

- double `_HOME_Y` calls are intentional;
- double `_HOME_X` calls are intentional;
- `prtouch_v2` remains configured for Creality/CFS compatibility;
- existing CFS behavior remains intact;
- the validated nozzle-clean path remains intact.

## Machine-specific values intentionally not shipped as defaults

- Eddy USB serial
- drive-current calibration
- Eddy frequency/height calibration curve
- temperature compensation data
- measured napkin-strip surface Z coordinates

## Superseded reference

This production snapshot supersedes:

```text
known-good-eddy-final-20261001-104541
```

The older snapshot remains useful as a rollback reference, but its validation notes contain an obsolete assumption that pre-XY Eddy `CLEAR_SIDE` could establish physical clearance. Off-bed testing disproved that assumption.

## CI reproduction contract

The cleaned production archive records the whole-file `sensorless.cfg` SHA256:

```text
548fdaa7d19a0eaf5a943febe416bde97dd736987ecf7e2991a5bd61b0caa12c
```

The raw archived `sensorless.cfg` bytes were not available as a standalone file in the accessible history when the public regression fixtures were created. The repository therefore does **not** claim that CI currently reproduces this whole-file hash.

Instead, the saved printer transcripts contain the complete pre-final `_IF_HOME_Z`, `_HOME_Z`, and `homing_override` sections plus the exact final three-block safety patch. CI locks the exact recovered final `_IF_HOME_Z`, exact recovered final `_HOME_Z`, exact pre-XY connectivity-only block, and byte-preserves all non-targeted homing sections through activation.

After activation, `sh install.sh status` reports:

```text
Production safety:     PASS
```

only when those exact recovered safety blocks match and the superseded off-bed `MARGIN=1.000 MAX_TRAVEL=5.000` guard is absent. Otherwise it reports `DRIFT - REVIEW`.

If the original cleaned production archive is later supplied as a repository test artifact, a whole-file SHA256 regression can be added in addition to this structural/exact-section contract.

## Live production verification

Run:

```sh
sh install.sh verify-production
```

The command is read-only and compares the active installation with the final production reference.

Result classes:

- **EXACT** — the active file SHA256 exactly matches the recorded production snapshot.
- **EXPECTED CUSTOM** — the hash differs, but the difference is expected to be machine-specific and the required safety structure validates.
- **DRIFT** — the file is missing or a required safety/compatibility contract does not validate.

Machine-specific files are not required to have the reference printer's bytes. In particular, `printer.cfg`, `btteddy_mcu.cfg`, `eddy_nozzle_clear.cfg`, and portions of `gcode_macro.cfg` may legitimately differ because of USB identity, calibration data, other installed includes, or measured napkin-strip coordinates.

The three isolated compatibility sources `extras/upgrade/ldc1612.py`, `extras/upgrade/probe_eddy_current.py`, and `extras/upgrade/bulk_sensor.py` are treated as exact production sources and should match their recorded SHA256 values.

The production `eddy_z_acquire.py` checksum is known, but its complete production bytes were not preserved as a retrievable repository artifact. A non-exact public helper is therefore accepted only when its required bounded-motion and fail-stop safety behavior is present; it is never falsely labeled byte-identical.

The command exits with status 3 when any `DRIFT` item is found, making it suitable for scripted audits while still performing no writes or printer motion.

## Firmware-update preservation model

The public helper now includes an **audit-before-repair** workflow for future Creality firmware updates.

Before updating:

```sh
sh install.sh pre-update-snapshot
```

This records the complete printer config plus the Klipper/core/service files that matter to the K1 Max + CFS + Eddy integration. It also records file SHA256 values, sizes, symlink targets and the starting firmware version.

After updating:

```sh
sh install.sh audit-after-update <snapshot>
```

The audit can run even when the printer is no longer on 2.3.5.33. It reports every captured path that is `CHANGED`, `MISSING`, or `NEW`, and rechecks the production homing safety contract.

It intentionally performs **no repair**. If any captured file was changed or removed, it exits 4 and requires review before any old file is restored. This prevents a 2.3.5.33 Klipper or CFS file from being copied blindly onto a newer, potentially incompatible firmware.

CI covers both an unchanged post-update comparison and a simulated firmware overwrite where `sensorless.cfg`, `eddy_z_acquire.py`, and the firmware version are changed. The simulated audit must detect the differences, preserve the altered files, and return the review-required exit code.

The public helper and tests should follow the corrected production model above.
