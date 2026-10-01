import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "k1max_cfs_eddy.py"


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
variable_z_moved: 0
gcode:

[gcode_macro _IF_HOME_Z]
gcode:
  FORCE_MOVE STEPPER=stepper_z DISTANCE=2 VELOCITY=10

[gcode_macro _HOME_Z]
gcode:
  G28 Z

[homing_override]
axes: xyz
gcode:
  _HOME_Y
  _HOME_Y
  _HOME_X
  _HOME_X
  _HOME_Z
""")
        write(root, "/usr/data/printer_data/config/gcode_macro.cfg", """[gcode_macro ACCURATE_G28]
gcode:
  ACCURATE_HOME_Z
""")
        write(root, "/usr/data/printer_data/config/box.cfg", "[box]\n")
        write(root, "/usr/share/klipper/klippy/extras/bed_mesh.py", "# stock creality bed mesh\n")
        write(root, "/dev/serial/by-id/usb-Klipper_rp2040_TEST-if00", "")

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
            self.run_helper(root, "activate")

            printer = (cfg / "printer.cfg").read_text()
            sensorless = (cfg / "sensorless.cfg").read_text()
            self.assertIn("endstop_pin: probe:z_virtual_endstop", printer)
            self.assertNotIn("position_endstop:", printer)
            self.assertIn(
                "EDDY_PREHOME_CLEAR MARGIN=1.000 MAX_TRAVEL=5.000",
                sensorless,
            )
            self.assertIn(
                "EDDY_PREHOME_CLEAR MAX_TRAVEL=2.000", sensorless
            )
            self.assertGreaterEqual(sensorless.count("_HOME_Y"), 2)
            self.assertGreaterEqual(sensorless.count("_HOME_X"), 2)

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
