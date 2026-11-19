'''
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 '''

import glob
import io
import json
import os
import random
import re
import struct
import tarfile
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

MQTT_DATA_TOPIC = 'OUT/12345678/ANAMOLY_DETECTION/DataCollection/payload'

INTERVAL_SECONDS = int(os.getenv("INTERVAL_SECONDS", "10"))

META_FORMAT = 'HHHHHHHH'
META_SIZE = struct.calcsize(META_FORMAT)

SRC_APP_ID = 13
DEST_APP_ID = 27
CHANNEL_NUM = 1
MSG_TYPE_DATA = 1
APP_VER = 1
SUB_CATEGORY = 0

SAMPLE_DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "data_collection_mode")

# ---------------------------------------------------------------------------
# Synthetic tar generation constants
# ---------------------------------------------------------------------------

WIFISTATS_TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "tl1_wifistats_20260102_112647.txt"
)

VALID_BANDS = ["2G", "5G", "6G"]
VALID_LABELS = ["pass", "fail_to_connect", "client_disconnect", "data_stall", "beacon_stuck"]

TEST_SCENARIOS = [
    {"band": "2G", "test_label": "pass",              "test_name": "normal_traffic",  "clients": 5},
    {"band": "2G", "test_label": "fail_to_connect",   "test_name": "connect_failure", "clients": 0},
    {"band": "5G", "test_label": "pass",              "test_name": "normal_traffic",  "clients": 3},
    {"band": "5G", "test_label": "client_disconnect", "test_name": "client_drop",     "clients": 4},
    {"band": "6G", "test_label": "pass",              "test_name": "normal_traffic",  "clients": 2},
    {"band": "2G", "test_label": "data_stall",        "test_name": "throughput_drop", "clients": 6},
    {"band": "5G", "test_label": "beacon_stuck",      "test_name": "beacon_failure",  "clients": 3},
    {"band": "6G", "test_label": "fail_to_connect",   "test_name": "connect_failure", "clients": 0},
]


# ---------------------------------------------------------------------------
# Wifistats randomization helpers
# ---------------------------------------------------------------------------

def _randomize_wifistats_line(line: str) -> str:
    """Return *line* with all numeric stat values replaced by random numbers.

    Structural tokens (section headers, HTT_ TLV names, Chain Pair headers,
    empty lines, pure-equals separators) are returned unchanged.

    Substitution order (applied to the rest):
      1. Range format   e.g. "0-250 : 24902"   -> keep range label, randomize value
      2. Mbps format    e.g. "5.5 Mbps: 0"     -> keep Mbps label, randomize value
      3. NxN format     e.g. "996x2:0"          -> keep NxN label, randomize value
      4. Indexed format e.g. "3:9990"           -> keep index, randomize value
      5. Simple = val   e.g. "mac_id = 0"       -> keep lhs, randomize value

    Lines whose text contains 'rssi', 'dbm', 'evm', or 'pilot_evm' use
    values drawn from [-128, -20]; all others use [0, 100000].
    """
    stripped = line.rstrip('\n')
    trailing_nl = '\n' if line.endswith('\n') else ''

    # --- unchanged lines ---
    if re.match(r'^\s*===\s*WIFISTAT\s+\d+\s*===', stripped):
        return line
    if re.match(r'^\s*HTT_', stripped):
        return line
    if re.match(r'^\s*Chain\s+Pair\s+\d+\s+Stats', stripped, re.IGNORECASE):
        return line
    s = stripped.strip()
    if not s:
        return line
    if re.match(r'^=+$', s):
        return line

    # --- value range ---
    lower = stripped.lower()
    use_neg = any(kw in lower for kw in ('rssi', 'dbm', 'evm', 'pilot_evm'))

    def rv() -> str:
        return str(random.randint(-128, -20) if use_neg else random.randint(0, 100000))

    result = stripped

    # 1. range format: "0-250 : 24902"
    result = re.sub(
        r'(\d+-\d+\s*:\s*)(\d+)',
        lambda m: m.group(1) + rv(),
        result,
    )

    # 2. Mbps format: "5.5 Mbps: 0"
    result = re.sub(
        r'(\d+(?:\.\d+)?\s+Mbps:\s*)(\d+)',
        lambda m: m.group(1) + rv(),
        result,
    )

    # 3. NxN format: "996x2:0"
    result = re.sub(
        r'(\d+x\d+:\s*)(\d+)',
        lambda m: m.group(1) + rv(),
        result,
    )

    # 4. indexed format: "3:9990"  (negative lookbehind: not preceded by letter/digit/hyphen)
    result = re.sub(
        r'(?<![a-zA-Z\d-])(-?\d+):\s*(-?\d+)',
        lambda m: m.group(1) + ':' + rv(),
        result,
    )

    # 5. simple "= val" at end of line
    result = re.sub(
        r'(=\s*)(-?\d+)\s*$',
        lambda m: m.group(1) + rv(),
        result,
    )

    return result + trailing_nl


