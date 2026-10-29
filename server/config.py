# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import tempfile
import xml.etree.ElementTree as ET

class Config(object):
    def __init__(self, path):
        self.path = path
        root = ET.parse(path).getroot()

        g = root.find("geometry")
        self.alpha_deg = float(g.findtext("alpha_degrees") or "0.0")
        self.srz0_deg = float(g.findtext("srz0_degrees") or "0.0")
        self.srn0_deg = float(g.findtext("srn0_degrees") or "120.0")

        self.real = {}
        for ax in root.findall("./real_axes/coarse/axis"):
            self.real[ax.get("var")] = ax.get("tango")

        self.pi_device = root.findtext("./real_axes/fine/tango_parser_device") or ""

        self.pi_attrs = {}
        for ax in root.findall("./real_axes/fine/axis"):
            self.pi_attrs[ax.get("var")] = ax.get("input_name")

        self.input_limits = {}
        for il in root.findall("./defaults/input_limits"):
            self.input_limits[il.get("var")] = (
                float(il.get("min") or "0.0"),
                float(il.get("max") or "0.0"),
            )

        self.offsets = {}
        for off in root.findall("./offsets/offset"):
            try:
                self.offsets[off.get("var")] = float((off.text or "").strip() or "0.0")
            except Exception:
                self.offsets[off.get("var")] = 0.0

        for v in ("SAN","SAT","SAS","SAZ","SAFT","SAFN","SAFZ"):
            if v not in self.offsets:
                self.offsets[v] = 0.0

    def get_offset(self, var):
        return float(self.offsets.get(var, 0.0))

    def set_offset(self, var, value):
        value = float(value)
        self.offsets[var] = value

        tree = ET.parse(self.path)
        root = tree.getroot()
        offs = root.find("offsets")
        if offs is None:
            offs = ET.SubElement(root, "offsets")

        node = root.find("./offsets/offset[@var='%s']" % var)
        if node is None:
            node = ET.SubElement(offs, "offset")
            node.set("var", var)
        node.text = "%.12g" % value

        d = os.path.dirname(os.path.abspath(self.path)) or "."
        fd, tmp = tempfile.mkstemp(prefix="cfg_", suffix=".xml", dir=d)
        try:
            with os.fdopen(fd, "wb") as f:
                tree.write(f, encoding="utf-8", xml_declaration=True)
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise
