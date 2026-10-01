# Creality Helper Script, Entware and Git — supported profile

This page documents the **supported Creality Helper Script profile** for the K1 Max + official CFS + BTT Eddy Duo installation on **CrealityOS 2.3.5.33**.

The goal is to keep the Creality CFS startup stack intact and let this repository own the Eddy-specific Z homing, mesh routing, and fixed napkin wipe. Only **Moonraker/Nginx** and **Fluidd** are required from the Creality Helper Script. Everything else is optional unless a dependency is stated below.

> This compatibility table is intentionally conservative. An item marked **Do not install** is either known to overlap this project's motion/probe/CFS path or replaces Klipper/config components that were not part of the validated production state.

Current upstream references:

- Guilouz Creality Helper Script: https://github.com/Guilouz/Creality-Helper-Script
- Current K1 Install Menu: https://github.com/Guilouz/Creality-Helper-Script/blob/main/scripts/menu/K1/install_menu_K1.sh
- Helper Script Wiki: https://guilouz.github.io/Creality-Helper-Script-Wiki/
- CFS / firmware 2.3.5.33 Git workaround discussion: https://github.com/Guilouz/Creality-Helper-Script-Wiki/discussions/787
- Firmware 2.3.5.33 CFS Helper Script discussion: https://github.com/Guilouz/Creality-Helper-Script-Wiki/discussions/797

## Why Git needs special handling on 2.3.5.33 CFS firmware

The CFS firmware line has shipped with a Git installation that may be missing or unusable. Because the normal Helper Script installation itself is cloned with Git, the cleanest path on this firmware is:

1. install Entware manually;
2. install Entware's Git packages;
3. point `/usr/bin/git` at the Entware Git binary;
4. clone the **original Guilouz Helper Script**;
5. install only the supported Helper Script items.

This project does **not** require the CFS-modified Helper Script fork. We deliberately preserve the original Creality CFS stack and apply our Eddy/CFS changes separately.

---

## A. Install Entware manually

SSH to the rooted printer as `root`.

Install Entware using the MIPS little-endian soft-float package feed used by the K1 CFS workaround:

```sh
wget http://bin.entware.net/mipselsf-k3.4/installer/generic.sh -O - | sh
```

Make the Entware commands available in the current SSH session:

```sh
export PATH=/opt/bin:/opt/sbin:$PATH
```

Verify Entware:

```sh
/opt/bin/opkg --version
```

Update the package lists:

```sh
/opt/bin/opkg update
```

### Optional Entware service startup

Git itself does not require Entware daemons, but optional Entware-based services may. If `/opt/etc/init.d/rc.unslung` exists and your `/etc/rc.local` does not already start it, add it **before the final `exit 0`**.

First inspect the file:

```sh
cat /etc/rc.local
```

If needed, edit it so the end contains:

```sh
/opt/etc/init.d/rc.unslung start
exit 0
```

Do not append a second `exit 0` above the Entware startup command.

---

## B. Install Git from Entware

Install Git and HTTP transport support:

```sh
/opt/bin/opkg install git
/opt/bin/opkg install git-http
```

Verify the Entware binary directly:

```sh
/opt/bin/git --version
```

### Replace the broken stock Git path safely

Preserve the original Creality Git binary once, if it exists and is not already a symbolic link:

```sh
if [ -e /usr/bin/git ] && [ ! -L /usr/bin/git ] && [ ! -e /usr/bin/git.creality.bak ]; then
    cp -a /usr/bin/git /usr/bin/git.creality.bak
fi
```

Replace `/usr/bin/git` with a link to Entware Git:

```sh
rm -f /usr/bin/git
ln -s /opt/bin/git /usr/bin/git
hash -r
```

Verify both the path and version:

```sh
ls -l /usr/bin/git
git --version
```

Expected path:

```text
/usr/bin/git -> /opt/bin/git
```

---

## C. Clone and run the original Creality Helper Script

Clone Guilouz's current Helper Script:

```sh
git clone --depth 1 \
  https://github.com/Guilouz/Creality-Helper-Script.git \
  /usr/data/helper-script
```

Run it:

```sh
sh /usr/data/helper-script/helper.sh
```

If the clone reports a TLS/certificate problem, first verify the printer's date/time. As a last-resort one-command workaround for the initial clone, use:

