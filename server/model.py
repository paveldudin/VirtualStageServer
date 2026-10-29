# -*- coding: utf-8 -*-
from __future__ import print_function
import math
import tango

class StageModel(object):
    def __init__(self, cfg, logger=None):
        self.cfg = cfg
        self.logger = logger
        self.dev = {}

        for k, name in cfg.real.items():
            self.dev[k] = tango.DeviceProxy(name)

        self.pi = tango.DeviceProxy(cfg.pi_device) if cfg.pi_device else None

        self.last_dest = {
            "SAN": 0.0, "SAT": 0.0, "SAS": 0.0, "SAZ": 0.0,
            "SAFT": 0.0, "SAFN": 0.0, "SAFZ": 0.0,
        }

    def log(self, msg):
        if self.logger is not None:
            try:
                self.logger(msg)
            except Exception:
                pass

    def validate_startup(self):
        # Check all coarse devices and mandatory attributes
        for var in ("SN","ST","SZ","SRZ","SRN"):
            if var not in self.dev:
                raise RuntimeError("Missing real axis in config: %s" % var)
            try:
                self.dev[var].ping()
                self.dev[var].read_attribute("position")
            except Exception as e:
                raise RuntimeError("Real device %s failed startup validation: %s" % (var, e))

        # PI device is only required for fine virtual axes
        if self.pi is not None:
            try:
                self.pi.ping()
                for var in ("PIX","PIY","PIZ"):
                    attr = self.cfg.pi_attrs.get(var, "")
                    if not attr:
                        raise RuntimeError("Missing PI attribute mapping for %s" % var)
                    self.pi.read_attribute(attr)
            except Exception as e:
                raise RuntimeError("PI device failed startup validation: %s" % e)

    def read_pos(self, var):
        return float(self.dev[var].read_attribute("position").value)

    def write_pos(self, var, value):
        self.dev[var].write_attribute("position", float(value))

    def read_pi(self, var):
        if self.pi is None:
            raise RuntimeError("PI device not configured")
        attr_name = self.cfg.pi_attrs[var]
        return float(self.pi.read_attribute(attr_name).value)

    def read_deadband(self, var):
        try:
            return float(self.dev[var].read_attribute("deadband").value)
        except Exception:
            return 0.0

    def read_limit_switches(self, var):
        try:
            f = bool(self.dev[var].read_attribute("forwardLimitSwitch").value)
            b = bool(self.dev[var].read_attribute("backwardLimitSwitch").value)
            return f, b
        except Exception:
            return False, False

    def read_soft_limits(self, var):
        try:
            mn = float(self.dev[var].read_attribute("minPositionSoftwareLimit").value)
            mx = float(self.dev[var].read_attribute("maxPositionSoftwareLimit").value)
            return mn, mx
        except Exception:
            return None, None

    def alpha_rad(self):
        return math.radians(self.cfg.alpha_deg)

    def dsrz_rad(self):
        return math.radians(self.read_pos("SRZ") - self.cfg.srz0_deg)

    def dsrn_rad(self):
        return math.radians(self.read_pos("SRN") - self.cfg.srn0_deg)

    def real_to_virtual(self):
        sn = self.read_pos("SN")
        st = self.read_pos("ST")
        sz = self.read_pos("SZ")

        d = self.dsrz_rad()
        a = self.alpha_rad()
        c = math.cos(d)
        s = math.sin(d)

        sat = -sn * s + st * c
        san =  sn * c + st * s
        sas = -sn * math.cos(a) - st * math.sin(a)
        saz = sz
        return {"SAN": san, "SAT": sat, "SAS": sas, "SAZ": saz}

    def virtual_to_real(self, san, sat, sas, saz):
        d = self.dsrz_rad()
        a = self.alpha_rad()
        c = math.cos(d)
        s = math.sin(d)

        sn = san * c - sat * s - sas * math.cos(a)
        st = san * s + sat * c + sas * math.sin(a)
        sz = saz
        return {"SN": sn, "ST": st, "SZ": sz}

    def fine_virtual(self, san, sat, saz):
        pix = self.read_pi("PIX")
        piy = self.read_pi("PIY")
        piz = self.read_pi("PIZ")

        d = self.dsrn_rad()
        c = math.cos(d)
        s = math.sin(d)

        saft = sat * c - saz * s + pix
        safz = sat * s + saz * c - piy
        safn = san + piz
        return {"SAFT": saft, "SAFN": safn, "SAFZ": safz}

    def check_real_targets_within_soft_limits(self, targets):
        for var in ("SN", "ST", "SZ"):
            mn, mx = self.read_soft_limits(var)
            if mn is None or mx is None:
                continue
            v = float(targets[var])
            if v < mn or v > mx:
                return False, "%s target %.6f outside software limits [%.6f, %.6f]" % (var, v, mn, mx)
        return True, "OK"

    def at_limit_switch(self, virt_var):
        if virt_var in ("SAN","SAT"):
            vars_ = ("SN","ST","SRZ")
        elif virt_var == "SAS":
            vars_ = ("SN","ST")
        elif virt_var == "SAZ":
            vars_ = ("SZ",)
        else:
            vars_ = ()
        for rv in vars_:
            f, b = self.read_limit_switches(rv)
            if f or b:
                return True
        return False

    def deadband_virtual(self, virt_var):
        dsn = self.read_deadband("SN")
        dst = self.read_deadband("ST")
        dsz = self.read_deadband("SZ")
        dsrz_deg = self.read_deadband("SRZ")

        if virt_var in ("SAN","SAT"):
            sn = self.read_pos("SN")
            st = self.read_pos("ST")
            radius = math.sqrt(sn * sn + st * st)
            dsrz_rad = math.radians(dsrz_deg)
            return float(dsn + dst + radius * dsrz_rad)
        if virt_var == "SAS":
            return float(dsn + dst)
        if virt_var == "SAZ":
            return float(dsz)
        return 0.0
