# -*- coding: utf-8 -*-
from __future__ import print_function
import traceback
import tango
from tango import DevState, DevFailed
from tango.server import Device, attribute, device_property, command, run

from server.config import Config
from server.model import StageModel

_MODELS = {}

def _log_stderr(msg):
    print("[virtual_stage_v2.4] %s" % msg)

def get_model(cfgfile):
    m = _MODELS.get(cfgfile)
    if m is None:
        cfg = Config(cfgfile)
        m = StageModel(cfg, logger=_log_stderr)
        m.validate_startup()
        _MODELS[cfgfile] = m
    return m

class VirtualAxis(Device):
    AxisRole   = device_property(dtype=str)
    ConfigFile = device_property(dtype=str)

    position = attribute(dtype=float, unit="mm", format="%6.3f",
                         fget="get_position", fset="set_position",
                         doc="Axis position (user)")

    offset = attribute(dtype=float, unit="mm", format="%6.3f",
                       display_level=tango.DispLevel.EXPERT,
                       fget="get_offset", fset="set_offset",
                       doc="Axis offset (expert)")

    checkUserInput = attribute(dtype=bool, format="%s",
                               fget="get_checkUserInput", fset="set_checkUserInput",
                               doc="Enable check of user input limits")

    minInputLimit = attribute(dtype=float, unit="mm", format="%6.3f",
                              fget="get_minInputLimit", fset="set_minInputLimit",
                              doc="Min allowed user input")

    maxInputLimit = attribute(dtype=float, unit="mm", format="%6.3f",
                              fget="get_maxInputLimit", fset="set_maxInputLimit",
                              doc="Max allowed user input")

    atLimitSwitch = attribute(dtype=bool, format="%s",
                              fget="get_atLimitSwitch",
                              doc="True if related real limit switch active")

    deadband = attribute(dtype=float, unit="mm", format="%6.6f",
                         fget="get_deadband",
                         doc="Computed deadband")

    lastValue = attribute(dtype=float, unit="mm", format="%6.3f",
                          fget="get_lastValue", fset="set_lastValue",
                          doc="Last destination (user)")

    info = attribute(dtype=str, format="%s", fget="get_info",
                     doc="Debug/status information")

    dryRun = attribute(dtype=bool, display_level=tango.DispLevel.EXPERT,
                       fget="get_dryRun", fset="set_dryRun",
                       doc="True: validate and print targets, never move motors")
    lastMoveReport = attribute(dtype=str, fget="get_lastMoveReport",
                               doc="Last movement request and validation result")
    lastMoveValid = attribute(dtype=bool, fget="get_lastMoveValid",
                              doc="Whether the last requested move passed validation")

    def get_dryRun(self):
        return self._dry_run

    def set_dryRun(self, value):
        self._dry_run = bool(value)
        _log_stderr("%s dryRun=%s" % (self.AxisRole, self._dry_run))

    def get_lastMoveReport(self):
        return self._move_report

    def get_lastMoveValid(self):
        return self._move_valid

    def init_device(self):
        Device.init_device(self)
        self._failed = False
        self._last_error = ""
        self._last = 0.0
        self._dry_run = True
        self._move_valid = False
        self._move_report = "No move requested"

        if not self.ConfigFile:
            raise DevFailed("ConfigFile property must be set")
        if not self.AxisRole:
            raise DevFailed("AxisRole property must be set")

        self.model = get_model(self.ConfigFile)
        self.cfg = self.model.cfg

        lohi = self.cfg.input_limits.get(self.AxisRole, (0.0, 0.0))
        self._min_in = float(lohi[0])
        self._max_in = float(lohi[1])
        self._check = True
        self._offset = float(self.cfg.get_offset(self.AxisRole))

        self.set_state(DevState.STANDBY)

    def _set_error(self, msg):
        self._failed = True
        self._last_error = str(msg)
        self.set_state(DevState.FAULT)
        _log_stderr("%s (%s): %s" % (self.get_name(), self.AxisRole, msg))

    def _raise_tango_error(self, where, exc):
        tb = traceback.format_exc()
        msg = "%s failed for %s: %s" % (where, self.AxisRole, exc)
        self._set_error(msg)
        _log_stderr(tb)
        tango.Except.throw_exception("VirtualStageError", msg, "VirtualAxis.%s" % where)

    def is_fine_axis(self):
        return self.AxisRole in ("SAFT", "SAFN", "SAFZ")

    def involved_real_axes(self):
        if self.AxisRole in ("SAN","SAT","SAS"):
            return ("SN","ST","SRZ")
        if self.AxisRole == "SAZ":
            return ("SZ",)
        if self.AxisRole in ("SAFT","SAFN","SAFZ"):
            return ("SN","ST","SZ","SRZ","SRN")
        return ()

    def update_state_from_real(self):
        if self._failed:
            self.set_state(DevState.FAULT)
            return

        states = []
        for rv in self.involved_real_axes():
            try:
                states.append(self.model.dev[rv].state())
            except Exception as e:
                self._set_error("state read failed on %s: %s" % (rv, e))
                return

        if any(s == DevState.MOVING for s in states):
            self.set_state(DevState.MOVING)
        elif any(s == DevState.FAULT for s in states):
            self.set_state(DevState.FAULT)
        elif any(s == DevState.ALARM for s in states):
            self.set_state(DevState.ALARM)
        elif all(s in (DevState.ON, DevState.STANDBY, DevState.RUNNING) for s in states):
            self.set_state(DevState.STANDBY)
        else:
            self.set_state(DevState.ON)

    def get_offset(self):
        return float(self._offset)

    def set_offset(self, value):
        try:
            v = float(value)
            self._offset = v
            self.cfg.set_offset(self.AxisRole, v)
        except Exception as e:
            self._raise_tango_error("set_offset", e)

    def get_position(self):
        try:
            self.update_state_from_real()
            v = self.model.real_to_virtual()
            san = v["SAN"]; sat = v["SAT"]; sas = v["SAS"]; saz = v["SAZ"]

            if self.AxisRole == "SAN":
                return san + self._offset
            if self.AxisRole == "SAT":
                return sat + self._offset
            if self.AxisRole == "SAS":
                return sas + self._offset
            if self.AxisRole == "SAZ":
                return saz + self._offset

            fine = self.model.fine_virtual(san, sat, saz)
            if self.AxisRole == "SAFT":
                return fine["SAFT"] + self._offset
            if self.AxisRole == "SAFN":
                return fine["SAFN"] + self._offset
            if self.AxisRole == "SAFZ":
                return fine["SAFZ"] + self._offset

            return 0.0 + self._offset
        except DevFailed:
            raise
        except Exception as e:
            self._raise_tango_error("get_position", e)

    def set_position(self, value):
        lines = ["[%s] axis=%s" % ("DRY RUN" if self._dry_run else "LIVE", self.AxisRole)]
        self._move_valid = False
        try:
            user_v = float(value)
            lines.append("Requested virtual position: %.6f" % user_v)
            if self.is_fine_axis():
                raise RuntimeError("Fine axis is read-only")
            if self.AxisRole not in ("SAN", "SAT", "SAS", "SAZ"):
                raise RuntimeError("Unknown axis role: %s" % self.AxisRole)
            if self._check and (user_v < self._min_in or user_v > self._max_in):
                raise RuntimeError("User input %.6f outside limits [%.6f, %.6f]" %
                                   (user_v, self._min_in, self._max_in))

            cur = self.model.real_to_virtual()
            cur[self.AxisRole] = user_v - self._offset
            targets = self.model.virtual_to_real(cur["SAN"], cur["SAT"], cur["SAS"], cur["SAZ"])
            for motor in ("SN", "ST", "SZ"):
                lines.append("Target %s = %.6f" % (motor, targets[motor]))

            # Fail closed: unreadable or invalid real limits are NOT treated as safe.
            for motor in ("SN", "ST", "SZ"):
                dev = self.model.dev[motor]
                low = float(dev.read_attribute("minPositionSoftwareLimit").value)
                high = float(dev.read_attribute("maxPositionSoftwareLimit").value)
                import math
                if not (math.isfinite(low) and math.isfinite(high) and low <= high):
                    raise RuntimeError("Invalid software limits on %s: [%s, %s]" % (motor, low, high))
                lines.append("Limits %s = [%.6f, %.6f]" % (motor, low, high))
                if not low <= targets[motor] <= high:
                    raise RuntimeError("%s target %.6f outside software limits [%.6f, %.6f]" %
                                       (motor, targets[motor], low, high))

            self._move_valid = True
            self._last = user_v
            self.model.last_dest[self.AxisRole] = user_v
            if self._dry_run:
                lines.append("ACCEPTED - simulation only; NO motors moved")
                self._move_report = "\n".join(lines)
                _log_stderr(self._move_report)
                return

            # Live mode retains v2.3 motion sequence.
            self.model.write_pos("SN", targets["SN"])
            self.model.write_pos("ST", targets["ST"])
            self.model.write_pos("SZ", targets["SZ"])
            lines.append("Live motor writes submitted")
            self._failed = False
            self._last_error = ""
            self.set_state(DevState.MOVING)
            self._move_report = "\n".join(lines)
            _log_stderr(self._move_report)
        except Exception as exc:
            lines.append("REJECTED/FAILED: %s" % exc)
            lines.append("No movement requested" if self._dry_run else
                         "Live mode: check whether any motor write was already submitted")
            self._move_report = "\n".join(lines)
            _log_stderr(self._move_report)
            self._raise_tango_error("set_position", exc)

    def get_checkUserInput(self):
        return bool(self._check)

    def set_checkUserInput(self, v):
        self._check = bool(v)

    def get_minInputLimit(self):
        return float(self._min_in)

    def set_minInputLimit(self, v):
        self._min_in = float(v)

    def get_maxInputLimit(self):
        return float(self._max_in)

    def set_maxInputLimit(self, v):
        self._max_in = float(v)

    def get_atLimitSwitch(self):
        try:
            return bool(self.model.at_limit_switch(self.AxisRole))
        except Exception as e:
            self._raise_tango_error("get_atLimitSwitch", e)

    def get_deadband(self):
        try:
            return float(self.model.deadband_virtual(self.AxisRole))
        except Exception as e:
            self._raise_tango_error("get_deadband", e)

    def get_lastValue(self):
        if self.AxisRole in self.model.last_dest:
            return float(self.model.last_dest[self.AxisRole])
        return float(self._last)

    def set_lastValue(self, v):
        self._last = float(v)
        if self.AxisRole in self.model.last_dest:
            self.model.last_dest[self.AxisRole] = float(v)

    def get_info(self):
        if self._last_error:
            return self._last_error
        return "OK"

    @command
    def STOP(self):
        if self._dry_run:
            _log_stderr("[DRY RUN] STOP for %s: no hardware command sent" % self.AxisRole)
            return
        for rv in self.involved_real_axes():
            try:
                self.model.dev[rv].command_inout("Stop")
            except Exception:
                try:
                    self.model.dev[rv].command_inout("STOP")
                except Exception:
                    pass
        self.set_state(DevState.STANDBY)

    def always_executed_hook(self):
        try:
            self.update_state_from_real()
        except DevFailed:
            raise
        except Exception as e:
            self._raise_tango_error("always_executed_hook", e)

def main(args=None):
    run((VirtualAxis,), args=args)

if __name__ == "__main__":
    main()
