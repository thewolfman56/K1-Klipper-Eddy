import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "k1max_cfs_eddy.py"
FIXTURES = REPO / "tests" / "fixtures"


def fixture(name):
    return (FIXTURES / name).read_text()


def section_core(text, header):
    lines = text.splitlines(True)
    start = None
    end = len(lines)
    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i
            break
    if start is None:
        raise AssertionError("section not found: %s" % header)
    for i in range(start + 1, len(lines)):
        s = lines[i].strip()
        if s.startswith("[") and s.endswith("]"):
            end = i
            break
    return "".join(lines[start:end]).rstrip("\n") + "\n"


def pre_xy_block(text):
    block = section_core(text, "[homing_override]")
    first = "  {% if x_axes is not defined or x_axes[2] is not defined %}"
    following = (
        "  {% if x_axes is defined and x_axes[0] is defined "
        "and x_axes[1] is defined %}"
    )
    a = block.find(first)
    b = block.find(following, a + len(first))
    if a < 0 or b < 0:
        raise AssertionError("unknown-Z block not found")
    return block[a:b]


def homing_override_without_pre_xy(text):
    block = section_core(text, "[homing_override]")
    first = "  {% if x_axes is not defined or x_axes[2] is not defined %}"
    following = (
        "  {% if x_axes is defined and x_axes[0] is defined "
        "and x_axes[1] is defined %}"
    )
    a = block.find(first)
    b = block.find(following, a + len(first))
    if a < 0 or b < 0:
        raise AssertionError("unknown-Z block not found")
    return block[:a] + "<VALIDATED_PRE_XY_BLOCK>\n" + block[b:]


def write(root, rel, text):
    p = root / rel.lstrip("/")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


