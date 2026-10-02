# v1.0.0 release checklist — K1 Max + CFS + BTT Eddy Duo

This checklist defines the release gate for the **CrealityOS 2.3.5.33** supported profile.

A green GitHub Actions run is necessary but not sufficient. The physical-printer checks below remain required because homing, Eddy clearance, CFS material handling, and the fixed napkin wipe involve real motion.

## 1. Repository / CI gate

- [ ] Draft PR contains only intended K1 Max + CFS + Eddy changes.
- [ ] GitHub Actions is green on the exact commit that will be tagged.
- [ ] Python compile checks pass for:
  - `scripts/k1max_cfs_eddy.py`
  - `klippy/extras/eddy_z_acquire.py`
- [ ] Exact deployed-source hash fixture passes.
- [ ] Synthetic stage → persist → activate → wipe → rollback test passes.
- [ ] Optional add-on good/risky-state tests pass.
- [ ] Production verifier accepted/drift tests pass.
- [ ] Firmware-update snapshot/audit tests pass.
- [ ] Release-readiness accepted/failure tests pass.
- [ ] No unexpected generated files, bytecode, or caches are committed.
- [ ] Release ZIP builder test passes.
- [ ] Two builds from the same source/version are byte-identical.
- [ ] Release ZIP excludes `.git`, `.github`, tests, `__pycache__`, and `.pyc` files.
- [ ] Release ZIP contains `RELEASE-MANIFEST.json`.

## 2. Live printer release-readiness gate

On the validated K1 Max, from the repository directory:

```sh
sh install.sh doctor
sh install.sh status
sh install.sh verify-production
sh install.sh release-readiness
```

Required core state:

- [ ] Firmware is exactly `2.3.5.33`.
- [ ] CFS `box.cfg` is present.
- [ ] One Eddy USB device is uniquely detected.
- [ ] Eddy drive-current calibration is persisted.
- [ ] Eddy height map is populated.
- [ ] `[stepper_z]` uses `probe:z_virtual_endstop`.
- [ ] Fixed CFS napkin wipe is configured for this printer.
- [ ] Production homing safety contract reports `PASS`.
- [ ] Superseded `MARGIN=1.000 MAX_TRAVEL=5.000` pre-XY Eddy-clearance block is absent.
- [ ] Exact production compatibility hashes pass for:
  - `extras/upgrade/ldc1612.py`
  - `extras/upgrade/probe_eddy_current.py`
  - `extras/upgrade/bulk_sensor.py`
- [ ] No `FAIL` appears in `release-readiness`.

A `WARN` for the public `eddy_z_acquire.py` is currently expected when its bounded/fail-stop safety contract passes but its bytes do not match the known, unrecovered production helper checksum. Do not convert this warning to `PASS` merely to make the report visually clean.

## 3. Optional validated add-ons

If installed, verify:

- [ ] Camera Settings Control loads its Helper Script config and `CAM_*` macros.
- [ ] Improved Shapers Calibrations remains available.
- [ ] Moonraker Timelapse remains available.
- [ ] OctoEverywhere:
  - [ ] uses stock Creality Python 3.8 profile;
  - [ ] does not depend on `/opt/bin/python3`;
  - [ ] K1 run wrapper uses `exec`;
  - [ ] exactly one `moonraker_octoeverywhere` process is running;
  - [ ] PID file matches the running process.
- [ ] Mobileraker Companion:
  - [ ] uses stock Creality Python 3.8 profile;
  - [ ] K1 wrapper uses `exec`;
  - [ ] exactly one `mobileraker.py` process is running;
  - [ ] PID file matches the running process.

`sh install.sh doctor` and `release-readiness` should surface risky optional states as warnings.

## 4. Physical cold-start homing validation

Keep immediate access to printer power.

From a full Klippy restart with XYZ unknown:

- [ ] Eddy connectivity check runs before XY:
  `EDDY_HOME_STATUS SAMPLES=50 TIMEOUT=2`.
- [ ] The connectivity result is **not** interpreted as physical clearance while XY is unknown.
- [ ] Creality's bounded unknown-Z-away move runs before lateral homing.
- [ ] Y homes twice intentionally.
- [ ] X homes twice intentionally.
- [ ] XY reaches the native-Z homing position.
- [ ] `M400`/settle occurs before Eddy clearance sampling.
- [ ] `EDDY_PREHOME_CLEAR MAX_TRAVEL=2.000` runs only after XY is over the bed.
- [ ] Native Eddy `G28 Z` completes normally.
- [ ] No blind Eddy-system `-8 mm` high-Z move toward the nozzle occurs.

