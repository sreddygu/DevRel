"""
UNOQ wakeword -> RPC helper.

Purpose
-------
Call the UNOQ MCU RPC method `flash_heart`. This is used by
`kws_keyword_beep_onnx.py --rpc-flash-heart-on-detect`.

Required (UNOQ)
--------------
- Curriculum RPC client present at: `~/kws/qa-intermediate-curriculum/rpc/`
- Python venv at: `~/kws/.venv` with `msgpack` installed

Commands (UNOQ)
--------------
    cd ~/kws
    . .venv/bin/activate
    python qa-intermediate-curriculum/rpc/MPU/unoq_rpc_wakeword.py --repeat 1
"""

import argparse
import sys
import time
from pathlib import Path


def _import_bridge() -> type:
    rpc_dir = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(rpc_dir))
    try:
        from rpc_base import ArduinoBridge  # type: ignore

        return ArduinoBridge
    finally:
        try:
            sys.path.remove(str(rpc_dir))
        except ValueError:
            pass


def flash_heart_once(timeout_s: float = 5.0) -> None:
    ArduinoBridge = _import_bridge()
    bridge = ArduinoBridge()
    try:
        bridge.call("flash_heart", timeout=timeout_s)
    finally:
        bridge.close()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Wakeword -> RPC helper (UNOQ).")
    p.add_argument("--repeat", type=int, default=1, help="Number of times to call flash_heart.")
    p.add_argument("--sleep-s", type=float, default=0.0, help="Sleep between repeats.")
    p.add_argument("--timeout-s", type=float, default=5.0, help="RPC call timeout.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    for i in range(int(args.repeat)):
        print(f"flash_heart[{i}]")
        flash_heart_once(timeout_s=float(args.timeout_s))
        if float(args.sleep_s) > 0 and i + 1 < int(args.repeat):
            time.sleep(float(args.sleep_s))


if __name__ == "__main__":
    main()