```sh
git -c http.sslVerify=false clone --depth 1 \
  https://github.com/Guilouz/Creality-Helper-Script.git \
  /usr/data/helper-script
```

Avoid permanently disabling Git certificate verification unless you understand the security tradeoff.

---

## D. Required Helper Script installs

Open:

```text
[Install] Menu
```

Install **only these two required items** first:

### 1 — Moonraker and Nginx — REQUIRED

Install menu option:

```text
1) Moonraker and Nginx
```

Moonraker is required by this project's installer for printer-state checks and for safely reading pending Eddy calibration values. Nginx is installed as part of the Helper Script's Moonraker package.

If the Moonraker install reports that its Git repository is unsafe or invalid, add the actual nested Moonraker Git checkout as a safe directory:

```sh
git config --global --add safe.directory /usr/data/moonraker/moonraker
```

Then rerun the Moonraker install/update operation.

### 2 — Fluidd — REQUIRED

Install menu option:

```text
2) Fluidd (port 4408)
```

Fluidd is the supported web UI for this guide. After installation it is normally available at:

```text
http://PRINTER_IP:4408/
```

Mainsail is not required.

---

## E. Required protection setting

After Moonraker/Fluidd are working, return to the Helper Script main menu and open:

```text
[Tools] Menu
```

Select:

```text
1) Prevent updating Klipper configuration files
```

This is important for the Eddy conversion. Creality's normal Klipper startup service can refresh configuration files during restart; the Helper Script's **Prevent updating Klipper configuration files** tool replaces that service behavior so the custom Eddy/CFS configuration is not silently overwritten.

Do **not** later select:

```text
2) Allow updating Klipper configuration files
```

unless you intentionally want to return to Creality-managed configuration behavior.

---

## F. Optional add-ons used on the validated reference machine

None of these are required for BTT Eddy or CFS operation. Skip all of them if you want the smallest possible installation.

### Entware — OPTIONAL infrastructure

The Helper Script lists Entware as Install Menu option 4, but on this firmware it has already been installed manually in order to fix Git. Do **not** reinstall it from the Helper Script if it is already present.

Verify:

```sh
/opt/bin/opkg --version
```

### 5 — Klipper Gcode Shell Command — OPTIONAL

Install this only when an optional feature needs it.

The current Helper Script requires it for items such as **Improved Shapers Calibrations**, Buzzer Support, Useful Macros, Camera Settings Control, and Git Backup.

It does not change Eddy homing by itself, but it allows Klipper macros to execute host shell commands, so install it only when needed.

### 10 — Improved Shapers Calibrations — OPTIONAL / VALIDATED

This was present on the validated reference installation and can be used with this Eddy/CFS configuration.

Dependency:

```text
5) Klipper Gcode Shell Command
```

Then install:

```text
10) Improved Shapers Calibrations
```

This feature is unrelated to Z probing, CFS nozzle wiping, or the Eddy mesh router.

### 16 — Moonraker Timelapse — OPTIONAL / VALIDATED

This was also present on the validated reference installation.

Dependency:

- Entware

Install:

```text
16) Moonraker Timelapse
```

It is not required for printing, CFS, or Eddy.

### 17 — Camera Settings Control — OPTIONAL / VALIDATED

Camera Settings Control was installed and active on the validated reference machine. The final configuration contained:

```text
[include Helper-Script/camera-settings.cfg]
```

and Klipper registered the expected camera commands, including `CAM_SETTINGS`, `CAM_BRIGHTNESS`, `CAM_CONTRAST`, `CAM_SATURATION`, `CAM_EXPOSURE_AUTO`, and the other `CAM_*` controls.

Dependency:

```text
5) Klipper Gcode Shell Command
```

Then install:

```text
17) Camera Settings Control
```

**Historical result:** the Helper Script installation itself worked on the validated camera. No separate corrective command was found in the saved installation history.

The current Helper Script also refuses this feature on the newer `CCX2F3299` camera hardware unless the compatible USB-camera service is present. Treat that Helper Script hardware check as authoritative for a different camera revision.

### 19 — OctoEverywhere — OPTIONAL / VALIDATED WITH K1-SPECIFIC FIXES

