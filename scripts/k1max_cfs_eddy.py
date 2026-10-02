#!/usr/bin/env python3
"""Guarded installer for K1 Max + CFS + BTT Eddy Duo on CrealityOS 2.3.5.33.

The helper never sends motion, probing, heating, wiping, or print G-code.
"""

import argparse
import configparser
import datetime as dt
import glob
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import urllib.request

SUPPORTED_FW = "2.3.5.33"
MARKER = "# K1MAX_CFS_EDDY_HELPER"
WIPE_MARKER = "# K1MAX_CFS_EDDY_WIPE_CONFIGURED=1"
PRODUCTION_SENSORLESS_SHA256 = "548fdaa7d19a0eaf5a943febe416bde97dd736987ecf7e2991a5bd61b0caa12c"

PRODUCTION_SHA256 = {
    "config/printer.cfg":
        "bde6f5eba8049eb523555e8e95028d55c3fdb91979173acbc26f47dcd8da133a",
    "config/sensorless.cfg":
        PRODUCTION_SENSORLESS_SHA256,
    "config/gcode_macro.cfg":
        "dd8485b7ae2670f3fb28989263c29a2a176010cb3e05a7a4181c313fe03f4bc2",
    "config/printer_params.cfg":
        "f39ace4c7d667674542d2e73d81fa41253eb888a09c6c0f9eb375aea307c3381",
    "config/btteddy_mcu.cfg":
        "5fe4bbb17eb34181aa388619c6d22ff51a4c16698fc07a376317c558e4b9c2f4",
    "config/eddy_nozzle_clear.cfg":
        "5318022508d0a1a114e86ac8f4bfe7432ae3831ceb44d5be242dcf970a7661bf",
    "config/box.cfg":
        "fb380eab607710592defe9541ca26236004b81018e3eaeb0562ba79b9fbf774d",
    "klippy/extras/eddy_z_acquire.py":
        "3ec1f7a218bba1a2326164d6d7f528a7fda2529fd6a0598e58a120db7fe3b31d",
    "klippy/extras/upgrade/ldc1612.py":
        "4e62a646656707b65245b3c3af2a3b3388e78f0468e0891d560afe9153978645",
    "klippy/extras/upgrade/probe_eddy_current.py":
        "896c458cf9817fd7d1d507a50464b79df89dd8f937dadb5f124a53bf0f1c8a8a",
    "klippy/extras/upgrade/bulk_sensor.py":
        "e3c27157658ba28b209ea7702d10c2b431136f6c498a99675094b0e709ea0a23",
}

# Exact safety sections recovered from the corrected production validation.
# These intentionally preserve Creality comments/structure around the Eddy edits.
VALIDATED_IF_HOME_Z = """[gcode_macro _IF_HOME_Z]
gcode:
  {% if printer['gcode_macro xyz_ready'].z_ready|int == 1 %}
    {% if printer.toolhead.position.z|int < 5 %}
      {% set z_park = 5.0 - printer.toolhead.position.z|int %}
      G91
      G1 z{z_park} F600
      G90
    {% endif %}
  {% else %}
    {% if printer['gcode_macro xyz_ready'].z_moved|int == 0 %}
      # BTT Eddy / cold-start safety:
      # XY may be unknown here, so the Eddy probe may be hanging
      # outside the bed and cannot be trusted as a clearance sensor.
      # Use Creality's original bounded Z-away move before XY homing.
      {% if printer.print_stats.z_pos|float <= 20.0 or printer.print_stats.power_loss == 1 %}
        FORCE_MOVE STEPPER=stepper_z DISTANCE={printer["gcode_macro PRINTER_PARAM"].z_safe_g28} VELOCITY=10
      {% else %}
        FORCE_MOVE STEPPER=stepper_z DISTANCE=0.1 VELOCITY=10
      {% endif %}
      SET_GCODE_VARIABLE MACRO=xyz_ready VARIABLE=z_moved VALUE=1
    {% endif %}
  {% endif %}"""

VALIDATED_HOME_Z = """[gcode_macro _HOME_Z]
gcode:
  {% if printer['gcode_macro xyz_ready'].y_ready|int == 1 %}
    {% if printer['gcode_macro xyz_ready'].x_ready|int == 1 %}
      _IF_HOME_Z
    {% endif %}
  {% endif %}
  # Preserve Creality's high-Z recovery for non-Eddy probes.
  # With Eddy, do not blindly move the bed 8mm toward the nozzle
  # based on persisted z_pos.  Once XY is centered, live Eddy
  # feedback and native probe homing establish the real Z position.
  {% if 'probe_eddy_current btt_eddy' not in printer.configfile.settings
        and printer.print_stats.z_pos|float >= 260.0 %}
    FORCE_MOVE STEPPER=stepper_z DISTANCE=-8 VELOCITY=10
  {% endif %}

  {% set POSITION_X = printer.configfile.settings['stepper_x'].position_max/2 %}
  {% set POSITION_Y = printer.configfile.settings['stepper_y'].position_max/2 %}
  # BED_MESH_SET_DISABLE
  G91
  {% set x_park = POSITION_X - printer.toolhead.position.x|int %}
  {% set y_park = POSITION_Y - printer.toolhead.position.y|int %}
  {action_respond_info("x_park = %s \\n" % (x_park))}
  {action_respond_info("y_park = %s \\n" % (y_park))}
  G1 x{x_park} y{y_park} F3600
  G90

  # BTT Eddy:
  # G1 queues motion asynchronously.  Wait until the carriage has
  # actually reached the final Z-homing XY position before sampling
  # Eddy, otherwise bed-height variation during XY travel can look
  # like unexpected Z movement.
  M400
  G4 P500

  # BTT Eddy:
  # Ensure the probe begins native Z homing on the clear side
  # of its configured frequency threshold.
  {% if 'probe_eddy_current btt_eddy' in printer.configfile.settings %}
    EDDY_PREHOME_CLEAR MAX_TRAVEL=2.000
  {% endif %}

  G28 Z
  SET_GCODE_VARIABLE MACRO=xyz_ready VARIABLE=z_ready VALUE=1
  # BED_MESH_SET_ENABLE"""

VALIDATED_PRE_XY_BLOCK = """  {% if x_axes is not defined or x_axes[2] is not defined %}
    BED_MESH_CLEAR

    # BTT Eddy connectivity check ONLY.
    # XY is not yet known, so the probe may be off-bed.
    # Do not interpret CLEAR_SIDE here as physical nozzle clearance.
    # This command performs no intentional motion and prevents homing
    # from continuing if the Eddy MCU/sensor is unavailable.
    {% if 'probe_eddy_current btt_eddy' in printer.configfile.settings %}
      {action_respond_info("Checking BTT Eddy connectivity before homing; clearance is NOT evaluated until XY is known\\n")}
      EDDY_HOME_STATUS SAMPLES=50 TIMEOUT=2
    {% endif %}
  {% endif %}

"""


