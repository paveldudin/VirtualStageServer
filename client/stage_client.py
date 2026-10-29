# -*- coding: utf-8 -*-
from __future__ import print_function
import tango

AXES = ("san","sat","sas","saz","saft","safn","safz")

for axis in AXES:
    name = "i12-m-ex1/ex1/Vsample-mt_%s" % axis
    try:
        d = tango.DeviceProxy(name)
        print(name, "position =", d.read_attribute("position").value, "info =", d.read_attribute("info").value)
    except Exception as e:
        print(name, "FAILED:", e)