## 5. Eddy fail-stop validation

- [ ] `EDDY_HOME_STATUS` reports plausible live data before intentional disconnect testing.
- [ ] Hot-unplugging Eddy causes Eddy operations to fail rather than return stale data.
- [ ] Main printer MCU/Klipper remains inspectable as expected.
- [ ] Reconnecting USB recreates the persistent by-id device.
- [ ] Eddy does not silently resume inside the old Klipper session.
- [ ] `FIRMWARE_RESTART` restores Eddy communication.

Do not repeat USB disconnect testing during an active print or motion.

## 6. Fixed napkin wipe validation

- [ ] Wipe coordinates are measurements from this printer, not copied from another machine.
- [ ] Wipe begins above the measured napkin surface.
- [ ] Wipe pressure/depth is physically acceptable.
- [ ] End-of-wipe clearance is safe.
- [ ] Fan/heater behavior is correct.
- [ ] `NOZZLE_CLEAR` completes without contacting the mount or bed.

## 7. Bed mesh / print-path validation

- [ ] `CHECK_BED_MESH AUTO_G29=1` routes to Eddy.
- [ ] A 20×20 / 400-point `rapid_scan` completes.
- [ ] Runtime mesh profile is active for the print session.
- [ ] Purge-line motion shows active mesh compensation.
- [ ] Complete CFS start path succeeds:

```text
BOX_START_PRINT
  → CX_ROUGH_G28
  → corrected protected G28
  → CX_NOZZLE_CLEAR
  → fixed-height napkin wipe
  → ACCURATE_G28
  → Eddy-aware redundant Z handling
  → CX_PRINT_LEVELING_CALIBRATION
  → CHECK_BED_MESH
  → 20×20 rapid_scan
  → CX_PRINT_DRAW_ONE_LINE
  → successful purge / print
```

## 8. Recovery / update safety

Before tagging:

```sh
sh install.sh backup
sh install.sh pre-update-snapshot
```

- [ ] A normal helper backup can be created.
- [ ] A firmware-update snapshot can be created.
- [ ] Snapshot manifest records firmware `2.3.5.33`.
- [ ] Snapshot contains the full printer config.
- [ ] Snapshot records the relevant Klipper/service paths.
- [ ] Rollback has already passed the synthetic CI test.
- [ ] Documentation clearly says **not** to restore old `.33` Klipper files blindly onto future firmware.

## 9. Documentation gate

- [ ] Root/SSH steps are documented.
- [ ] Entware → Git bootstrap is documented.
- [ ] Required Helper Script items are documented.
- [ ] Optional validated Helper Script items are documented.
- [ ] Unsupported/conflicting Helper Script items are documented.
- [ ] BTT Eddy mount/calibration steps are documented.
- [ ] CFS napkin-strip mount requirement is documented.
- [ ] Machine-specific values are clearly identified as non-portable.
- [ ] Off-bed Eddy safety limitation is prominent.
- [ ] Production verification commands are documented.
- [ ] Firmware-update audit-before-repair workflow is documented.

## 10. Merge / tag

Only after the checklist above is satisfied:

1. Convert PR #1 from draft to ready for review.
2. Merge to `main`.
3. Tag the exact validated merge commit:

```sh
git tag -a v1.0.0 -m "K1 Max + CFS + BTT Eddy Duo — CrealityOS 2.3.5.33"
git push origin v1.0.0
```

4. Build the deterministic printer-install ZIP:

```sh
python3 scripts/build_release.py \
  --version v1.0.0 \
  --output dist/K1-Klipper-Eddy-v1.0.0.zip
```

5. Create the GitHub release from `v1.0.0`.
6. Attach `dist/K1-Klipper-Eddy-v1.0.0.zip` for printers where Git is unavailable or intentionally not installed.
7. State prominently in the release notes that **v1.0.0 is validated only for CrealityOS 2.3.5.33**.
8. Keep the production snapshot/checksums and safety limitations in the release notes.

Do not mark a later Creality firmware as supported until its changed Klipper/CFS files have gone through the same audit and physical regression process.
