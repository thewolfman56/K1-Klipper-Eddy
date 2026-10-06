# v1.0.1 release notes — documentation and installation-safety update

## Scope

v1.0.1 is a **documentation/safety release** for the same validated hardware and firmware profile as v1.0.0:

- Creality K1 Max
- official Creality CFS upgrade
- CrealityOS 2.3.5.33
- BTT Eddy Duo over USB
- fixed CFS napkin-strip wipe
- Fluidd + Moonraker/Nginx

There are **no installer, Klipper, config-template, homing, probing, CFS, or printer-behavior code changes** between v1.0.0 and v1.0.1.

## What changed

### One complete installation guide

Added:

```text
docs/START-HERE-COMPLETE-INSTALL.md
```

This is now the recommended entry point for a new install. It puts the normal procedure into one ordered document from a clean printer through final backups:

1. recommended factory-reset/fresh official 2.3.5.33 starting state;
2. official CFS installation and stock validation;
3. root/SSH;
4. Entware and Git;
5. required Creality Helper Script components;
6. BTT Eddy Duo mounting and USB setup;
7. repository install and preflight;
8. Eddy staging;
9. drive-current and height-map calibration;
10. native Eddy Z activation;
11. progressive Y/X/Z/full homing validation;
12. measured fixed napkin wipe;
13. production/readiness verification;
14. exact OrcaSlicer Machine Start and Change Filament G-code;
15. fresh-slice command checks;
16. controlled CFS print/tool-change validation;
17. final backup and firmware-update snapshot;
18. future update-audit and rollback workflow.

The focused documents remain available as deeper technical references.

### Recommended clean firmware starting point

The README and complete install guide now recommend beginning with a **factory-reset or freshly reflashed official CrealityOS 2.3.5.33 installation** before rooting or applying Helper Script/Klipper changes.

This is a recommendation rather than a claim that every already-configured printer must be reset. Its purpose is to reduce unknown leftovers from earlier macros, probe integrations, Helper Script changes, or firmware/config experiments.

A reset/reflash may erase configuration and user data; users should preserve anything they need first.

### Safety, warranty, and liability language

The README now states prominently that:

- the project is used at the user's own risk;
- it is an unofficial community project;
- incorrect hardware, calibration, configuration, or slicer settings can damage the printer or other property;
- users are responsible for backups, machine-specific measurements, validation, and safe first-motion testing;
- rooting/modifying the printer or adding third-party hardware may affect manufacturer warranty or service eligibility;
- GPLv3 NO WARRANTY provisions apply.

The wording intentionally says modifications **may affect or void** warranty/service eligibility rather than claiming that every modification automatically voids every warranty in every jurisdiction.

### CI coverage on main

Installer/package tests now run automatically on pushes to `main` in addition to the original release branch.

## Compatibility

v1.0.1 does not expand firmware support.

**Validated target remains CrealityOS 2.3.5.33 only.**

Do not treat v1.0.1 as validation for 2.3.5.34, 2.3.5.35, the newer 1.1.x K1 Max firmware line, a different mainboard, or a CFS-C conversion.

## Existing v1.0.0 validation remains applicable

Because runtime/printer code is unchanged, the completed v1.0.0 physical regression remains the production behavior reference, including:

- sensorless X/Y homing;
- native Eddy Z homing;
- corrected cold-start safety routing;
- fixed napkin wipe;
- 20×20 / 400-point rapid scan;
- complete START_PRINT path;
- initial CFS tool load;
- real T0 -> T1 tool change;
- normal CFS cutter/purge/flush path;
- prime-tower continuation;
- final recovery/health validation.

## Recommended starting document

For a new installation, start with:

```text
docs/START-HERE-COMPLETE-INSTALL.md
```

The README links to it prominently.
