"""Per-OS hardware probes.

Each module exposes a ``probe()`` function returning a dict with the
fields ``hardware.detect_hardware`` needs to fill the DeviceProfile
envelope. Missing fields are returned as typed empties (0, "", []) so
the dispatcher in ``hardware.py`` can fill the rest from lookup tables
or SDK probes without worrying about None checks.
"""
