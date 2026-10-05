# OrcaSlicer machine G-code for K1 Max + CFS + BTT Eddy

This is the **validated OrcaSlicer startup/tool-change configuration** for the
K1 Max + official CFS + BTT Eddy Duo profile documented by this repository.

Validated on the reference printer with:

- Creality K1 Max
- official CFS upgrade
- CrealityOS 2.3.5.33
- BTT Eddy Duo
- OrcaSlicer 2.4.2
- fixed Eddy-safe CFS napkin-strip wipe

The physical regression on 2026-10-02 completed the corrected startup purge,
first layer, and a real mid-print CFS tool change successfully. A final
2026-10-05 regression then re-audited the generated G-code, the live
START_PRINT chain, the normal CFS cutter/purge path, T0 -> T1 tool change, and
the prime-tower continuation before freezing the production-known-good
baseline.

## Why this slicer configuration is required

Creality's stock `START_PRINT` ends with `CX_PRINT_DRAW_ONE_LINE`. That purge
occurs **before** OrcaSlicer emits its first `T...` command, so with CFS the
printer can purge before the selected filament is loaded.

This project patches `START_PRINT` during `activate` so that:

- `CX_NOZZLE_CLEAR` remains in `START_PRINT`;
- the Eddy-safe fixed-height napkin wipe still runs before accurate homing and
  bed leveling;
- `CX_PRINT_DRAW_ONE_LINE` is removed from `START_PRINT`;
- OrcaSlicer loads the selected CFS filament first;
- OrcaSlicer then returns the nozzle to first-layer temperature and draws the
  startup purge.

Do **not** add `CX_PRINT_DRAW_ONE_LINE` back to the slicer profile.

The legacy/stale `CFS_NOZZLE_CLEAR` and `CFS_NOZZLE_CLEAN` side-brush
commands are not used by this profile. On the validated Eddy Duo mount, that
old side-brush route is physically incompatible with the probe/mount geometry
and must stay out of sliced G-code. This is separate from Creality's normal
native CFS cutter and purge-chute path, which was physically validated during
the successful tool-change print.

## Machine Start G-code

In OrcaSlicer:

**Printer preset → Machine G-code → Machine start G-code**

Use:

```gcode
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
```

The required order is:

```text
START_PRINT
  → rough/accurate homing
  → Eddy-safe napkin wipe through CX_NOZZLE_CLEAR
  → Eddy bed leveling
  → return to slicer without a purge
T{current_extruder}
  → CFS loads the selected filament
M109 S[first-layer temperature]
  → restore/wait for print temperature
custom Orca purge
  → purge the filament that is actually loaded
print
```

## Change Filament G-code

In OrcaSlicer:

**Printer preset → Machine G-code → Change filament G-code**

Use:

```gcode
G2 Z{z_after_toolchange + 0.8} I0.86 J0.86 P1 F10000
G1 X0 Y245 F30000
{if z_after_toolchange > 0}
G1 Z{z_after_toolchange} F600
{endif}
```

The conditional Z restore is important. On the initial Orca-generated tool
selection, `z_after_toolchange` can evaluate to `0`. An unconditional:

```gcode
G1 Z{z_after_toolchange} F600
```

would therefore generate `G1 Z0 F600` before the redundant initial tool
selection. The conditional keeps the initial toolhead safely above the bed
while preserving the normal return-to-Z behavior for real mid-print tool
changes.

## Commands that should not appear in sliced startup G-code

The generated file should contain **no**:

```gcode
CFS_NOZZLE_CLEAR
CFS_NOZZLE_CLEAN
CX_PRINT_DRAW_ONE_LINE
```

The validated reference slice also emitted no standalone `BOX_NOZZLE_CLEAN`
command. A printer-side/manual helper with that name may still exist in
Creality's CFS configuration; do not confuse that helper with the obsolete
slicer-emitted `CFS_NOZZLE_*` side-brush path.

`CX_NOZZLE_CLEAR` still exists on the printer and is called internally by
`START_PRINT`; it should not appear as a separate slicer command.

## Expected sliced startup sequence

For a first tool such as T0 or T1, the generated G-code should look
approximately like:

```gcode
start_print EXTRUDER_TEMP=230 BED_TEMP=60 CHAMBER_TEMP=0
T0
RESPOND TYPE=command MSG="Loading Filament from CFS Slot "1
M109 S230

M204 S2000
G1 Z3 F600
M83
...
G1 X0 Y0 E15 F6000
G1 X150 Y0 E15 F6000
G92 E0
G1 Z1 F600
```

OrcaSlicer may emit another identical `T0`/`T1` after its initial
tool-change positioning. On the validated Creality CFS wrapper an immediate
same-tool command is a no-op; the physical regression confirmed that behavior.

## Final validated reference slice

The final audited reference G-code on the printer was:

```text
Mini Halloween Pumpkin - Single 3 color_PLA_11m42s.gcode
SHA256 9bfd7adc514f2df839489425f1d09347c87a75d0fa2e26b027808ce1481b02bb
```

Despite the filename, the executable tool sequence in that file was only:

```text
T0
T0
T1
```

The first-tool path was:

```text
start_print EXTRUDER_TEMP=230 BED_TEMP=60 CHAMBER_TEMP=0
T0
M109 S230
...
T0
SET_ACTIVE_SPOOL ID=33
```

and the real color change was:

```text
M104 S230
...
T1
SET_ACTIVE_SPOOL ID=3
...
prime tower / wipe continuation
```

The `SET_ACTIVE_SPOOL` IDs above belong to the reference printer's filament
profiles and are **not portable defaults**. Keep your own spool IDs in Orca's
filament start G-code.

## Physical validation completed

The final physical/regression validation confirmed:

- the napkin-strip wipe occurs during `START_PRINT`;
- no Creality purge line occurs before the CFS load;
- the selected first tool loads successfully;
- `M109` restores the requested first-layer nozzle temperature;
- the custom Orca purge runs after the CFS load;
- the first layer starts at the correct Z;
- the normal CFS cutter path clears the Eddy Duo mount;
- the normal CFS purge-chute/flush path clears the Eddy Duo mount;
- a real T0 -> T1 mid-print CFS tool change completes;
- prime-tower/wipe continuation resumes normally after the tool change;
- the obsolete `CFS_NOZZLE_CLEAR` / `CFS_NOZZLE_CLEAN` side-brush path is
  absent from the generated G-code.


Always reslice after changing printer Machine G-code; previously generated
G-code files retain the old startup sequence.