# The real .33 installation deliberately kept ordinary Creality Klipper
# modules in place and installed only isolated compatibility namespaces,
# thin loaders, the bed_mesh router, and the Eddy helper.
EDDY_KLIPPY_FILES = (
    Path("upgrade/__init__.py"),
    Path("upgrade/mcu.py"),
    Path("upgrade/msgproto.py"),
    Path("upgrade/serialhdl.py"),
    Path("extras/upgrade/__init__.py"),
    Path("extras/upgrade/bed_mesh.py"),
    Path("extras/upgrade/bulk_sensor.py"),
    Path("extras/upgrade/bus.py"),
    Path("extras/upgrade/ldc1612.py"),
    Path("extras/upgrade/manual_probe.py"),
    Path("extras/upgrade/probe.py"),
    Path("extras/upgrade/probe_eddy_current.py"),
    Path("extras/upgrade/temperature_probe.py"),
    Path("extras/probe_eddy_current.py"),
    Path("extras/temperature_probe.py"),
    Path("extras/bed_mesh.py"),
    Path("extras/eddy_z_acquire.py"),
)

EDDY_KLIPPY_TOUCHED = EDDY_KLIPPY_FILES + (
    Path("mcu.py"),
    Path("extras/bed_mesh_creality.py"),
)

# Stock CrealityOS 2.3.5.33 hashes recorded immediately before the manual
# isolated Eddy compatibility install.
CREALITY_23533_CORE_SHA256 = {
    "extras/probe.py":
        "432633cfd1168c1f4e5f8321a7bf03b95684f26e52a604df01f44e32aa559f5f",
    "extras/manual_probe.py":
        "7431f2629021f92c8ea84e8d078bb4c4cfa760e4b946d5abc519747d318e215e",
    "extras/bed_mesh.py":
        "6ba9f844b5d1a1a51c36a385e480775a3aafb50a5fe474908e7560259ab40957",
    "extras/bus.py":
        "9fd8580ce182b6fd878653f23f155d856f60994941dbef0f10dbc78f34fe62a9",
    "mcu.py":
        "4b5b902cd424e9dd4dacd376c3431dc9d84e02dd9a93ebb49b84ac3b548de3ec",
}


class Stop(RuntimeError):
    pass


def root_path(root, absolute):
    return Path(root) / absolute.lstrip("/")


def repo_root():
    return Path(__file__).resolve().parent.parent


def printer_paths(root):
    return {
        "config": root_path(root, "/usr/data/printer_data/config"),
        "printer": root_path(root, "/usr/data/printer_data/config/printer.cfg"),
        "sensorless": root_path(root, "/usr/data/printer_data/config/sensorless.cfg"),
        "gcode_macro": root_path(root, "/usr/data/printer_data/config/gcode_macro.cfg"),
        "box": root_path(root, "/usr/data/printer_data/config/box.cfg"),
        "eddy_cfg": root_path(root, "/usr/data/printer_data/config/btteddy_mcu.cfg"),
        "eddy_macros": root_path(root, "/usr/data/printer_data/config/eddy_nozzle_clear.cfg"),
        "klippy": root_path(root, "/usr/share/klipper/klippy"),
        "extras": root_path(root, "/usr/share/klipper/klippy/extras"),
        "backups": root_path(root, "/usr/data/k1max-cfs-eddy-backups"),
    }


def read_text(path):
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return ""


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-k1max-cfs-eddy")
    tmp.write_text(data)
    os.replace(str(tmp), str(path))


def detect_firmware(root):
    candidates = [
        "/etc/ota_info",
        "/etc/os-release",
        "/usr/data/creality/userdata/config/system_version.json",
        "/usr/data/creality/userdata/config/system_config.json",
    ]
    seen = []
    for name in candidates:
        p = root_path(root, name)
        if p.exists():
            text = read_text(p)
            seen.append((str(p), text))
            m = re.search(r"\b(?:V)?(\d+\.\d+\.\d+\.\d+)\b", text)
            if m:
                return m.group(1), str(p)
    for base in [root_path(root, "/usr/data/creality"), root_path(root, "/usr/data")]:
        if not base.exists():
            continue
        for p in list(base.glob("**/system_version.json"))[:10]:
            text = read_text(p)
            m = re.search(r"\b(?:V)?(\d+\.\d+\.\d+\.\d+)\b", text)
            if m:
                return m.group(1), str(p)
    return None, None


def detect_eddy_serial(root):
    serial_dir = root_path(root, "/dev/serial/by-id")
    if not serial_dir.exists():
        return None
    found = []
    for p in serial_dir.iterdir():
        name = p.name.lower()
        if "klipper" in name and ("rp2040" in name or "eddy" in name):
            found.append("/dev/serial/by-id/" + p.name)
    return found[0] if len(found) == 1 else None


def moonraker_json(path):
    with urllib.request.urlopen("http://127.0.0.1:7125" + path, timeout=3) as r:
        return json.loads(r.read().decode("utf-8"))


def process_ids(root, needle):
    """Return PIDs whose /proc/<pid>/cmdline contains needle."""
    proc = root_path(root, "/proc")
    if not proc.exists():
        return []
    found = []
    try:
        entries = proc.iterdir()
    except OSError:
        return []
    for entry in entries:
        if not entry.name.isdigit():
            continue
        cmdline = entry / "cmdline"
        try:
            data = cmdline.read_bytes().replace(b"\x00", b" ").decode(
                "utf-8", errors="replace"
            )
        except OSError:
            continue
        if needle in data:
            found.append(int(entry.name))
    return sorted(found)


def read_pid(path):
    try:
        return int(Path(path).read_text().strip())
    except (OSError, ValueError):
        return None