OctoEverywhere was validated on the reference machine, but the CFS/Entware environment exposed two K1-specific problems:

1. the upstream K1 bootstrap preferred Entware Python when `/opt/bin/opkg` existed;
2. the K1 `start-stop-daemon` wrapper could leave an orphan process and start a second `moonraker_octoeverywhere` instance.

The validated installation used **stock Creality Python 3.8** and deliberately kept `/opt/bin/python3` absent.

Dependencies from the Helper Script: Moonraker + Nginx, Fluidd or Mainsail, and Entware.

Install menu option:

```text
19) OctoEverywhere
```

The validated OctoEverywhere repository was `/usr/data/octoeverywhere` at commit `1fbc632e3a5e441c613feabc9d7ed48a67ae082a`.

First verify the intended Python runtime:

```sh
which python3
python3 --version
[ -e /opt/bin/python3 ] && echo "WARNING: /opt/bin/python3 EXISTS" || echo "GOOD: /opt/bin/python3 is absent"
python3 -c "import virtualenv, PIL; print('stock Python dependencies OK')"
```

On the validated source revision, the K1 dependency block in `install.sh` was changed so it did not install Entware Python/PIP/Pillow:

```sh
cd /usr/data/octoeverywhere
cp -p install.sh install.sh.pre-k1-cfs-eddy

python3 - <<'PY'
from pathlib import Path

p = Path("install.sh")
s = p.read_text()

start = s.index('    if [[ $IS_K1_OS -eq 1 ]]\n    then', s.index("install_or_update_system_dependencies()"))
end = s.index('    elif [[ $IS_K2_OS -eq 1 ]]', start)

replacement = '''    if [[ $IS_K1_OS -eq 1 ]]
    then
        log_info "K1: using stock Creality Python 3.8; skipping Entware Python/PIP/Pillow install."

        if ! python3 -c "import virtualenv, PIL" >/dev/null 2>&1; then
            log_error "Stock K1 Python is missing virtualenv or Pillow."
            exit 1
        fi
'''

p.write_text(s[:start] + replacement + s[end:])
print("OctoEverywhere K1 dependency bootstrap patched.")
PY
```

The validated launch JSON also set `"DisableMoonrakerConfigFileWrites": true`. On that historical `install.sh`, this guarded edit adds the flag:

```sh
python3 - <<'PY'
from pathlib import Path

p = Path("install.sh")
s = p.read_text()

needle = '\\"CMD_LINE_ARGS\\":\\"${CMD_LINE_ARGS}\\"}'
replacement = '\\"CMD_LINE_ARGS\\":\\"${CMD_LINE_ARGS}\\",\\"DisableMoonrakerConfigFileWrites\\":true}'

if needle not in s:
    raise SystemExit("ERROR: OctoEverywhere launch JSON anchor not found")

p.write_text(s.replace(needle, replacement, 1))
print("DisableMoonrakerConfigFileWrites enabled.")
PY
```

The K1 service template in `py_installer/Service.py` was changed to `exec` the Python module so the service PID tracks the actual process:

```sh
cp -p py_installer/Service.py py_installer/Service.py.pre-k1-cfs-eddy

python3 - <<'PY'
from pathlib import Path

p = Path("py_installer/Service.py")
s = p.read_text()

old = '''PYTHONPATH={context.RepoRootFolder} {context.VirtualEnvPath}/bin/python3 -m {moduleNameToRun} "{argsJsonBase64}"
exit $?
'''
new = '''export PYTHONPATH={context.RepoRootFolder}
exec {context.VirtualEnvPath}/bin/python3 -m {moduleNameToRun} "{argsJsonBase64}"
'''

if old not in s:
    raise SystemExit("ERROR: expected OctoEverywhere K1 service template not found")

p.write_text(s.replace(old, new, 1))
print("OctoEverywhere K1 service wrapper patched to exec Python.")
PY

python3 -m py_compile py_installer/Service.py
```

The generated validated paths were:

```text
/usr/data/printer_data/octoeverywhere-store/run-octoeverywhere-service.sh
/etc/init.d/S66octoeverywhere_service
/var/run/octoeverywhere.pid
/usr/data/printer_data/config/octoeverywhere-system.cfg
```

If a repeated/failed install leaves duplicate OctoEverywhere processes:

