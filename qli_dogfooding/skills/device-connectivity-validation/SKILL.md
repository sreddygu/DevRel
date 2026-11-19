# Device Connectivity Validation

Check reachability before remote QLI work without changing device networking.

1. Require a target host name or IP address.
2. Run `python src/qli_device_lifecycle_apps.py connectivity --host <host>`.
3. Use a caller-supplied port or timeout only when required.
4. Record endpoint, port, timeout, return code, and result.

Do not switch Wi-Fi, activate a static IP, or modify routes. Those actions are
separate state-changing workflows that require explicit approval and recovery
planning.