def addon_audit(root):
    """Read-only audit of optional add-ons validated on the reference K1 Max."""
    cfg = root_path(root, "/usr/data/printer_data/config")
    printer = read_text(cfg / "printer.cfg")
    entware_python = root_path(root, "/opt/bin/python3").exists()
    findings = []

    def add(level, name, message):
        findings.append((level, name, message))

    # Camera Settings Control
    camera_cfg = cfg / "Helper-Script/camera-settings.cfg"
    camera_installed = (
        "Helper-Script/camera-settings.cfg" in printer
        or camera_cfg.exists()
    )
    if camera_installed:
        if "Helper-Script/camera-settings.cfg" in printer:
            add("PASS", "Camera Settings Control",
                "validated config include is present")
        else:
            add("WARN", "Camera Settings Control",
                "camera-settings.cfg exists but printer.cfg does not include it")
    else:
        add("INFO", "Camera Settings Control", "not installed")

    # OctoEverywhere
    oe_repo = root_path(root, "/usr/data/octoeverywhere")
    oe_service = root_path(root, "/etc/init.d/S66octoeverywhere_service")
    oe_cfg = cfg / "octoeverywhere-system.cfg"
    oe_installed = oe_repo.exists() or oe_service.exists() or oe_cfg.exists()
    if oe_installed:
        oe_install = read_text(oe_repo / "install.sh")
        oe_run_candidates = [
            root_path(
                root,
                "/usr/data/printer_data/octoeverywhere-store/"
                "run-octoeverywhere-service.sh",
            ),
            root_path(
                root,
                "/usr/data/octoeverywhere-store/run-octoeverywhere-service.sh",
            ),
        ]
        oe_run = next((x for x in oe_run_candidates if x.exists()), None)
        oe_run_text = read_text(oe_run) if oe_run else ""

        if entware_python:
            add("WARN", "OctoEverywhere",
                "/opt/bin/python3 exists; validated profile used stock "
                "Creality Python 3.8")
        else:
            add("PASS", "OctoEverywhere",
                "Entware Python is absent (validated runtime profile)")

        if "DisableMoonrakerConfigFileWrites" in oe_install:
            add("PASS", "OctoEverywhere",
                "DisableMoonrakerConfigFileWrites patch/behavior marker found")
        else:
            add("INFO", "OctoEverywhere",
                "historical DisableMoonrakerConfigFileWrites marker not "
                "visible; inspect newer upstream behavior before patching")

        if oe_run is None:
            add("WARN", "OctoEverywhere",
                "K1 run-octoeverywhere-service.sh was not found")
        elif re.search(r"(?m)^\s*exec\s+", oe_run_text):
            add("PASS", "OctoEverywhere",
                "K1 service wrapper uses exec")
        else:
            add("WARN", "OctoEverywhere",
                "K1 service wrapper does not use exec; PID duplication is "
                "possible")

        oe_pids = process_ids(root, "moonraker_octoeverywhere")
        oe_pidfile = read_pid(root_path(root, "/var/run/octoeverywhere.pid"))
        if len(oe_pids) == 1:
            add("PASS", "OctoEverywhere",
                "exactly one runtime process found (PID %d)" % oe_pids[0])
        elif len(oe_pids) > 1:
            add("WARN", "OctoEverywhere",
                "multiple runtime processes found: %s" %
                ", ".join(str(x) for x in oe_pids))
        else:
            add("INFO", "OctoEverywhere",
                "no runtime process found (service may be stopped)")

        if oe_pidfile is not None and oe_pids:
            if oe_pidfile in oe_pids:
                add("PASS", "OctoEverywhere",
                    "PID file matches a running OctoEverywhere process")
            else:
                add("WARN", "OctoEverywhere",
                    "PID file %d does not match running process(es) %s" %
                    (oe_pidfile, ", ".join(str(x) for x in oe_pids)))
    else:
        add("INFO", "OctoEverywhere", "not installed")

    # Mobileraker Companion
    mr_repo = root_path(root, "/usr/data/mobileraker_companion")
    mr_service_candidates = [
        root_path(root, "/etc/init.d/S80mobileraker_service"),
        root_path(root, "/etc/init.d/S80mobileraker"),
    ]
    mr_installed = mr_repo.exists() or any(x.exists() for x in mr_service_candidates)
    if mr_installed:
        mr_install = read_text(mr_repo / "scripts/install.sh")
        mr_run = mr_repo / ".k1/run-companion-service.sh"
        mr_run_text = read_text(mr_run)

        if entware_python:
            add("WARN", "Mobileraker Companion",
                "/opt/bin/python3 exists; validated profile kept Entware "
                "Python absent")
        else:
            add("PASS", "Mobileraker Companion",
                "Entware Python is absent (validated runtime profile)")

        if (
            "using stock Creality Python 3.8" in mr_install
            or "skipping Entware Python/PIP/Pillow" in mr_install
        ):
            add("PASS", "Mobileraker Companion",
                "stock-Python K1 bootstrap marker found")
        else:
            add("INFO", "Mobileraker Companion",
                "historical stock-Python bootstrap marker not visible; "
                "inspect newer upstream installer before patching")

        if not mr_run.exists():
            add("WARN", "Mobileraker Companion",
                ".k1/run-companion-service.sh was not found")
        elif re.search(r"(?m)^\s*exec\s+", mr_run_text):
            add("PASS", "Mobileraker Companion",
                "K1 service wrapper uses exec")
        else:
            add("WARN", "Mobileraker Companion",
                "K1 service wrapper does not use exec")

        mr_pids = process_ids(root, "mobileraker.py")
        mr_pidfile = read_pid(root_path(root, "/var/run/mobileraker.pid"))
        if len(mr_pids) == 1:
            add("PASS", "Mobileraker Companion",
                "exactly one runtime process found (PID %d)" % mr_pids[0])
        elif len(mr_pids) > 1:
            add("WARN", "Mobileraker Companion",
                "multiple runtime processes found: %s" %
                ", ".join(str(x) for x in mr_pids))
        else:
            add("INFO", "Mobileraker Companion",
                "no runtime process found (service may be stopped)")

        if mr_pidfile is not None and mr_pids:
            if mr_pidfile in mr_pids:
                add("PASS", "Mobileraker Companion",
                    "PID file matches the running Mobileraker process")
            else:
                add("WARN", "Mobileraker Companion",
                    "PID file %d does not match running process(es) %s" %
                    (mr_pidfile, ", ".join(str(x) for x in mr_pids)))
    else:
        add("INFO", "Mobileraker Companion", "not installed")

    print("\nOptional add-on audit (read-only)")
    for level, name, message in findings:
        print("  %-4s %-26s %s" % (level, name + ":", message))
    warnings = sum(1 for level, _, _ in findings if level == "WARN")
    print("  Summary: %d warning(s); no files were changed." % warnings)
    return findings


def assert_idle(root):
    if str(root) != "/":
        return
    try:
        data = moonraker_json("/printer/objects/query?print_stats")
        state = data["result"]["status"]["print_stats"]["state"]
    except Exception as exc:
        raise Stop("Cannot confirm printer idle through Moonraker: %s" % exc)
    if state in ("printing", "paused"):
        raise Stop("Printer state is %s; refusing to modify files." % state)


def doctor(args, write=False):
    p = printer_paths(args.root)
    fw, source = detect_firmware(args.root)
    print("K1 Max + CFS + BTT Eddy Duo preflight")
    print("  root:      %s" % args.root)
    print("  firmware:  %s%s" % (fw or "NOT DETECTED", (" (" + source + ")") if source else ""))
    print("  printer:   %s" % ("found" if p["printer"].exists() else "MISSING"))
    print("  sensorless:%s" % (" found" if p["sensorless"].exists() else " MISSING"))
    print("  CFS box:   %s" % ("found" if p["box"].exists() else "MISSING"))
    serial = detect_eddy_serial(args.root)
    print("  Eddy USB:  %s" % (serial or "not uniquely detected"))

    addon_audit(args.root)

    if fw != SUPPORTED_FW and not args.force_unsupported:
        raise Stop("Expected firmware %s; detected %s. Use --force-unsupported only for development."
                   % (SUPPORTED_FW, fw or "unknown"))
    for key in ("printer", "sensorless", "gcode_macro", "box"):
        if not p[key].exists():
            raise Stop("Required file missing: %s" % p[key])
    if write:
        assert_idle(args.root)
    return serial


def timestamp():
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def backup(args, reason="manual"):
    p = printer_paths(args.root)
    p["backups"].mkdir(parents=True, exist_ok=True)
    dest = p["backups"] / ("%s-%s" % (timestamp(), reason))
    n = 1
    while dest.exists():
        dest = p["backups"] / ("%s-%s-%d" % (timestamp(), reason, n))
        n += 1
    dest.mkdir(parents=True)
    shutil.copytree(p["config"], dest / "config")

    touched = [str(rel) for rel in EDDY_KLIPPY_TOUCHED]
    for rel in EDDY_KLIPPY_TOUCHED:
        target = p["klippy"] / rel
        if target.exists():
            out = dest / "klippy-original" / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, out)

    (dest / "manifest.json").write_text(json.dumps({
        "reason": reason,
        "created": dt.datetime.now().isoformat(),
        "root": str(args.root),
        "touched_klippy": touched,
    }, indent=2))
    print("Backup: %s" % dest)
    return dest


