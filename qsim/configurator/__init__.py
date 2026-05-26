"""qsim configurator — the reference-design configurator (headless core).

This is the answer to "can a user design their own device, or only print a fixed BOM?".
It is NOT a schematic-capture tool (reinventing KiCad would be pointless) and NOT a fixed
catalog. It is the middle ground: a high-level `DeviceSpec` of physically-meaningful knobs
(detector type, gate rate, channels, distance, ...) that drives BOTH

  * the BEHAVIOURAL simulation (qsim -> QBER / secret-key rate), and
  * the reference HARDWARE design (BOM assembly + derived board parameters),

consistently, with design-rule checks tying them together. Turn one knob and the predicted
performance, the parts list, and the board parameters all update together — and illegal
combinations are flagged. The DeviceSpec is shareable data (YAML), so this is the headless
core a drag-and-drop GUI will later sit on top of (the "virtual quantum bench").

The detailed circuit (schematic/SPICE/PCB) stays in the expert reference design (docs/03,
hardware/) and KiCad; the configurator selects and parametrises it, it does not redraw it.
"""
from .spec import DeviceSpec
from .compile import configure, ConfigReport

__all__ = ["DeviceSpec", "configure", "ConfigReport"]
