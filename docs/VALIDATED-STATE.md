# Validated reference state

This branch was derived from the final production snapshot taken on **2026-10-01** after the K1 Max + CFS + BTT Eddy integration passed its end-to-end regression.

## Platform

- Creality K1 Max
- Official CFS upgrade
- CrealityOS 2.3.5.33
- BTT Eddy Duo over USB
- Eddy used as the native Z virtual endstop
- Creality PRTouch object retained for proprietary CFS compatibility
- fixed external CFS napkin-strip holder

## Behaviors validated on the source machine

- G28 from a normal homed state
- G28 from an unhomed state
- G28 after a full Klippy restart
- native Eddy Z homing
- pre-Z-home Eddy clearance
- power-loss / unknown-Z pre-XY clearance
- deliberate two-pass sensorless Y homing retained
- deliberate two-pass sensorless X homing retained
- M400 synchronization before Eddy sampling at the Z-home XY location
- 20×20 Eddy `rapid_scan`
- runtime mesh compensation during the purge line
- complete Creality CFS start-print path

The simulated power-loss validation began close to the bed and required 30 verified +0.050 mm recovery moves before XY was permitted. Total recovery movement was 1.500 mm; the final reported Eddy height was approximately 3.508 mm. Native Z homing then completed at approximately 2.498 mm.

These measurements document the tested machine; they are **not installation constants**.

## Machine-specific values intentionally not shipped as defaults

- Eddy USB serial
- drive-current calibration
- Eddy frequency/height calibration curve
- temperature compensation data
- measured napkin-strip surface Z coordinates

The public helper discovers or asks for these values and blocks unsafe stages when they are missing.

## Source snapshot integrity

The final on-printer production snapshot was archived before this packaging work. The installer is based on its behavior and file history, not on a newer upstream firmware assumption.

The public branch also retains the upstream GPLv3 license and source history.