def generate_wifistats_content() -> str:
    """Read the wifistats template and return a randomized copy as a string."""
    if not os.path.exists(WIFISTATS_TEMPLATE_PATH):
        print(f"[simulator] Wifistats template not found: {WIFISTATS_TEMPLATE_PATH}")
        return ""
    with open(WIFISTATS_TEMPLATE_PATH, encoding="utf-8") as fh:
        lines = fh.readlines()
    return "".join(_randomize_wifistats_line(ln) for ln in lines)


def generate_simulated_tar(
    band: str,
    test_label: str,
    test_name: str,
    clients_per_band: int = 5,
) -> bytes:
    """Build a gzip-compressed tar in memory containing a randomized wifistats
    file and a matching JSON metadata file.

    Returns the raw tar bytes, or an empty bytes object on failure.
    """
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    # --- wifistats ---
    wifistats_text = generate_wifistats_content()
    if not wifistats_text:
        return b""
    wifistats_bytes = wifistats_text.encode("utf-8")

    # --- JSON metadata ---
    meta = {
        "timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "band": band,
        "test_label": test_label,
        "test_name": test_name,
        "clients_per_band": float(clients_per_band),
        "model_inference_label": test_label,
        "all_stats": [round(random.random(), 4) for _ in range(50)],
    }
    json_bytes = json.dumps(meta).encode("utf-8")

    # --- fd_logs ---
    fd_bytes = b"Dummy fd_logs content for anomaly detection.\n"

    # --- build tar in memory ---
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        # wifistats file
        wi = tarfile.TarInfo(name=f"tl1_wifistats_{ts}.txt")
        wi.size = len(wifistats_bytes)
        tf.addfile(wi, io.BytesIO(wifistats_bytes))
        # JSON file
        ji = tarfile.TarInfo(name=f"tl1_sample_{ts}.json")
        ji.size = len(json_bytes)
        tf.addfile(ji, io.BytesIO(json_bytes))
        # fd_logs file
        fi = tarfile.TarInfo(name=f"test_fd_logs_{ts}.txt")
        fi.size = len(fd_bytes)
        tf.addfile(fi, io.BytesIO(fd_bytes))

    return buf.getvalue()


# ---------------------------------------------------------------------------
# MQTT helpers
# ---------------------------------------------------------------------------

def _pack_header(
    body_bytes: bytes,
    *,
    src: int = SRC_APP_ID,
    dest: int = DEST_APP_ID,
    channel: int = CHANNEL_NUM,
    msg_type: int = MSG_TYPE_DATA,
    app_ver: int = APP_VER,
    msg_id: int = 0,
    subcat: int = SUB_CATEGORY,
) -> bytes:
    length = len(body_bytes) & 0xFFFF
    return struct.pack(META_FORMAT, src, dest, channel, msg_type, app_ver, msg_id, subcat, length)