def ensure_include(printer_cfg, include_name):
    text = read_text(printer_cfg)
    directive = "[include %s]" % include_name
    if directive in text:
        return
    atomic_write(printer_cfg, directive + "\n" + text)


def _mcu_router_state(text):
    has_import = "from upgrade import mcu as upgrade_mcu" in text
    has_selector = "def _obtain_MCU_class(config):" in text
    if has_import and has_selector:
        return "patched"
    if has_import or has_selector:
        return "partial"
    return "stock"


def patch_mcu_router(path):
    """Apply only the validated .33 MCU-class routing patch."""
    text = read_text(path)
    state = _mcu_router_state(text)
    if state == "patched":
        return
    if state == "partial":
        raise Stop(
            "mcu.py contains a partial Eddy router patch; refusing to guess."
        )

    import_anchor = "import serialhdl, msgproto, pins, chelper, clocksync\n"
    if import_anchor not in text:
        raise Stop(
            "Expected CrealityOS 2.3.5.33 mcu.py import anchor was not found."
        )

    old = """def add_printer_objects(config):
    printer = config.get_printer()
    reactor = printer.get_reactor()
    mainsync = clocksync.ClockSync(reactor)
    printer.add_object('mcu', MCU(config.getsection('mcu'), mainsync))
    for s in config.get_prefix_sections('mcu '):
        printer.add_object(s.section, MCU(
            s, clocksync.SecondarySync(reactor, mainsync)))
"""
    new = """def _obtain_MCU_class(config):
    if config.getboolean('stock_implementation', True):
        return MCU
    return upgrade_mcu.MCU

def add_printer_objects(config):
    printer = config.get_printer()
    reactor = printer.get_reactor()
    mainsync = clocksync.ClockSync(reactor)
    mcu = _obtain_MCU_class(config.getsection('mcu'))
    printer.add_object('mcu', mcu(config.getsection('mcu'), mainsync))
    for s in config.get_prefix_sections('mcu '):
        mcu = _obtain_MCU_class(s)
        printer.add_object(s.section, mcu(
            s, clocksync.SecondarySync(reactor, mainsync)))
"""
    if text.count(old) != 1:
        raise Stop(
            "Expected CrealityOS 2.3.5.33 add_printer_objects block "
            "was not found exactly once."
        )

    text = text.replace(
        import_anchor,
        import_anchor + "from upgrade import mcu as upgrade_mcu\n",
        1,
    )
    text = text.replace(old, new, 1)
    atomic_write(path, text)


def validate_creality_core(root, p):
    """Validate stock core files that the manual install intentionally kept."""
    # Synthetic test roots do not contain the full Creality source files.
    strict_hashes = str(root) == "/"
    results = {}
    for rel_s, expected in CREALITY_23533_CORE_SHA256.items():
        path = p["klippy"] / rel_s
        if not path.exists():
            if strict_hashes:
                raise Stop("Required Creality Klipper file missing: %s" % path)
            results[rel_s] = "missing-test-fixture"
            continue

        # mcu.py is expected to differ after the validated router patch.
        if rel_s == "mcu.py" and _mcu_router_state(read_text(path)) == "patched":
            results[rel_s] = "validated-router-present"
            continue

        # bed_mesh.py becomes the small conditional router after first install;
        # the original must then exist as bed_mesh_creality.py.
        if rel_s == "extras/bed_mesh.py" and "bed_mesh_creality" in read_text(path):
            preserved = p["extras"] / "bed_mesh_creality.py"
            if not preserved.exists():
                raise Stop(
                    "bed_mesh.py is routed but bed_mesh_creality.py is missing."
                )
            if strict_hashes and sha256_file(preserved) != expected:
                raise Stop(
                    "Preserved Creality bed_mesh.py hash does not match "
                    "the validated 2.3.5.33 baseline."
                )
            results[rel_s] = "router+preserved-stock"
            continue

        actual = sha256_file(path)
        if strict_hashes and actual != expected:
            raise Stop(
                "Creality core hash mismatch for %s: expected %s, got %s"
                % (rel_s, expected, actual)
            )
        results[rel_s] = actual
    return results


def copy_klippy_tree(root):
    """Install only the isolated compatibility files used on the real printer."""
    p = printer_paths(root)
    src_root = repo_root() / "klippy"
    p["klippy"].mkdir(parents=True, exist_ok=True)

    validate_creality_core(root, p)

    # Preserve the original Creality bed_mesh byte-for-byte before installing
    # the conditional router.  Never overwrite an existing preserved copy.
    stock_bed = p["extras"] / "bed_mesh.py"
    saved_bed = p["extras"] / "bed_mesh_creality.py"
    if not saved_bed.exists():
        if not stock_bed.exists():
            raise Stop("Creality bed_mesh.py is missing.")
        if "bed_mesh_creality" in read_text(stock_bed):
            raise Stop(
                "bed_mesh.py already looks routed but no preserved "
                "bed_mesh_creality.py exists."
            )
        if str(root) == "/":
            expected = CREALITY_23533_CORE_SHA256["extras/bed_mesh.py"]
            actual = sha256_file(stock_bed)
            if actual != expected:
                raise Stop(
                    "Refusing to preserve unknown bed_mesh.py; expected "
                    "CrealityOS 2.3.5.33 hash %s, got %s"
                    % (expected, actual)
                )
        shutil.copy2(stock_bed, saved_bed)

    for rel in EDDY_KLIPPY_FILES:
        src = src_root / rel
        if not src.exists():
            raise Stop("Repository compatibility file missing: %s" % rel)
        dst = p["klippy"] / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    # Keep Creality's mcu.py and apply only the validated routing delta.
    patch_mcu_router(p["klippy"] / "mcu.py")



def make_eddy_cfg(serial, x_offset, y_offset, z_offset):
    return f"""{MARKER}
# Generated for K1 Max + CFS + BTT Eddy Duo.
# USB serial and calibration are printer-specific.
[mcu eddy]
is_non_critical: true
stock_implementation: false
serial: {serial}
restart_method: command

[temperature_sensor btt_eddy_mcu]
sensor_type: temperature_mcu
sensor_mcu: eddy
min_temp: 0
max_temp: 105

[probe_eddy_current btt_eddy]
sensor_type: ldc1612
z_offset: {z_offset:.6f}
i2c_mcu: eddy
i2c_bus: i2c0f
x_offset: {x_offset:.6f}
y_offset: {y_offset:.6f}

[temperature_probe btt_eddy]
sensor_type: Generic 3950
sensor_pin: eddy:gpio26
horizontal_move_z: 2.0

[eddy_z_acquire]
probe: probe_eddy_current btt_eddy
"""


