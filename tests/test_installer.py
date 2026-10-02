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

            self.run_helper(
                root, "stage", "--x-offset", "-23", "--y-offset", "0"
            )
            sensorless = (
                root / "usr/data/printer_data/config/sensorless.cfg"
            ).read_text()

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
            self.assertEqual(
                section_core(sensorless, "[gcode_macro _IF_HOME_Z]"),
                fixture("validated_if_home_z.cfg"),
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


if __name__ == "__main__":
    unittest.main()