def build_cloud_meta_data(
    service_name: str,
    read_files: bool = True,
    num_files: int = 1,
    file_path: str = "",
    file_size: int = 0,
) -> bytes:
    """Build cloud_meta_data structure for CIA."""
    name_bytes = service_name.encode("utf-8")[:32].ljust(32, b"\0")
    read_files_byte = struct.pack("?", read_files)
    num_files_byte = struct.pack("B", num_files)
    payload = name_bytes + read_files_byte + num_files_byte
    if read_files and num_files > 0:
        path_bytes = file_path.encode("utf-8") + b"\0"
        payload += path_bytes
        data_type = struct.pack("I", 2)  # BINARY = 2
        payload += data_type
        # V2: files_size array (uint32)
        payload += struct.pack("I", file_size)

    # V2 Trailer: headerLen (uint16) + headerVersion (uint16) + nextHeaderEnum (uint16)
    header_len = len(payload) + 6
    header_version = 2
    next_header_enum = 0
    payload += struct.pack("HHH", header_len, header_version, next_header_enum)

    return payload


# ---------------------------------------------------------------------------
# Simulator class
# ---------------------------------------------------------------------------

class DataCollectionSimulator:
    def __init__(self):
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.stop_event = threading.Event()
        # Keep sample tars as fallback (used only if generate_simulated_tar fails)
        self.sample_tars = []
        self._load_sample_tars()

    def _load_sample_tars(self):
        if os.path.exists(SAMPLE_DATA_DIR):
            self.sample_tars = sorted(glob.glob(os.path.join(SAMPLE_DATA_DIR, "*.tar")))
            print(f"Loaded {len(self.sample_tars)} sample tar files from {SAMPLE_DATA_DIR}")
        else:
            print(f"Sample data directory not found: {SAMPLE_DATA_DIR}")

    def _on_connect(self, client, userdata, flags, reasonCode, properties=None):
        print("AP Simulator (DataCollection) connected")

    def run(self):
        self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self.client.loop_start()

        scenario_index = 0
        tar_index = 0  # fallback index for pre-existing tars

        try:
            while not self.stop_event.is_set():
                # --- pick scenario and generate synthetic tar ---
                scenario = TEST_SCENARIOS[scenario_index % len(TEST_SCENARIOS)]
                scenario_index += 1

                tar_bytes = generate_simulated_tar(
                    band=scenario["band"],
                    test_label=scenario["test_label"],
                    test_name=scenario["test_name"],
                    clients_per_band=scenario["clients"],
                )

                # Fallback to pre-existing tar if generation failed
                if not tar_bytes:
                    if not self.sample_tars:
                        print("[simulator] No tar available (generation failed, no sample tars). Waiting...")
                        time.sleep(5)
                        continue
                    current_tar = self.sample_tars[tar_index % len(self.sample_tars)]
                    tar_index += 1
                    try:
                        with open(current_tar, "rb") as fh:
                            tar_bytes = fh.read()
                        print(f"[simulator] Fallback: using {os.path.basename(current_tar)}")
                    except Exception as e:
                        print(f"[simulator] Error reading fallback tar: {e}")
                        time.sleep(5)
                        continue

                try:
                    file_path = f"/tmp/simulated_{scenario['test_name']}.tar"
                    cloud_meta = build_cloud_meta_data(
                        "DataCollection",
                        file_path=file_path,
                        file_size=len(tar_bytes)
                    )
                    full_payload = cloud_meta + tar_bytes
                    header = _pack_header(full_payload, dest=27)
                    self.client.publish(MQTT_DATA_TOPIC, header + full_payload, qos=1)
                    print(
                        f"[simulator] Sent synthetic tar: band={scenario['band']} "
                        f"label={scenario['test_label']} name={scenario['test_name']} "
                        f"({len(tar_bytes)} bytes)"
                    )
                except Exception as e:
                    print(f"[simulator] Error sending tar: {e}")

                time.sleep(INTERVAL_SECONDS)

        except KeyboardInterrupt:
            print("Stopping...")
            self.stop_event.set()
            self.client.loop_stop()
            self.client.disconnect()


if __name__ == "__main__":
    sim = DataCollectionSimulator()
    sim.run()