def placeholder_macros():
    return f"""{MARKER}
# The fixed napkin strip is non-conductive. Eddy cannot discover its Z height.
# configure-wipe must be run with measurements from this printer.

[gcode_macro NOZZLE_CLEAR]
description: K1 Max CFS Eddy wipe - NOT CONFIGURED
rename_existing: NOZZLE_CLEAR_PRTOUCH
gcode:
  {{action_raise_error("K1 Max CFS Eddy napkin wipe is not calibrated. Run install.sh configure-wipe after measuring this printer.")}}

[gcode_macro CHECK_BED_MESH]
description: Eddy-safe CFS bed mesh router
rename_existing: CHECK_BED_MESH_PRTOUCH
gcode:
  {{% set auto_g29 = params.AUTO_G29|default(0)|int %}}
  {{% if "probe_eddy_current btt_eddy" in printer.configfile.settings %}}
    {{% if printer.toolhead.homed_axes != "xyz" %}}
      {{action_raise_error("Eddy-safe CHECK_BED_MESH requires XYZ homed")}}
    {{% endif %}}
    {{% if auto_g29 == 1 %}}
      BED_MESH_CLEAR
      BED_MESH_CALIBRATE PROFILE=eddy_runtime METHOD=rapid_scan HORIZONTAL_MOVE_Z=2 MESH_MIN=15,15 MESH_MAX=280,285 PROBE_COUNT=20,20 ALGORITHM=bicubic
      BED_MESH_PROFILE REMOVE=eddy_runtime
    {{% else %}}
      {{action_raise_error("Eddy-safe CHECK_BED_MESH requires AUTO_G29=1")}}
    {{% endif %}}
  {{% else %}}
    CHECK_BED_MESH_PRTOUCH {{rawparams}}
  {{% endif %}}
"""


def replace_section(text, header, new_section):
    lines = text.splitlines(True)
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i
            break
    if start is None:
        raise Stop("Section not found: %s" % header)
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith("[") and s.endswith("]"):
            end = i
            break
    before = "".join(lines[:start])
    after = "".join(lines[end:])
    if before and not before.endswith("\n"):
        before += "\n"
    section = new_section.rstrip() + "\n\n"
    return before + section + after.lstrip("\n")


def section_core(text, header):
    """Return one config section with only separator newlines normalized."""
    lines = text.splitlines(True)
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i
            break
    if start is None:
        return None
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith("[") and s.endswith("]"):
            end = i
            break
    return "".join(lines[start:end]).rstrip("\n")


def pre_xy_block(text):
    block = section_core(text, "[homing_override]")
    if block is None:
        return None
    first = "  {% if x_axes is not defined or x_axes[2] is not defined %}"
    following = (
        "  {% if x_axes is defined and x_axes[0] is defined "
        "and x_axes[1] is defined %}"
    )
    a = block.find(first)
    b = block.find(following, a + len(first))
    if a < 0 or b < 0:
        return None
    return block[a:b]


def sensorless_contract(text):
    """Return exact recovered-production safety contract checks."""
    checks = {
        "_IF_HOME_Z": (
            section_core(text, "[gcode_macro _IF_HOME_Z]")
            == VALIDATED_IF_HOME_Z
        ),
        "_HOME_Z": (
            section_core(text, "[gcode_macro _HOME_Z]")
            == VALIDATED_HOME_Z
        ),
        "pre_xy": (
            pre_xy_block(text)
            == VALIDATED_PRE_XY_BLOCK
        ),
        "unsafe_off_bed_guard_absent": (
            "EDDY_PREHOME_CLEAR MARGIN=1.000 MAX_TRAVEL=5.000"
            not in text
        ),
    }
    return checks


def patch_stage_sensorless(path):
    """Validate the bounded unknown-Z path without rewriting sensorless.cfg.

    During calibration staging TMC/Creality still owns Z.  The stock .33
    bounded unknown-Z-away move is the desired behavior.  Rewriting the whole
    macro here would create unnecessary drift before native Eddy activation.
    """
    text = read_text(path)
    block = section_core(text, "[gcode_macro _IF_HOME_Z]")
    if block is None:
        raise Stop("Cannot find _IF_HOME_Z in sensorless.cfg")
    if "FORCE_MOVE STEPPER=stepper_z DISTANCE=" not in block:
        raise Stop(
            "_IF_HOME_Z does not contain the expected bounded Z-away move; "
            "refusing to stage Eddy on an unknown homing layout."
        )
    if "z_safe_g28} VELOCITY=10" not in block:
        raise Stop(
            "_IF_HOME_Z does not contain Creality's z_safe_g28 path; "
            "refusing to rewrite an unknown homing layout."
        )
    if "EDDY_PREHOME_CLEAR MARGIN=1.000 MAX_TRAVEL=5.000" in text:
        raise Stop(
            "Unsafe legacy off-bed Eddy clearance block detected. "
            "Remove/rollback it before staging."
        )


def stage(args):
    detected = doctor(args, write=True)
    serial = args.eddy_serial or detected
    if not serial:
        raise Stop("Eddy serial was not uniquely detected. Supply --eddy-serial /dev/serial/by-id/...")
    backup(args, "pre-stage")
    copy_klippy_tree(args.root)
    p = printer_paths(args.root)
    atomic_write(p["eddy_cfg"], make_eddy_cfg(serial, args.x_offset, args.y_offset, args.z_offset))
    atomic_write(p["eddy_macros"], placeholder_macros())
    ensure_include(p["printer"], "eddy_nozzle_clear.cfg")
    ensure_include(p["printer"], "btteddy_mcu.cfg")
    patch_stage_sensorless(p["sensorless"])
    print("\nSTAGED. No motion command was sent.")
    print("Review the diff, then issue FIRMWARE_RESTART in Fluidd.")
    print("Do not print or run native Eddy Z homing yet. Calibrate Eddy first.")


def section_block(text, header):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i
            break
    if start is None:
        return []
    out = []
    for line in lines[start + 1:]:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            break
        out.append(line)
    return out


def calibration_state(path):
    text = read_text(path)
    block = section_block(text, "[probe_eddy_current btt_eddy]")
    reg = None
    collecting = False
    cal_parts = []
    for line in block:
        s = line.strip()
        if s.startswith("reg_drive_current:"):
            reg = s.split(":", 1)[1].strip()
        if s.startswith("calibrate:"):
            collecting = True
            rest = s.split(":", 1)[1].strip()
            if rest:
                cal_parts.append(rest)
            continue
        if collecting:
            if line[:1].isspace():
                cal_parts.append(s)
            elif s:
                collecting = False
    joined = "".join(cal_parts)
    points = len([x for x in joined.split(",") if ":" in x])
    return reg, points


def set_section_values(path, header, values):
    text = read_text(path)
    lines = text.splitlines()
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i
            break
    if start is None:
        raise Stop("Missing section %s in %s" % (header, path))
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith("[") and s.endswith("]"):
            end = i
            break

    old = lines[start + 1:end]
    keys = set(values)
    cleaned = []
    i = 0
    while i < len(old):
        s = old[i].strip()
        key = s.split(":", 1)[0].strip() if ":" in s else None
        if key in keys:
            i += 1
            while i < len(old) and old[i][:1].isspace():
                i += 1
            continue
        cleaned.append(old[i])
        i += 1

    additions = []
    for key, value in values.items():
        if "\n" in str(value):
            additions.append(key + ":")
            for part in str(value).strip().splitlines():
                additions.append("  " + part.strip())
        else:
            additions.append("%s: %s" % (key, value))
    new_lines = lines[:start + 1] + cleaned + additions + lines[end:]
    atomic_write(path, "\n".join(new_lines).rstrip() + "\n")