```sh
/etc/init.d/S66octoeverywhere_service stop || true
ps | grep '[m]oonraker_octoeverywhere'
ps | grep '[m]oonraker_octoeverywhere' | awk '{print $1}' | xargs -r kill -9
rm -f /var/run/octoeverywhere.pid
/etc/init.d/S66octoeverywhere_service start
sleep 3
```

Restart Moonraker after the OctoEverywhere Moonraker include changes:

```sh
/etc/init.d/S56moonraker_service stop
sleep 2
/etc/init.d/S56moonraker_service start
```

Require exactly one OctoEverywhere process:

```sh
OE_COUNT="$(ps | grep '[m]oonraker_octoeverywhere' | wc -l)"
echo "OctoEverywhere Python process count: $OE_COUNT"
if [ "$OE_COUNT" -ne 1 ]; then
    echo "STOP: Expected exactly one OctoEverywhere instance."
    exit 1
fi
wget -qO- http://127.0.0.1:7125/server/info
```

The saved reboot validation showed one OctoEverywhere process matching the PID file, Python 3.8.2, and no Entware Python.

> These edits document the **validated historical OctoEverywhere revision**. Inspect newer upstream K1 installers before applying the patch blindly; equivalent fixes may already be upstream.

### 22 — Mobileraker Companion — OPTIONAL / VALIDATED WITH K1-SPECIFIC FIXES

Mobileraker Companion was validated with the same core rule: **use stock Creality Python 3.8 and do not let the installer pull in Entware Python/PIP/Pillow**.

Dependencies from the Helper Script: Moonraker + Nginx, Fluidd or Mainsail, and Entware.

Install menu option:

```text
22) Mobileraker Companion
```

The validated repository lived at `/usr/data/mobileraker_companion`. Before installation, the saved history patched `scripts/install.sh`:

```sh
cd /usr/data/mobileraker_companion
mkdir -p /usr/data/pre-helper-components
cp -p scripts/install.sh /usr/data/pre-helper-components/mobileraker-install.sh.official
cp -p installer/Service.py /usr/data/pre-helper-components/mobileraker-Service.py.official

python3 - <<'PY'
from pathlib import Path

p = Path("scripts/install.sh")
s = p.read_text()

func = s.index("install_or_update_system_dependencies()")
start = s.index('    if [ "$IS_K1_OS" -eq 1 ]; then', func)
end = s.index('    elif [ "$IS_SONIC_PAD_OS" -eq 1 ]; then', start)

replacement = '''    if [ "$IS_K1_OS" -eq 1 ]; then
        log_info "K1: using stock Creality Python 3.8; skipping Entware Python/PIP/Pillow install."

        if ! python3 -c "import virtualenv, PIL" >/dev/null 2>&1; then
            log_error "Stock K1 Python is missing virtualenv or Pillow."
            exit 1
        fi

'''

p.write_text(s[:start] + replacement + s[end:])
print("K1 dependency bootstrap patched.")
PY
```

The K1 service wrapper in `installer/Service.py` was changed to `exec` Python:

```sh
python3 - <<'PY'
from pathlib import Path

p = Path("installer/Service.py")
s = p.read_text()

old = '''PYTHONPATH={context.repo_root} {context.virtual_env}/bin/python3 {context.repo_root}/mobileraker.py -l {context.printer_data_logs_folder} -c {context.mobileraker_conf_path}
exit $?
'''
new = '''export PYTHONPATH={context.repo_root}
exec {context.virtual_env}/bin/python3 {context.repo_root}/mobileraker.py -l {context.printer_data_logs_folder} -c {context.mobileraker_conf_path}
'''

if old not in s:
    raise SystemExit("ERROR: Expected K1 service launch template not found")

p.write_text(s.replace(old, new, 1))
print("K1 service wrapper patched to exec Python.")
PY
```

Validate the source edits before running/re-running the installer:

```sh
sh -n scripts/install.sh && echo "install.sh syntax OK"
python3 -m py_compile installer/Service.py && echo "Service.py syntax OK"
GIT_PAGER=cat git diff -- scripts/install.sh installer/Service.py
```

The generated validated wrapper ran:

