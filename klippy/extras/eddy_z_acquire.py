# BTT Eddy pre-home safety helper for K1 Max + CFS.
#
# This is derived from the helper validated on the 2.3.5.33 test machine.
# Positive stepper_z FORCE_MOVE direction was physically verified to move
# the bed/nozzle geometry away from the Eddy trigger plane before this helper
# was enabled. Do not transplant this module to a different motion platform
# without validating that direction first.

import math


class EddyZAcquire:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object("gcode")
        self.probe_name = config.get(
            "probe", "probe_eddy_current btt_eddy"
        )
        self.gcode.register_command(
            "EDDY_HOME_STATUS",
            self.cmd_EDDY_HOME_STATUS,
            desc="Report Eddy Z homing threshold status"
        )
        self.gcode.register_command(
            "EDDY_PREHOME_CLEAR",
            self.cmd_EDDY_PREHOME_CLEAR,
            desc="Move Z away from bed until Eddy is safely clear"
        )

    def _sample_frequency(self, gcmd, probe, sample_target, timeout):
        reactor = self.printer.get_reactor()
        state = {
            "done": False,
            "stop": False,
            "freqs": [],
            "errors": 0,
            "overflows": 0,
        }

        def handle_batch(msg):
            if state["stop"]:
                return False
            if not isinstance(msg, dict):
                return True
            state["errors"] = msg.get("errors", state["errors"])
            state["overflows"] = msg.get(
                "overflows", state["overflows"]
            )
            data = msg.get("data", ())
            remaining = sample_target - len(state["freqs"])
            for sample in data[:remaining]:
                if len(sample) < 2:
                    continue
                try:
                    freq = float(sample[1])
                except (TypeError, ValueError):
                    continue
                if math.isfinite(freq):
                    state["freqs"].append(freq)
            if len(state["freqs"]) >= sample_target:
                state["done"] = True
                return False
            return True

        probe.add_client(handle_batch)
        deadline = reactor.monotonic() + timeout
        while not state["done"]:
            now = reactor.monotonic()
            if now >= deadline:
                break
            reactor.pause(min(now + 0.010, deadline))

        if not state["done"]:
            state["stop"] = True
            now = reactor.monotonic()
            reactor.pause(now + 0.250)

        if not state["freqs"]:
            raise gcmd.error(
                "EDDY_PREHOME_CLEAR: no valid Eddy samples received"
            )
        if state["errors"]:
            raise gcmd.error(
                "EDDY_PREHOME_CLEAR: Eddy errors=%s"
                % (state["errors"],)
            )
        if state["overflows"]:
            raise gcmd.error(
                "EDDY_PREHOME_CLEAR: Eddy overflows=%s"
                % (state["overflows"],)
            )
        return sum(state["freqs"]) / float(len(state["freqs"]))

    def _height_if_valid(self, calibration, freq):
        try:
            height = calibration.freq_to_height(freq)
        except self.printer.command_error:
            return None
        # EddyCalibration uses +/-99.9 as OUT_OF_RANGE.
        if height <= -99.9 or height >= 99.9:
            return None
        return height

    def cmd_EDDY_HOME_STATUS(self, gcmd):
        probe = self.printer.lookup_object(self.probe_name)
        calibration = probe.calibration
        z_offset = probe.get_offsets()[2]
        trigger_freq = calibration.height_to_freq(z_offset)
        samples = gcmd.get_int("SAMPLES", 250, minval=25, maxval=1000)
        timeout = gcmd.get_float("TIMEOUT", 3.0, above=0.0)
        freq = self._sample_frequency(
            gcmd, probe, samples, timeout
        )
        height = self._height_if_valid(calibration, freq)
        if height is None:
            height_text = "outside calibration range"
            delta_text = "not available"
        else:
            height_text = "%.6f mm" % height
            delta_text = "%+.6f mm" % (height - z_offset)
        state_text = (
            "TRIGGERED_SIDE" if freq >= trigger_freq else "CLEAR_SIDE"
        )
        gcmd.respond_info(
            "EDDY_HOME_STATUS:\n"
            "  current frequency: %.3f Hz\n"
            "  current calibrated height: %s\n"
            "  configured z_offset: %.6f mm\n"
            "  homing trigger frequency: %.3f Hz\n"
            "  frequency delta: %+.3f Hz\n"
            "  height delta: %s\n"
            "  state: %s"
            % (
                freq, height_text, z_offset, trigger_freq,
                freq - trigger_freq, delta_text, state_text
            )
        )

    def cmd_EDDY_PREHOME_CLEAR(self, gcmd):
        # The normal default remains deliberately small. The K1 Max
        # cold-start macro explicitly requests MARGIN=1 / MAX_TRAVEL=5.
        margin = gcmd.get_float(
            "MARGIN", 0.050, minval=0.025, maxval=1.000
        )
        step = gcmd.get_float(
            "STEP", 0.050, minval=0.010, maxval=0.050
        )
        max_travel = gcmd.get_float(
            "MAX_TRAVEL", 0.250, minval=0.050, maxval=5.000
        )
        speed = gcmd.get_float(
            "VELOCITY", 1.0, above=0.0, maxval=2.0
        )
        sample_target = gcmd.get_int(
            "SAMPLES", 250, minval=50, maxval=500
        )
        timeout = gcmd.get_float("TIMEOUT", 2.0, above=0.0)
        settle = gcmd.get_float(
            "SETTLE", 1.0, minval=0.25, maxval=3.0
        )

        probe = self.printer.lookup_object(self.probe_name)
        calibration = probe.calibration
        z_offset = probe.get_offsets()[2]
        target_height = z_offset + margin
        trigger_freq = calibration.height_to_freq(z_offset)
        target_freq = calibration.height_to_freq(target_height)

        force_move = self.printer.lookup_object("force_move")
        stepper = force_move.lookup_stepper("stepper_z")
        reactor = self.printer.get_reactor()

        def sample_eddy():
            return self._sample_frequency(
                gcmd, probe, sample_target, timeout
            )

        current_freq = sample_eddy()
        current_height = self._height_if_valid(
            calibration, current_freq
        )
        if current_freq <= target_freq:
            gcmd.respond_info(
                "EDDY_PREHOME_CLEAR: already safely CLEAR\n"
                "  current frequency: %.3f Hz\n"
                "  current height: %s\n"
                "  target frequency: %.3f Hz\n"
                "  target height: %.6f mm\n"
                "  movement: NONE"
                % (
                    current_freq,
                    (
                        "outside calibration range"
                        if current_height is None
                        else "%.6f mm" % current_height
                    ),
                    target_freq,
                    target_height,
                )
            )
            return

        gcmd.respond_info(
            "EDDY_PREHOME_CLEAR: starting\n"
            "  current frequency: %.3f Hz\n"
            "  trigger frequency: %.3f Hz\n"
            "  z_offset: %.6f mm\n"
            "  target frequency: %.3f Hz\n"
            "  target height: %.6f mm\n"
            "  step: %.6f mm\n"
            "  max travel: %.6f mm"
            % (
                current_freq, trigger_freq, z_offset, target_freq,
                target_height, step, max_travel
            )
        )

        total_moved = 0.0
        move_count = 0
        start_freq = current_freq
        previous_freq = current_freq

        # The validated K1 Max orientation uses positive direct stepper_z
        # movement to increase Eddy clearance. Each move is intentionally
        # tiny and is followed by a new sensor measurement.
        force_move._force_enable(stepper)

        while current_freq > target_freq:
            remaining = max_travel - total_moved
            if remaining < 0.009999:
                raise gcmd.error(
                    "EDDY_PREHOME_CLEAR: maximum safe travel "
                    "reached before clearance"
                )
            move_distance = min(step, remaining)
            force_move.manual_move(
                stepper, move_distance, speed, 0.0
            )
            total_moved += move_distance
            move_count += 1

            now = reactor.monotonic()
            reactor.pause(now + settle)
            current_freq = sample_eddy()
            freq_change = current_freq - previous_freq

            gcmd.respond_info(
                "EDDY_PREHOME_CLEAR: sample %d\n"
                "  frequency: %.3f Hz\n"
                "  frequency change: %+.3f Hz\n"
                "  total +Z movement: %.6f mm"
                % (
                    move_count, current_freq, freq_change, total_moved
                )
            )

            # Moving in the validated away direction should lower Eddy
            # frequency. Confirm a meaningful increase before aborting,
            # allowing a small first-move backlash/take-up effect.
            if freq_change > 40.0:
                now = reactor.monotonic()
                reactor.pause(now + settle)
                confirm_freq = sample_eddy()
                confirm_change = confirm_freq - previous_freq
                current_freq = confirm_freq
                freq_change = confirm_change
                if freq_change > 40.0:
                    raise gcmd.error(
                        "EDDY_PREHOME_CLEAR: ABORT - "
                        "confirmed +Z frequency increase"
                    )

            # After 0.075 mm, require evidence that the sensor is moving
            # away from the bed. This catches reversed mechanics or a
            # non-responsive Eddy before large recovery travel occurs.
            if (
                total_moved >= 0.075
                and current_freq > start_freq - 40.0
            ):
                raise gcmd.error(
                    "EDDY_PREHOME_CLEAR: ABORT - "
                    "no meaningful cumulative Eddy response after "
                    "%.6f mm +Z travel" % total_moved
                )

            previous_freq = current_freq

        final_height = self._height_if_valid(
            calibration, current_freq
        )
        gcmd.respond_info(
            "EDDY_PREHOME_CLEAR: CLEAR\n"
            "  final frequency: %.3f Hz\n"
            "  final calibrated height: %s\n"
            "  target height: %.6f mm\n"
            "  total +Z movement: %.6f mm\n"
            "  moves: %d\n"
            "  READY FOR Z HOMING"
            % (
                current_freq,
                (
                    "outside calibration range"
                    if final_height is None
                    else "%.6f mm" % final_height
                ),
                target_height, total_moved, move_count
            )
        )


def load_config(config):
    return EddyZAcquire(config)