def get_pending(args):
    if args.pending_json:
        return json.loads(Path(args.pending_json).read_text())
    if str(args.root) != "/":
        raise Stop("--pending-json is required when --root is not /")
    data = moonraker_json("/printer/objects/query?configfile")
    cf = data["result"]["status"]["configfile"]
    return cf.get("save_config_pending_items", {})


def persist(args):
    doctor(args, write=True)
    p = printer_paths(args.root)
    pending = get_pending(args)
    eddy = pending.get("probe_eddy_current btt_eddy", {})
    temp = pending.get("temperature_probe btt_eddy", {})
    allowed_eddy = {k: v for k, v in eddy.items() if k in ("reg_drive_current", "calibrate")}
    allowed_temp = {k: v for k, v in temp.items() if k in ("calibration_temp", "drift_calibration")}
    if not allowed_eddy and not allowed_temp:
        raise Stop("No pending Eddy calibration values were found.")
    backup(args, "pre-persist")
    if allowed_eddy:
        set_section_values(p["eddy_cfg"], "[probe_eddy_current btt_eddy]", allowed_eddy)
    if allowed_temp:
        set_section_values(p["eddy_cfg"], "[temperature_probe btt_eddy]", allowed_temp)
    reg, points = calibration_state(p["eddy_cfg"])
    print("Persisted only Eddy calibration values.")
    print("  drive current: %s" % (reg or "missing"))
    print("  height-map points: %d" % points)
    print("Issue FIRMWARE_RESTART only after reviewing btteddy_mcu.cfg.")


def patch_stepper_z(path):
    text = read_text(path)
    lines = text.splitlines()
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == "[stepper_z]":
            start = i
            break
    if start is None:
        raise Stop("[stepper_z] not found")
    for i in range(start + 1, len(lines)):
        if lines[i].strip().startswith("["):
            end = i
            break
    out = lines[:start + 1]
    wrote_endstop = False
    for line in lines[start + 1:end]:
        s = line.strip()
        if s.startswith("endstop_pin:"):
            out.append("endstop_pin: probe:z_virtual_endstop")
            wrote_endstop = True
        elif s.startswith("position_endstop:"):
            continue
        else:
            out.append(line)
    if not wrote_endstop:
        out.append("endstop_pin: probe:z_virtual_endstop")
    out.extend(lines[end:])
    atomic_write(path, "\n".join(out).rstrip() + "\n")


def patch_homing_override_safety(text):
    """Add the validated connectivity-only pre-XY Eddy check.

    When XY is unknown the probe can be off-bed.  EDDY_HOME_STATUS is used
    only to prove the Eddy MCU/sensor is responsive; CLEAR_SIDE is not treated
    as physical nozzle clearance until XY geometry is known.
    """
    section_header = "[homing_override]"
    lines = text.splitlines(True)
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == section_header:
            start = i
            break
    if start is None:
        raise Stop("Expected [homing_override] section not found.")
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith("[") and s.endswith("]"):
            end = i
            break

    block = "".join(lines[start:end])
    first = "  {% if x_axes is not defined or x_axes[2] is not defined %}"
    following = (
        "  {% if x_axes is defined and x_axes[0] is defined "
        "and x_axes[1] is defined %}"
    )
    a = block.find(first)
    b = block.find(following, a + len(first))
    if a < 0 or b < 0:
        raise Stop(
            "Expected unknown-Z block in [homing_override] was not found."
        )

    safe = VALIDATED_PRE_XY_BLOCK
    new_block = block[:a] + safe + block[b:]
    return "".join(lines[:start]) + new_block + "".join(lines[end:])


def patch_native_homing(sensorless):
    text = read_text(sensorless)
    if "[gcode_macro _IF_HOME_Z]" not in text or "[gcode_macro _HOME_Z]" not in text:
        raise Stop("Expected K1 Max sensorless macros not found")

    guard = VALIDATED_IF_HOME_Z
    homez = VALIDATED_HOME_Z

    text = replace_section(text, "[gcode_macro _IF_HOME_Z]", guard)
    text = replace_section(text, "[gcode_macro _HOME_Z]", homez)
    text = patch_homing_override_safety(text)
    atomic_write(sensorless, text)


def patch_accurate_g28(path):
    text = read_text(path)
    section = """[gcode_macro ACCURATE_G28]
gcode:
  {% if "probe_eddy_current btt_eddy" in printer.configfile.settings %}
    {action_respond_info("Eddy configured: ACCURATE_G28 skipping redundant second Z home")}
  {% else %}
    ACCURATE_HOME_Z
  {% endif %}"""
    atomic_write(path, replace_section(text, "[gcode_macro ACCURATE_G28]", section))


def activate(args):
    doctor(args, write=True)
    p = printer_paths(args.root)
    reg, points = calibration_state(p["eddy_cfg"])
    if reg is None:
        raise Stop("Drive-current calibration is not persisted.")
    if points < 50:
        raise Stop("Eddy height map is missing/incomplete (%d points found)." % points)
    sensorless_text = read_text(p["sensorless"])
    if sensorless_text.count("_HOME_Y") < 2 or sensorless_text.count("_HOME_X") < 2:
        raise Stop("Two-pass K1 Max sensorless homing pattern was not detected.")
    backup(args, "pre-activate")
    patch_stepper_z(p["printer"])
    patch_native_homing(p["sensorless"])
    patch_accurate_g28(p["gcode_macro"])
    print("Native Eddy Z activation written. No motion command was sent.")
    print("Review the files, issue FIRMWARE_RESTART, then validate G28 with your hand on power.")