```sh
export PYTHONPATH=/usr/data/mobileraker_companion
exec /usr/data/mobileraker-env/bin/python3 \
  /usr/data/mobileraker_companion/mobileraker.py \
  -l /usr/data/printer_data/logs \
  -c /usr/data/printer_data/config/mobileraker.conf
```

Validate after installation:

```sh
/usr/data/mobileraker-env/bin/python --version
ps | grep '[m]obileraker.py' || echo "Mobileraker process not found"
cat /var/run/mobileraker.pid 2>/dev/null || true
wget -qO- http://127.0.0.1:7125/server/info
```

The saved reference state had one Mobileraker process, a matching PID file, Python 3.8.2 in `/usr/data/mobileraker-env`, Moonraker ready with no failed components, and `/opt/bin/python3` absent.

> These commands document the **validated historical Mobileraker source state**. Check a newer upstream installer before applying them blindly.

---

## G. Full K1 Install Menu compatibility table

The table below follows the current 24-item K1 Install Menu from Guilouz's Helper Script.

| # | Helper Script item | Status for this project | Notes |
|---:|---|---|---|
| 1 | Moonraker and Nginx | **REQUIRED** | Required by this installer and Fluidd. |
| 2 | Fluidd | **REQUIRED** | Supported web UI for this guide. |
| 3 | Mainsail | Optional / unvalidated | Redundant when Fluidd is installed; no known Eddy conflict. |
| 4 | Entware | Optional infrastructure | Needed for Git on this firmware and several optional add-ons. Install it manually before cloning Helper Script; do not reinstall it from the menu. |
| 5 | Klipper Gcode Shell Command | Optional / validated dependency | Needed if you install Improved Shapers; otherwise skip it. |
| 6 | Klipper Adaptive Meshing & Purging | **DO NOT INSTALL** | Replaces/extends print-start, bed-mesh and purge behavior. This project already routes CFS leveling to the validated 20×20 Eddy `rapid_scan` and preserves Creality's CFS start sequence. |
| 7 | Buzzer Support | Optional / unvalidated | No known probe conflict; requires Gcode Shell Command. |
| 8 | Nozzle Cleaning Fan Control | **DO NOT INSTALL** | Hooks the Creality nozzle-cleaning/PRTouch path. This project supplies its own fixed-height CFS napkin wipe and explicitly manages the fans during `NOZZLE_CLEAR`. |
| 9 | Fans Control Macros | Optional / unvalidated | No known direct Eddy conflict, but not part of the validated reference state. |
| 10 | Improved Shapers Calibrations | **OPTIONAL / VALIDATED** | Present on the validated machine; requires Gcode Shell Command. |
| 11 | Useful Macros | **DO NOT INSTALL** | Adds bed-leveling, backup/restore and other macros that overlap configuration and calibration workflows this project deliberately controls. |
| 12 | Save Z-Offset Macros | **DO NOT INSTALL** | Persists a G-code Z offset independently of Eddy's calibrated probe/endstop relationship and can produce an unexpected/double Z correction. |
| 13 | Screws Tilt Adjust Support | **DO NOT INSTALL for v1.0** | Replaces Klipper's `screws_tilt_adjust.py` and invokes the active probe stack. It was not validated against this customized Eddy Klipper tree. |
| 14 | M600 Support | **DO NOT INSTALL for v1.0** | Implements its own unload/load/pause filament workflow and was not validated with Creality CFS material handling. |
| 15 | Git Backup | Optional / unvalidated | Does not own homing, but watches/pushes the config directory and requires Entware + Gcode Shell Command. This project's own rollback snapshots remain the authoritative recovery path. |
| 16 | Moonraker Timelapse | **OPTIONAL / VALIDATED** | Present on the validated reference machine; requires Entware. |
| 17 | Camera Settings Control | **OPTIONAL / VALIDATED** | Present and active on the reference machine; requires Gcode Shell Command. No corrective patch was needed on the validated camera revision. |
| 18 | USB Camera Support | Optional / unvalidated | No known Eddy conflict; requires Entware. |
| 19 | OctoEverywhere | **OPTIONAL / VALIDATED WITH K1 FIXES** | Validated with stock Creality Python 3.8, `DisableMoonrakerConfigFileWrites`, an `exec` K1 wrapper, and single-process/PID cleanup. |
| 20 | Moonraker Obico | Optional / unvalidated | Remote-access service only; requires Moonraker, a web UI and Entware. |
| 21 | GuppyFLO | Optional / unvalidated | Remote-access layer; not part of the reference validation. |
| 22 | Mobileraker Companion | **OPTIONAL / VALIDATED WITH K1 FIXES** | Validated with stock Python 3.8 dependency bootstrap and an `exec` service wrapper; requires Moonraker, web UI and Entware. |
| 23 | OctoApp Companion | Optional / unvalidated | Requires Moonraker, a web UI and Entware. |
| 24 | SimplyPrint | Optional / unvalidated | Moonraker integration; not part of the reference validation. |