class InstallerFlowTest(unittest.TestCase):
    def run_helper(self, root, *args):
        cmd = [sys.executable, str(SCRIPT), "--root", str(root), *args]
        return subprocess.run(
            cmd, cwd=REPO, text=True, capture_output=True, check=True
        )

    def make_root(self, root):
        write(root, "/etc/ota_info", "version=2.3.5.33\n")
        write(root, "/usr/data/printer_data/config/printer.cfg", """[stepper_z]
step_pin: PB0
endstop_pin: tmc2209_stepper_z:virtual_endstop
position_endstop: 0

[stepper_x]
position_max: 300

[stepper_y]
position_max: 300
""")
        write(root, "/usr/data/printer_data/config/sensorless.cfg", """[gcode_macro xyz_ready]
variable_x_ready: 0
variable_y_ready: 0
variable_z_ready: 0
variable_xy_moved: 0
variable_z_moved: 0
gcode:

[gcode_macro PRINTER_PARAM]
variable_z_safe_g28: 3.0
variable_max_y_position: 300
gcode:

[gcode_macro _IF_HOME_Z]
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
      {% if printer.print_stats.z_pos|float <= 20.0 or printer.print_stats.power_loss == 1 %}
        FORCE_MOVE STEPPER=stepper_z DISTANCE={printer["gcode_macro PRINTER_PARAM"].z_safe_g28} VELOCITY=10
      {% else %}
        FORCE_MOVE STEPPER=stepper_z DISTANCE=0.1 VELOCITY=10
      {% endif %}
      SET_GCODE_VARIABLE MACRO=xyz_ready VARIABLE=z_moved VALUE=1
    {% endif %}
  {% endif %}

[gcode_macro _IF_MOVE_XY]
gcode:
  _IF_HOME_Z

[gcode_macro _HOME_Y]
gcode:
  _IF_MOVE_XY

[gcode_macro _HOME_X]
gcode:
  _IF_MOVE_XY

[gcode_macro _HOME_Z]
gcode:
  {% if printer.print_stats.z_pos|float >= 260.0 %}
    FORCE_MOVE STEPPER=stepper_z DISTANCE=-8 VELOCITY=10
  {% endif %}
  G28 Z

[homing_override]
axes: xyz
gcode:
  M220 S100
  {% set x_axes = printer.toolhead.homed_axes %}
  {% if x_axes is defined and x_axes[0] is defined %}
    {action_respond_info("x_axes: %s \\n" % (x_axes))}
  {% else %}
    SET_GCODE_VARIABLE MACRO=xyz_ready VARIABLE=x_ready VALUE=0
    SET_GCODE_VARIABLE MACRO=xyz_ready VARIABLE=y_ready VALUE=0
    SET_GCODE_VARIABLE MACRO=xyz_ready VARIABLE=z_ready VALUE=0
    SET_GCODE_VARIABLE MACRO=xyz_ready VARIABLE=xy_moved VALUE=0
    SET_GCODE_VARIABLE MACRO=xyz_ready VARIABLE=z_moved VALUE=0
    {action_respond_info("x_axes is NULL\\n")}
  {% endif %}

  {% if x_axes is not defined or x_axes[2] is not defined %}
    BED_MESH_CLEAR
  {% endif %}

  {% if x_axes is defined and x_axes[0] is defined and x_axes[1] is defined %}
    {action_respond_info("x_axes: %s \\n" % (x_axes))}
  {% endif %}

  {% set home_all = 'X' not in params and 'Y' not in params %}
  {% if home_all or 'Y' in params %}
    _HOME_Y
  {% endif %}
  {% if home_all or 'Y' in params %}
    _HOME_Y
  {% endif %}
  {% if home_all or 'X' in params %}
    _HOME_X
  {% endif %}
  {% if home_all or 'X' in params %}
    _HOME_X
  {% endif %}
  {% if home_all or 'Z' in params %}
    _HOME_Z
  {% endif %}
""")
        write(root, "/usr/data/printer_data/config/gcode_macro.cfg", """[gcode_macro ACCURATE_G28]
gcode:
  ACCURATE_HOME_Z
""")
        write(root, "/usr/data/printer_data/config/box.cfg", "[box]\n")
        write(root, "/usr/share/klipper/klippy/extras/bed_mesh.py", "# stock creality bed mesh\n")
        write(root, "/usr/share/klipper/klippy/mcu.py", """# synthetic Creality .33 mcu
import sys, os, zlib, logging, math
import serialhdl, msgproto, pins, chelper, clocksync

# CREALITY_MCU_SENTINEL_MUST_SURVIVE

def add_printer_objects(config):
    printer = config.get_printer()
    reactor = printer.get_reactor()
    mainsync = clocksync.ClockSync(reactor)
    printer.add_object('mcu', MCU(config.getsection('mcu'), mainsync))
    for s in config.get_prefix_sections('mcu '):
        printer.add_object(s.section, MCU(
            s, clocksync.SecondarySync(reactor, mainsync)))

def get_printer_mcu(printer, name):
    return printer.lookup_object(name)
""")
        write(root, "/usr/share/klipper/klippy/stepper.py", "# CREALITY_STEPPER_SENTINEL\n")
        write(root, "/dev/serial/by-id/usb-Klipper_rp2040_TEST-if00", "")

    def install_validated_optional_addons(self, root):
        cfg = root / "usr/data/printer_data/config"
        printer = (cfg / "printer.cfg").read_text()
        (cfg / "printer.cfg").write_text(
            "[include Helper-Script/camera-settings.cfg]\n" + printer
        )
        write(
            root,
            "/usr/data/printer_data/config/Helper-Script/camera-settings.cfg",
            "[gcode_macro CAM_SETTINGS]\ngcode:\n  RESPOND MSG=camera\n",
        )

        write(
            root,
            "/usr/data/octoeverywhere/install.sh",
            'PY_LAUNCH_JSON="DisableMoonrakerConfigFileWrites"\n',
        )
        write(
            root,
            "/usr/data/printer_data/octoeverywhere-store/"
            "run-octoeverywhere-service.sh",
            "#!/bin/sh\nexport PYTHONPATH=/usr/data/octoeverywhere\n"
            "exec /usr/data/octoeverywhere-env/bin/python3 "
            "-m moonraker_octoeverywhere test\n",
        )
        write(
            root,
            "/etc/init.d/S66octoeverywhere_service",
            "#!/bin/sh\n",
        )
        write(
            root,
            "/usr/data/printer_data/config/octoeverywhere-system.cfg",
            "[octoeverywhere]\n",
        )
        write(
            root,
            "/proc/111/cmdline",
            "python3\x00-m\x00moonraker_octoeverywhere\x00",
        )
        write(root, "/var/run/octoeverywhere.pid", "111\n")

        write(
            root,
            "/usr/data/mobileraker_companion/scripts/install.sh",
            'echo "K1: using stock Creality Python 3.8; '
            'skipping Entware Python/PIP/Pillow install."\n',
        )
        write(
            root,
            "/usr/data/mobileraker_companion/.k1/run-companion-service.sh",
            "#!/bin/sh\n"
            "export PYTHONPATH=/usr/data/mobileraker_companion\n"
            "exec /usr/data/mobileraker-env/bin/python3 "
            "/usr/data/mobileraker_companion/mobileraker.py\n",
        )
        write(
            root,
            "/etc/init.d/S80mobileraker_service",
            "#!/bin/sh\n",
        )
        write(
            root,
            "/proc/222/cmdline",
            "/usr/data/mobileraker-env/bin/python3\x00"
            "/usr/data/mobileraker_companion/mobileraker.py\x00",
        )
        write(root, "/var/run/mobileraker.pid", "222\n")

    def test_doctor_audits_validated_optional_addons(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_root(root)
            self.install_validated_optional_addons(root)

            out = self.run_helper(root, "doctor").stdout

            self.assertIn("Optional add-on audit (read-only)", out)
            self.assertIn("PASS Camera Settings Control:", out)
            self.assertIn("PASS OctoEverywhere:", out)
            self.assertIn("K1 service wrapper uses exec", out)
            self.assertIn("exactly one runtime process found (PID 111)", out)
            self.assertIn("PASS Mobileraker Companion:", out)
            self.assertIn("stock-Python K1 bootstrap marker found", out)
            self.assertIn("exactly one runtime process found (PID 222)", out)
            self.assertIn("Summary: 0 warning(s); no files were changed.", out)

    def test_doctor_warns_on_risky_optional_addon_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_root(root)
            self.install_validated_optional_addons(root)

            write(root, "/opt/bin/python3", "# fake Entware Python\n")
            write(
                root,
                "/usr/data/printer_data/octoeverywhere-store/"
                "run-octoeverywhere-service.sh",
                "#!/bin/sh\n"
                "PYTHONPATH=/usr/data/octoeverywhere "
                "/usr/data/octoeverywhere-env/bin/python3 "
                "-m moonraker_octoeverywhere test\n",
            )
            write(
                root,
                "/proc/112/cmdline",
                "python3\x00-m\x00moonraker_octoeverywhere\x00",
            )
            write(root, "/var/run/octoeverywhere.pid", "999\n")

            out = self.run_helper(root, "doctor").stdout

            self.assertIn("WARN OctoEverywhere:", out)
            self.assertIn("/opt/bin/python3 exists", out)
            self.assertIn("does not use exec", out)
            self.assertIn("multiple runtime processes found: 111, 112", out)
            self.assertIn("PID file 999 does not match", out)
            self.assertIn("WARN Mobileraker Companion:", out)

    def test_stage_keeps_bounded_unknown_z_move_without_off_bed_eddy_clearance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_root(root)

            sensorless_path = (
                root / "usr/data/printer_data/config/sensorless.cfg"
            )
            before = sensorless_path.read_text()

            self.run_helper(
                root, "stage", "--x-offset", "-23", "--y-offset", "0"
            )
            sensorless = sensorless_path.read_text()

            # Calibration staging must not rewrite Creality's homing file.
            self.assertEqual(before, sensorless)

            self.assertIn(
                'FORCE_MOVE STEPPER=stepper_z DISTANCE={printer["gcode_macro PRINTER_PARAM"].z_safe_g28} VELOCITY=10',
                sensorless,
            )
            self.assertNotIn(
                "EDDY_PREHOME_CLEAR MARGIN=1.000 MAX_TRAVEL=5.000",
                sensorless,
            )
            self.assertNotIn(
                "EDDY_HOME_STATUS SAMPLES=50 TIMEOUT=2",
                sensorless,
            )

    def test_verify_production_accepts_expected_machine_specific_differences(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_root(root)

            self.run_helper(
                root, "stage", "--x-offset", "-23", "--y-offset", "0"
            )
            pairs = ",".join(
                "%.3f:%.3f" % (0.05 + i * 0.04, 3000000 - i * 1000)
                for i in range(60)
            )
            pending = root / "pending.json"
            pending.write_text(json.dumps({
                "probe_eddy_current btt_eddy": {
                    "reg_drive_current": "16",
                    "calibrate": pairs,
                }
            }))
            self.run_helper(
                root, "persist", "--pending-json", str(pending)
            )
            self.run_helper(root, "activate")
            self.run_helper(
                root, "configure-wipe",
                "--start-x", "70.5", "--start-y", "305.5",
                "--start-surface-z", "4.2",
                "--end-x", "90.5", "--end-y", "305.5",
                "--end-surface-z", "4.35",
                "--confirm-measured",
            )

            out = self.run_helper(root, "verify-production").stdout
            self.assertIn(
                "K1 Max + CFS + BTT Eddy production verification", out
            )
            self.assertIn("EXPECTED CUSTOM sensorless.cfg:", out)
            self.assertIn("EXPECTED CUSTOM printer.cfg:", out)
            self.assertIn("EXPECTED CUSTOM btteddy_mcu.cfg:", out)
            self.assertIn("EXPECTED CUSTOM eddy_nozzle_clear.cfg:", out)
            self.assertIn("EXACT           extras/upgrade/ldc1612.py:", out)
            self.assertIn(
                "EXACT           extras/upgrade/probe_eddy_current.py:", out
            )
            self.assertIn(
                "EXACT           extras/upgrade/bulk_sensor.py:", out
            )
            self.assertIn("EXPECTED CUSTOM extras/eddy_z_acquire.py:", out)
            self.assertIn("0 DRIFT", out)
            self.assertIn(
                "Result: production safety profile accepted", out
            )

    def test_verify_production_returns_nonzero_on_safety_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_root(root)

            # Build a normally activated installation first.
            self.run_helper(
                root, "stage", "--x-offset", "-23", "--y-offset", "0"
            )
            pairs = ",".join(
                "%.3f:%.3f" % (0.05 + i * 0.04, 3000000 - i * 1000)
                for i in range(60)
            )
            pending = root / "pending.json"
            pending.write_text(json.dumps({
                "probe_eddy_current btt_eddy": {
                    "reg_drive_current": "16",
                    "calibrate": pairs,
                }
            }))
            self.run_helper(
                root, "persist", "--pending-json", str(pending)
            )
            self.run_helper(root, "activate")

            sensorless = (
                root / "usr/data/printer_data/config/sensorless.cfg"
            )
            text = sensorless.read_text().replace(
                "EDDY_HOME_STATUS SAMPLES=50 TIMEOUT=2",
                "EDDY_HOME_STATUS SAMPLES=25 TIMEOUT=2",
            )
            sensorless.write_text(text)

            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "--root", str(root),
                    "verify-production",
                ],
                cwd=REPO, text=True, capture_output=True,
            )
            self.assertEqual(proc.returncode, 3)
            self.assertIn("DRIFT           sensorless.cfg:", proc.stdout)
            self.assertIn("Result: REVIEW REQUIRED", proc.stdout)

    def make_release_ready_install(self, root):
        self.make_root(root)
        self.run_helper(
            root, "stage", "--x-offset", "-23", "--y-offset", "0"
        )
        pairs = ",".join(
            "%.3f:%.3f" % (0.05 + i * 0.04, 3000000 - i * 1000)
            for i in range(60)
        )
        pending = root / "pending.json"
        pending.write_text(json.dumps({
            "probe_eddy_current btt_eddy": {
                "reg_drive_current": "16",
                "calibrate": pairs,
            }
        }))
        self.run_helper(
            root, "persist", "--pending-json", str(pending)
        )
        self.run_helper(root, "activate")
        self.run_helper(
            root, "configure-wipe",
            "--start-x", "70.5", "--start-y", "305.5",
            "--start-surface-z", "4.2",
            "--end-x", "90.5", "--end-y", "305.5",
            "--end-surface-z", "4.35",
            "--confirm-measured",
        )

    def test_release_readiness_accepts_validated_public_install_with_warning(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_release_ready_install(root)

            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "--root", str(root),
                    "release-readiness",
                ],
                cwd=REPO, text=True, capture_output=True,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertIn(
                "K1 Max + CFS + BTT Eddy release-readiness",
                proc.stdout,
            )
            self.assertIn("PASS  Firmware:", proc.stdout)
            self.assertIn(
                "PASS  Production homing safety:", proc.stdout
            )
            self.assertIn(
                "PASS  extras/upgrade/ldc1612.py:", proc.stdout
            )
            self.assertIn(
                "PASS  extras/upgrade/probe_eddy_current.py:",
                proc.stdout,
            )
            self.assertIn(
                "PASS  extras/upgrade/bulk_sensor.py:", proc.stdout
            )
            self.assertIn(
                "WARN  eddy_z_acquire.py:", proc.stdout
            )
            self.assertIn(
                "PASS  Optional add-ons:", proc.stdout
            )
            self.assertIn(
                "PASS  Firmware-update snapshot:", proc.stdout
            )
            self.assertIn(
                "PASS  Repository files:", proc.stdout
            )
            self.assertIn(
                "Release readiness: READY WITH WARNINGS",
                proc.stdout,
            )

    def test_release_readiness_fails_on_core_safety_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_release_ready_install(root)

            sensorless = (
                root / "usr/data/printer_data/config/sensorless.cfg"
            )
            sensorless.write_text(
                sensorless.read_text().replace(
                    "EDDY_HOME_STATUS SAMPLES=50 TIMEOUT=2",
                    "EDDY_HOME_STATUS SAMPLES=25 TIMEOUT=2",
                )
            )

            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "--root", str(root),
                    "release-readiness",
                ],
                cwd=REPO, text=True, capture_output=True,
            )
            self.assertEqual(proc.returncode, 5)
            self.assertIn(
                "FAIL  Production homing safety:", proc.stdout
            )
            self.assertIn(
                "Release readiness: NOT READY", proc.stdout
            )

    def test_firmware_update_snapshot_and_no_change_audit(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_root(root)

            self.run_helper(
                root, "stage", "--x-offset", "-23", "--y-offset", "0"
            )
            pairs = ",".join(
                "%.3f:%.3f" % (0.05 + i * 0.04, 3000000 - i * 1000)
                for i in range(60)
            )
            pending = root / "pending.json"
            pending.write_text(json.dumps({
                "probe_eddy_current btt_eddy": {
                    "reg_drive_current": "16",
                    "calibrate": pairs,
                }
            }))
            self.run_helper(
                root, "persist", "--pending-json", str(pending)
            )
            self.run_helper(root, "activate")
            self.run_helper(
                root, "configure-wipe",
                "--start-x", "70.5", "--start-y", "305.5",
                "--start-surface-z", "4.2",
                "--end-x", "90.5", "--end-y", "305.5",
                "--end-surface-z", "4.35",
                "--confirm-measured",
            )

            snap_out = self.run_helper(
                root, "pre-update-snapshot"
            ).stdout
            self.assertIn(
                "Pre-firmware-update snapshot created:", snap_out
            )
            snapshots = sorted(
                (
                    root / "usr/data/k1max-cfs-eddy-update-snapshots"
                ).glob("*-pre-firmware-update*")
            )
            self.assertEqual(len(snapshots), 1)
            manifest = json.loads(
                (snapshots[0] / "manifest.json").read_text()
            )
            self.assertEqual(
                manifest["kind"],
                "k1max-cfs-eddy-pre-firmware-update",
            )
            self.assertEqual(manifest["firmware"], "2.3.5.33")
            self.assertIn("sensorless.cfg", manifest["config"])
            self.assertIn(
                "/usr/share/klipper/klippy/extras/eddy_z_acquire.py",
                manifest["tracked"],
            )

            audit = self.run_helper(
                root, "audit-after-update", str(snapshots[0])
            ).stdout
            self.assertIn(
                "K1 Max + CFS + BTT Eddy post-firmware-update audit",
                audit,
            )
            self.assertIn("0 CHANGED, 0 MISSING, 0 NEW", audit)
            self.assertIn(
                "Production homing safety contract: PASS", audit
            )
            self.assertIn(
                "Result: no pre-update files were overwritten", audit
            )

    def test_firmware_update_audit_detects_overwrites_without_repair(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_root(root)

            self.run_helper(
                root, "stage", "--x-offset", "-23", "--y-offset", "0"
            )
            pairs = ",".join(
                "%.3f:%.3f" % (0.05 + i * 0.04, 3000000 - i * 1000)
                for i in range(60)
            )
            pending = root / "pending.json"
            pending.write_text(json.dumps({
                "probe_eddy_current btt_eddy": {
                    "reg_drive_current": "16",
                    "calibrate": pairs,
                }
            }))
            self.run_helper(
                root, "persist", "--pending-json", str(pending)
            )
            self.run_helper(root, "activate")
            self.run_helper(
                root, "configure-wipe",
                "--start-x", "70.5", "--start-y", "305.5",
                "--start-surface-z", "4.2",
                "--end-x", "90.5", "--end-y", "305.5",
                "--end-surface-z", "4.35",
                "--confirm-measured",
            )
            self.run_helper(root, "pre-update-snapshot")
            snapshot = next(
                (
                    root / "usr/data/k1max-cfs-eddy-update-snapshots"
                ).glob("*-pre-firmware-update*")
            )

            # Simulate a Creality update overwriting both config and Klipper,
            # plus changing the firmware version.
            write(root, "/etc/ota_info", "version=2.3.5.34\n")
            sensorless = (
                root / "usr/data/printer_data/config/sensorless.cfg"
            )
            before_sensorless = sensorless.read_text()
            sensorless.write_text(
                before_sensorless.replace(
                    "EDDY_HOME_STATUS SAMPLES=50 TIMEOUT=2",
                    "EDDY_HOME_STATUS SAMPLES=25 TIMEOUT=2",
                )
            )
            helper = (
                root
                / "usr/share/klipper/klippy/extras/eddy_z_acquire.py"
            )
            helper_before = helper.read_text()
            helper.write_text("# firmware replaced helper\n")

            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT), "--root", str(root),
                    "audit-after-update", str(snapshot),
                ],
                cwd=REPO, text=True, capture_output=True,
            )
            self.assertEqual(proc.returncode, 4)
            self.assertIn("Baseline firmware: 2.3.5.33", proc.stdout)
            self.assertIn("Current firmware:  2.3.5.34", proc.stdout)
            self.assertIn("CHANGED    config/sensorless.cfg", proc.stdout)
            self.assertIn(
                "CHANGED    /usr/share/klipper/klippy/extras/eddy_z_acquire.py",
                proc.stdout,
            )
            self.assertIn(
                "Production homing safety contract: DRIFT - REVIEW",
                proc.stdout,
            )
            self.assertIn(
                "Result: REVIEW REQUIRED BEFORE ANY RESTORE/REPAIR",
                proc.stdout,
            )

            # Audit is read-only: it must not repair either modified file.
            self.assertNotEqual(sensorless.read_text(), before_sensorless)
            self.assertEqual(
                helper.read_text(), "# firmware replaced helper\n"
            )

    def test_complete_staged_flow_and_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.make_root(root)

            self.run_helper(root, "doctor")
            self.run_helper(
                root, "stage", "--x-offset", "-23", "--y-offset", "0"
            )
            cfg = root / "usr/data/printer_data/config"
            printer = (cfg / "printer.cfg").read_text()
            self.assertIn("[include btteddy_mcu.cfg]", printer)
            self.assertIn("[include eddy_nozzle_clear.cfg]", printer)
            self.assertTrue(
                (root / "usr/share/klipper/klippy/extras/bed_mesh_creality.py").exists()
            )

            klippy = root / "usr/share/klipper/klippy"
            self.assertEqual(
                (klippy / "stepper.py").read_text(),
                "# CREALITY_STEPPER_SENTINEL\n",
            )
            self.assertFalse((klippy / "serialhdl.py").exists())
            self.assertFalse((klippy / "extras/tmc.py").exists())
            self.assertFalse((klippy / "extras/gcode_shell_command.py").exists())
            mcu = (klippy / "mcu.py").read_text()
            self.assertIn("CREALITY_MCU_SENTINEL_MUST_SURVIVE", mcu)
            self.assertIn("from upgrade import mcu as upgrade_mcu", mcu)
            self.assertIn("def _obtain_MCU_class(config):", mcu)
            self.assertTrue((klippy / "upgrade/mcu.py").exists())
            self.assertTrue((klippy / "extras/upgrade/probe_eddy_current.py").exists())
            self.assertTrue((klippy / "extras/probe_eddy_current.py").exists())
            self.assertTrue((klippy / "extras/temperature_probe.py").exists())

            pairs = ",".join(
                "%.3f:%.3f" % (0.05 + i * 0.04, 3000000 - i * 1000)
                for i in range(60)
            )
            pending = root / "pending.json"
            pending.write_text(json.dumps({
                "probe_eddy_current btt_eddy": {
                    "reg_drive_current": "16",
                    "calibrate": pairs,
                }
            }))
            self.run_helper(
                root, "persist", "--pending-json", str(pending)
            )

            staged_sensorless = (cfg / "sensorless.cfg").read_text()
            preserved_sections = {
                header: section_core(staged_sensorless, header)
                for header in (
                    "[gcode_macro _IF_MOVE_XY]",
                    "[gcode_macro _HOME_Y]",
                    "[gcode_macro _HOME_X]",
                )
            }
            preserved_homing_override = homing_override_without_pre_xy(
                staged_sensorless
            )

            self.run_helper(root, "activate")

            printer = (cfg / "printer.cfg").read_text()
            sensorless = (cfg / "sensorless.cfg").read_text()
            self.assertIn("endstop_pin: probe:z_virtual_endstop", printer)
            self.assertNotIn("position_endstop:", printer)
            self.assertNotIn(
                "EDDY_PREHOME_CLEAR MARGIN=1.000 MAX_TRAVEL=5.000",
                sensorless,
            )
            self.assertIn(
                "EDDY_HOME_STATUS SAMPLES=50 TIMEOUT=2", sensorless
            )
            self.assertIn(
                'FORCE_MOVE STEPPER=stepper_z DISTANCE={printer["gcode_macro PRINTER_PARAM"].z_safe_g28} VELOCITY=10',
                sensorless,
            )
            self.assertIn(
                "'probe_eddy_current btt_eddy' not in printer.configfile.settings",
                sensorless,
            )
            self.assertIn(
                "EDDY_PREHOME_CLEAR MAX_TRAVEL=2.000", sensorless
            )
            self.assertGreaterEqual(sensorless.count("_HOME_Y"), 2)
            self.assertGreaterEqual(sensorless.count("_HOME_X"), 2)

            self.assertEqual(
                section_core(sensorless, "[gcode_macro _IF_HOME_Z]"),
                fixture("validated_if_home_z.cfg"),
            )
            self.assertEqual(
                section_core(sensorless, "[gcode_macro _HOME_Z]"),
                fixture("validated_home_z.cfg"),
            )
            self.assertEqual(
                pre_xy_block(sensorless),
                fixture("validated_pre_xy_block.txt"),
            )
            for header, before in preserved_sections.items():
                self.assertEqual(
                    section_core(sensorless, header),
                    before,
                    "activation changed untouched section %s" % header,
                )
            self.assertEqual(
                homing_override_without_pre_xy(sensorless),
                preserved_homing_override,
                "activation changed homing_override outside pre-XY safety block",
            )

            status = self.run_helper(root, "status").stdout
            self.assertIn("Pre-XY Eddy check:     present", status)
            self.assertIn("Bounded unknown-Z move: present", status)
            self.assertIn("Pre-Z Eddy clearance:  present", status)
            self.assertIn("Unsafe off-bed guard:  ABSENT (good)", status)
            self.assertIn("Production safety:     PASS", status)
            self.assertIn(
                "Production file hash:  different (section contract still applies)",
                status,
            )

            self.run_helper(
                root, "configure-wipe",
                "--start-x", "70.5", "--start-y", "305.5",
                "--start-surface-z", "4.2",
                "--end-x", "90.5", "--end-y", "305.5",
                "--end-surface-z", "4.35",
                "--confirm-measured",
            )
            macros = (cfg / "eddy_nozzle_clear.cfg").read_text()
            self.assertIn("# K1MAX_CFS_EDDY_WIPE_CONFIGURED=1", macros)

            status = self.run_helper(root, "status").stdout
            self.assertIn("Native Eddy Z:         ACTIVE", status)
            self.assertIn("Fixed napkin wipe:     configured", status)

            backups = sorted(
                (root / "usr/data/k1max-cfs-eddy-backups").glob("*-pre-stage*")
            )
            self.assertEqual(len(backups), 1)
            self.run_helper(root, "rollback", str(backups[0]))

            restored = (cfg / "printer.cfg").read_text()
            self.assertIn(
                "endstop_pin: tmc2209_stepper_z:virtual_endstop", restored
            )
            self.assertIn("position_endstop: 0", restored)
            self.assertFalse((cfg / "btteddy_mcu.cfg").exists())

            restored_mcu = (
                root / "usr/share/klipper/klippy/mcu.py"
            ).read_text()
            self.assertIn("CREALITY_MCU_SENTINEL_MUST_SURVIVE", restored_mcu)
            self.assertNotIn("upgrade_mcu", restored_mcu)
            self.assertEqual(
                (
                    root / "usr/share/klipper/klippy/extras/bed_mesh.py"
                ).read_text(),
                "# stock creality bed mesh\n",
            )
            self.assertFalse(
                (
                    root / "usr/share/klipper/klippy/extras/"
                    "bed_mesh_creality.py"
                ).exists()
            )
            self.assertFalse(
                (root / "usr/share/klipper/klippy/upgrade/mcu.py").exists()
            )
            self.assertFalse(
                (
                    root / "usr/share/klipper/klippy/extras/upgrade/"
                    "probe_eddy_current.py"
                ).exists()
            )


if __name__ == "__main__":
    unittest.main()