def make_wipe(args):
    approach_z = args.start_surface_z + args.approach_clearance
    wipe_end_z = args.end_surface_z - args.wipe_depth
    return f"""{MARKER}
{WIPE_MARKER}
# Values below were explicitly confirmed as measurements for this printer.
[gcode_macro NOZZLE_CLEAR]
description: Eddy-safe fixed-height K1 Max CFS napkin wipe
rename_existing: NOZZLE_CLEAR_PRTOUCH
gcode:
  {{% set hot_min = params.HOT_MIN_TEMP|default(140)|float %}}
  {{% set hot_max = params.HOT_MAX_TEMP|default(200)|float %}}
  {{% set bed_temp = params.BED_MAX_TEMP|default(60)|float %}}
  {{% set start_x = {args.start_x:.6f} %}}
  {{% set start_y = {args.start_y:.6f} %}}
  {{% set start_surface_z = {args.start_surface_z:.6f} %}}
  {{% set end_x = {args.end_x:.6f} %}}
  {{% set end_y = {args.end_y:.6f} %}}
  {{% set end_surface_z = {args.end_surface_z:.6f} %}}
  {{% set approach_z = {approach_z:.6f} %}}
  {{% set wipe_end_z = {wipe_end_z:.6f} %}}

  {{% if printer.toolhead.homed_axes != "xyz" %}}
    {{action_raise_error("Eddy-safe NOZZLE_CLEAR requires XYZ homed")}}
  {{% endif %}}
  SAVE_GCODE_STATE NAME=EDDY_NOZZLE_CLEAR_STATE
  M140 S{{bed_temp}}
  M104 S{{hot_min}}
  M106 P0 S0
  M106 P2 S0
  {{% if hot_min > 0 %}}
    TEMPERATURE_WAIT SENSOR=extruder MINIMUM={{hot_min - 10}} MAXIMUM={{hot_min + 10}}
  {{% endif %}}
  M104 S{{hot_min + 40}}
  G90
  G1 Z10 F150
  G1 X{{start_x}} Y{{start_y}} F9000
  G1 Z{{approach_z}} F150
  M104 S{{hot_max}}
  {{% if hot_max > 0 %}}
    TEMPERATURE_WAIT SENSOR=extruder MINIMUM={{hot_max - 10}} MAXIMUM={{hot_max + 10}}
  {{% endif %}}
  M104 S{{hot_min}}
  G1 X{{end_x}} Y{{end_y}} Z{{wipe_end_z}} F120
  M106 P0 S255
  M106 P2 S255
  {{% if hot_min > 0 %}}
    TEMPERATURE_WAIT SENSOR=extruder MINIMUM={{hot_min - 5}} MAXIMUM={{hot_min + 5}}
  {{% endif %}}
  G1 X{{end_x + 10.0}} Y{{end_y}} Z{{end_surface_z + 10.0}} F120
  M106 P0 S0
  M106 P2 S0
  M140 S{{bed_temp}}
  {{% if bed_temp > 0 %}}
    TEMPERATURE_WAIT SENSOR=heater_bed MINIMUM={{bed_temp - 5}} MAXIMUM={{bed_temp + 5}}
  {{% endif %}}
  G1 X142.5 Y150.0 Z10 F9000
  RESTORE_GCODE_STATE NAME=EDDY_NOZZLE_CLEAR_STATE

[gcode_macro CHECK_BED_MESH]
description: Eddy-safe CFS bed mesh router
rename_existing: CHECK_BED_MESH_PRTOUCH
gcode:
  {{% set auto_g29 = params.AUTO_G29|default(0)|int %}}
  {{% if "probe_eddy_current btt_eddy" in printer.configfile.settings %}}
    {{% if printer.toolhead.homed_axes != "xyz" %}}
      {{action_raise_error("Eddy-safe CHECK_BED_MESH requires XYZ homed")}}
    {{% endif %}}
    {{% if auto_g29 == 1 %}}
      BED_MESH_CLEAR
      BED_MESH_CALIBRATE PROFILE=eddy_runtime METHOD=rapid_scan HORIZONTAL_MOVE_Z=2 MESH_MIN=15,15 MESH_MAX=280,285 PROBE_COUNT=20,20 ALGORITHM=bicubic
      BED_MESH_PROFILE REMOVE=eddy_runtime
    {{% else %}}
      {{action_raise_error("Eddy-safe CHECK_BED_MESH requires AUTO_G29=1")}}
    {{% endif %}}
  {{% else %}}
    CHECK_BED_MESH_PRTOUCH {{rawparams}}
  {{% endif %}}
"""


def configure_wipe(args):
    doctor(args, write=True)
    if not args.confirm_measured:
        raise Stop("--confirm-measured is required; do not use somebody else's wipe Z values.")
    for name in ("start_surface_z", "end_surface_z"):
        value = getattr(args, name)
        if not (0.0 < value < 20.0):
            raise Stop("%s is outside the conservative 0..20 mm sanity range." % name)
    for name in ("start_x", "start_y", "end_x", "end_y"):
        value = getattr(args, name)
        if not (-5.0 <= value <= 315.0):
            raise Stop("%s is outside the K1 Max sanity range." % name)
    backup(args, "pre-wipe")
    p = printer_paths(args.root)
    atomic_write(p["eddy_macros"], make_wipe(args))
    print("Measured fixed wipe written. No motion or heater command was sent.")


def status(args):
    p = printer_paths(args.root)
    fw, _ = detect_firmware(args.root)
    reg, points = calibration_state(p["eddy_cfg"])
    printer = read_text(p["printer"])
    sensorless = read_text(p["sensorless"])
    macros = read_text(p["eddy_macros"])
    native = bool(re.search(r"(?m)^\s*endstop_pin:\s*probe:z_virtual_endstop\s*$", printer))
    print("Firmware:             %s" % (fw or "unknown"))
    print("Eddy config:           %s" % ("present" if p["eddy_cfg"].exists() else "missing"))
    print("Drive current:         %s" % (reg or "missing"))
    print("Height-map points:     %d" % points)
    print("Native Eddy Z:         %s" % ("ACTIVE" if native else "not active"))
    print("Pre-XY Eddy check:     %s" % ("present" if "EDDY_HOME_STATUS SAMPLES=50 TIMEOUT=2" in sensorless else "missing"))
    print("Bounded unknown-Z move:%s" % (" present" if "z_safe_g28} VELOCITY=10" in sensorless else " missing"))
    print("Pre-Z Eddy clearance:  %s" % ("present" if "EDDY_PREHOME_CLEAR MAX_TRAVEL=2.000" in sensorless else "missing"))
    print("Unsafe off-bed guard:  %s" % ("ABSENT (good)" if "MARGIN=1.000 MAX_TRAVEL=5.000" not in sensorless else "PRESENT - REVIEW"))
    contract = sensorless_contract(sensorless)
    contract_ok = all(contract.values())
    print("Production safety:     %s" % ("PASS" if contract_ok else "DRIFT - REVIEW"))
    sensorless_hash = sha256_file(p["sensorless"]) if p["sensorless"].exists() else None
    print(
        "Production file hash:  %s"
        % (
            "EXACT MATCH"
            if sensorless_hash == PRODUCTION_SENSORLESS_SHA256
            else ("different (section contract still applies)" if sensorless_hash else "missing")
        )
    )
    if not contract_ok:
        print(
            "  contract details: %s"
            % ", ".join(
                "%s=%s" % (name, "ok" if ok else "DRIFT")
                for name, ok in contract.items()
            )
        )
    print("Fixed napkin wipe:     %s" % ("configured" if WIPE_MARKER in macros else "NOT CONFIGURED"))