### Meaning of the labels

- **REQUIRED** — install this for the supported procedure.
- **OPTIONAL / VALIDATED** — the feature was present on the known-good reference machine but is not needed for Eddy/CFS.
- **OPTIONAL / VALIDATED WITH K1 FIXES** — validated on the reference machine, but only after the documented K1-specific installation/service correction.
- **Optional / unvalidated** — no direct conflict is known, but it was not part of the final regression. Install only after the base Eddy/CFS system passes validation, and add one feature at a time.
- **DO NOT INSTALL** — conflicts with, overlaps, or replaces a part of the probe/CFS/motion/config stack that this project depends on.

---

## H. Customize Menu guidance

The Helper Script also offers customization features. For this project's supported profile:

| Customize item | Status | Reason |
|---|---|---|
| Custom Boot Display | Optional | Cosmetic only. |
| Remove Creality Web Interface | **DO NOT USE** | Preserve Creality's CFS management/interface path. Fluidd can remain on port 4408 without removing the Creality UI. |
| Guppy Screen | **DO NOT INSTALL for v1.0** | Replaces the touchscreen workflow and brings additional printer-control integrations; not part of the validated CFS/Eddy state. |
| Creality Dynamic Logos for Fluidd | Optional | Cosmetic Fluidd customization only. |

---

## I. Tools and Backup/Restore guidance

### Safe Helper Script tool actions

These are compatible with the supported profile:

- Restart Nginx
- Restart Moonraker
- Restart Klipper
- Update Entware packages
- Clear cache/logs
- Enable/disable Moonraker camera settings, if using a compatible camera

### Use with caution

**Fix printing Gcode files from folder** replaces Klipper's `gcode.py`. It was not part of the validated custom Klipper tree, so leave it disabled for the v1.0 supported profile.

### Do not use as routine maintenance

- **Allow updating Klipper configuration files** — can restore Creality-managed config behavior and overwrite Eddy/CFS changes.
- **Restore previous firmware** — changes the firmware baseline and invalidates this project's 2.3.5.33 compatibility guarantee.
- **Reset factory settings** — removes this installation and Helper Script features.

The Helper Script's configuration backup feature may be used to make an additional archive, but after Eddy installation the preferred recovery method is this repository's own:

```sh
sh install.sh backup
sh install.sh rollback <backup>
```

because those backups include both the printer configuration and every Klipper Python file this project replaces.

---

## J. Recommended install order

For a clean CrealityOS 2.3.5.33 + CFS machine:

```text
1. Root / enable SSH
2. Manually install Entware
3. Install Entware Git + git-http
4. Link /usr/bin/git -> /opt/bin/git
5. Clone Guilouz Creality Helper Script
6. Install Moonraker + Nginx
7. Add Moonraker Git safe.directory if needed
8. Install Fluidd
9. Tools -> Prevent updating Klipper configuration files
10. OPTIONAL: Gcode Shell Command
11. OPTIONAL: Improved Shapers
12. OPTIONAL: Moonraker Timelapse
13. OPTIONAL: Camera Settings Control
14. OPTIONAL: OctoEverywhere (check/apply documented K1 fixes)
15. OPTIONAL: Mobileraker Companion (check/apply documented K1 fixes)
16. Clone this K1-Klipper-Eddy fork
17. Run: sh install.sh doctor
18. Continue with the Eddy staging/calibration/activation guide
```

If you do not want Git or any optional Helper Script add-ons, a release ZIP/USB copy of this project can be used instead; **Moonraker/Nginx and Fluidd remain the only required Helper Script installs for the supported profile.**