def verify_production(args):
    """Read-only comparison against the corrected production reference."""
    p = printer_paths(args.root)
    rows = []

    def record(name, path, expected_hash, custom_ok=None, custom_message=""):
        path = Path(path)
        if not path.exists():
            rows.append(("DRIFT", name, "missing", None, expected_hash))
            return
        actual = sha256_file(path)
        if actual == expected_hash:
            rows.append(("EXACT", name, "production SHA256 match", actual, expected_hash))
            return
        ok = False
        message = custom_message
        if custom_ok is not None:
            try:
                ok = bool(custom_ok(path))
            except Exception as exc:
                message = "validation error: %s" % exc
                ok = False
        if ok:
            rows.append((
                "EXPECTED CUSTOM", name,
                message or "machine-specific bytes differ but required structure is valid",
                actual, expected_hash,
            ))
        else:
            rows.append((
                "DRIFT", name,
                message or "SHA256 differs and required structure was not validated",
                actual, expected_hash,
            ))

    def sensorless_ok(path):
        return all(sensorless_contract(read_text(path)).values())

    def printer_ok(path):
        text = read_text(path)
        return (
            re.search(
                r"(?m)^\s*endstop_pin:\s*probe:z_virtual_endstop\s*$",
                text,
            )
            is not None
            and "[include btteddy_mcu.cfg]" in text
            and "[include eddy_nozzle_clear.cfg]" in text
        )

    def eddy_cfg_ok(path):
        reg, points = calibration_state(path)
        text = read_text(path)
        return (
            "[probe_eddy_current btt_eddy]" in text
            and reg is not None
            and points >= 50
            and "serial:" in text
        )

    def wipe_ok(path):
        text = read_text(path)
        return (
            WIPE_MARKER in text
            and "[gcode_macro NOZZLE_CLEAR]" in text
            and "[gcode_macro CHECK_BED_MESH]" in text
        )

    def gcode_macro_ok(path):
        text = read_text(path)
        block = section_core(text, "[gcode_macro ACCURATE_G28]")
        return (
            block is not None
            and "probe_eddy_current btt_eddy" in block
            and "ACCURATE_HOME_Z" in block
        )

    def eddy_helper_ok(path):
        text = read_text(path)
        # The production helper's checksum is known, but its complete bytes
        # were not recoverable as a repository artifact.  A non-exact helper
        # is accepted only if the required public safety commands exist and
        # the motion command remains bounded and positive-only.
        return (
            "EDDY_HOME_STATUS" in text
            and "EDDY_PREHOME_CLEAR" in text
            and "force_move.manual_move" in text
            and "move_distance = min(step, remaining)" in text
            and "if freq_change > 40.0:" in text
            and "total_moved >= 0.075" in text
        )

    record(
        "sensorless.cfg",
        p["sensorless"],
        PRODUCTION_SHA256["config/sensorless.cfg"],
        sensorless_ok,
        "exact recovered production safety sections match",
    )
    record(
        "printer.cfg",
        p["printer"],
        PRODUCTION_SHA256["config/printer.cfg"],
        printer_ok,
        "machine-specific config differs; native Eddy Z and required includes are present",
    )
    record(
        "btteddy_mcu.cfg",
        p["eddy_cfg"],
        PRODUCTION_SHA256["config/btteddy_mcu.cfg"],
        eddy_cfg_ok,
        "machine-specific serial/calibration differs; calibrated Eddy config is present",
    )
    record(
        "eddy_nozzle_clear.cfg",
        p["eddy_macros"],
        PRODUCTION_SHA256["config/eddy_nozzle_clear.cfg"],
        wipe_ok,
        "printer-specific napkin coordinates differ; guarded wipe/mesh macros are present",
    )
    record(
        "gcode_macro.cfg",
        p["gcode_macro"],
        PRODUCTION_SHA256["config/gcode_macro.cfg"],
        gcode_macro_ok,
        "other macro content differs; Eddy-aware ACCURATE_G28 routing is present",
    )

    # These compatibility modules should remain exact production sources.
    for rel in (
        "extras/upgrade/ldc1612.py",
        "extras/upgrade/probe_eddy_current.py",
        "extras/upgrade/bulk_sensor.py",
    ):
        record(
            rel,
            p["klippy"] / rel,
            PRODUCTION_SHA256["klippy/" + rel],
        )

    record(
        "extras/eddy_z_acquire.py",
        p["klippy"] / "extras/eddy_z_acquire.py",
        PRODUCTION_SHA256["klippy/extras/eddy_z_acquire.py"],
        eddy_helper_ok,
        "production checksum is known but exact helper bytes are unrecovered; required safety behavior is present",
    )

    print("K1 Max + CFS + BTT Eddy production verification")
    print("Reference: known-good-eddy-production-20261001-153849")
    print("Read-only: no files, services, or printer state were changed.\n")
    for state, name, message, actual, expected in rows:
        print("%-15s %-36s %s" % (state, name + ":", message))
        if actual and actual != expected:
            print("  current:   %s" % actual)
            print("  reference: %s" % expected)

    exact = sum(1 for row in rows if row[0] == "EXACT")
    custom = sum(1 for row in rows if row[0] == "EXPECTED CUSTOM")
    drift = sum(1 for row in rows if row[0] == "DRIFT")
    print(
        "\nSummary: %d EXACT, %d EXPECTED CUSTOM, %d DRIFT"
        % (exact, custom, drift)
    )
    if drift:
        print("Result: REVIEW REQUIRED")
        return 3
    print("Result: production safety profile accepted")
    return 0


def rollback(args):
    assert_idle(args.root)
    src = Path(args.backup_dir)
    if not src.is_absolute():
        src = printer_paths(args.root)["backups"] / src
    manifest_path = src / "manifest.json"
    if not manifest_path.exists() or not (src / "config").exists():
        raise Stop("Not a helper backup: %s" % src)
    manifest = json.loads(manifest_path.read_text())
    p = printer_paths(args.root)
    safety = backup(args, "pre-rollback")
    shutil.rmtree(p["config"])
    shutil.copytree(src / "config", p["config"])
    original = src / "klippy-original"
    for rel_s in manifest.get("touched_klippy", []):
        rel = Path(rel_s)
        dst = p["klippy"] / rel
        saved = original / rel
        if saved.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(saved, dst)
        elif dst.exists():
            dst.unlink()
    print("Restored: %s" % src)
    print("Safety snapshot of pre-rollback state: %s" % safety)
    print("No restart or motion command was sent.")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="/", help=argparse.SUPPRESS)
    parser.add_argument("--force-unsupported", action="store_true",
                        help="development only: bypass the 2.3.5.33 firmware stop")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor")
    sub.add_parser("backup")
    sub.add_parser("status")
    sub.add_parser("verify-production")

    st = sub.add_parser("stage")
    st.add_argument("--eddy-serial")
    st.add_argument("--x-offset", type=float, required=True)
    st.add_argument("--y-offset", type=float, required=True)
    st.add_argument("--z-offset", type=float, default=2.5,
                    help="validated starting trigger height; verify on your hardware")

    pe = sub.add_parser("persist")
    pe.add_argument("--pending-json", help=argparse.SUPPRESS)

    sub.add_parser("activate")

    wi = sub.add_parser("configure-wipe")
    wi.add_argument("--start-x", type=float, required=True)
    wi.add_argument("--start-y", type=float, required=True)
    wi.add_argument("--start-surface-z", type=float, required=True)
    wi.add_argument("--end-x", type=float, required=True)
    wi.add_argument("--end-y", type=float, required=True)
    wi.add_argument("--end-surface-z", type=float, required=True)
    wi.add_argument("--approach-clearance", type=float, default=0.20)
    wi.add_argument("--wipe-depth", type=float, default=0.30)
    wi.add_argument("--confirm-measured", action="store_true")

    rb = sub.add_parser("rollback")
    rb.add_argument("backup_dir")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            doctor(args)
        elif args.command == "backup":
            doctor(args, write=True)
            backup(args)
        elif args.command == "stage":
            stage(args)
        elif args.command == "persist":
            persist(args)
        elif args.command == "activate":
            activate(args)
        elif args.command == "configure-wipe":
            configure_wipe(args)
        elif args.command == "status":
            status(args)
        elif args.command == "verify-production":
            return verify_production(args)
        elif args.command == "rollback":
            rollback(args)
        else:
            parser.error("unknown command")
    except Stop as exc:
        print("STOP: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
