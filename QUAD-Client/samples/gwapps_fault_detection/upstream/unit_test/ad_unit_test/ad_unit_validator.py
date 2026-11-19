'''
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 '''

import csv
import glob
import json
import os
import struct
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Incoming from CIA (responses/broadcasts)
MQTT_AP_RESPONSE_TOPIC = 'OUT/+/ANAMOLY_DETECTION/UnitTest/payload'
# Outgoing to AP (validation requests & control commands bypass CIA)
MQTT_AP_SEND_TOPIC = 'ANAMOLY_DETECTION:/ANAMOLY_DETECTION:/:INPUT_PARAMS'

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")
AP_RESPONSE_TIMEOUT_SEC = 5.0
CYCLE_SLEEP_SEC = 2.0
VALIDATION_CYCLES = int(os.getenv("VALIDATION_CYCLES", "1"))

META_FORMAT = 'HHHHHHHHHHH'
META_SIZE = struct.calcsize(META_FORMAT)

REQUIRED_STATS = [
    'Control_Stats/Rx_Management','Control_Stats/Tx_Management',
    'cmd_result/mac_id_0_hwq_id_0_type_0','cmd_result/mac_id_0_hwq_id_0_type_1',
    'cmd_result/mac_id_0_hwq_id_0_type_2','cmd_result/mac_id_0_hwq_id_0_type_3',
    'cmd_result/mac_id_0_hwq_id_0_type_4','cmd_result/mac_id_0_hwq_id_0_type_5',
    'cmd_result/mac_id_0_hwq_id_0_type_6','cmd_result/mac_id_0_hwq_id_0_type_7',
    'cmd_result/mac_id_0_hwq_id_0_type_8','cmd_result/mac_id_0_hwq_id_0_type_9',
    'cmd_result/mac_id_0_hwq_id_0_type_10','cmd_result/mac_id_0_hwq_id_0_type_11',
    'cmd_result/mac_id_0_hwq_id_0_type_12',
    'cmd_result/mac_id_0_hwq_id_4_type_0','cmd_result/mac_id_0_hwq_id_4_type_1',
    'cmd_result/mac_id_0_hwq_id_4_type_2','cmd_result/mac_id_0_hwq_id_4_type_3',
    'cmd_result/mac_id_0_hwq_id_4_type_4','cmd_result/mac_id_0_hwq_id_4_type_5',
    'cmd_result/mac_id_0_hwq_id_4_type_6','cmd_result/mac_id_0_hwq_id_4_type_7',
    'cmd_result/mac_id_0_hwq_id_4_type_8','cmd_result/mac_id_0_hwq_id_4_type_9',
    'cmd_result/mac_id_0_hwq_id_4_type_10','cmd_result/mac_id_0_hwq_id_4_type_11',
    'cmd_result/mac_id_0_hwq_id_4_type_12',
    'ppdu_ok','tx_xretry',
    'fw_rx_mgmt_subtype/type_0','fw_rx_mgmt_subtype/type_2',
    'fw_rx_mgmt_subtype/type_4','fw_rx_mgmt_subtype/type_11',
    'fw_rx_mgmt_subtype/type_12',
    'fw_tx_mgmt_subtype/tx_mgmt_1','fw_tx_mgmt_subtype/tx_mgmt_3',
    'fw_tx_mgmt_subtype/tx_mgmt_5','fw_tx_mgmt_subtype/tx_mgmt_10',
    'fw_tx_mgmt_subtype/tx_mgmt_11','fw_tx_mgmt_subtype/tx_mgmt_12',
    'm1_packets','m3_packets','m1_success','m3_success',
    'Control_Stats/Total_Number_of_connected_clients',
    'rssi_mgmt','rssi_data','rssi_comb','rssi_in_dbm'
]

def _pack_meta_header_for_live(body: bytes) -> bytes:
    src = 27
    dst = 13
    channel = 1
    msg_type = 2
    version = 3
    app_msg_id = 6
    subcat = 0
    length = len(body) & 0xFFFF
    header_len = META_SIZE
    header_version = 2
    next_header_enum = 0
    return struct.pack(META_FORMAT, src, dst, channel, msg_type, version, app_msg_id, subcat, length, header_len, header_version, next_header_enum)

# To parse cloud_meta_data length dynamically matching the C logic
def parse_cloud_meta(payload_bytes):
    try:
        offset = 0
        service_name = payload_bytes[offset:offset+32].decode('utf-8', errors='ignore').strip('\x00')
        offset += 32
        read_files = struct.unpack('?', payload_bytes[offset:offset+1])[0]
        offset += 1
        num_files = struct.unpack('B', payload_bytes[offset:offset+1])[0]
        offset += 1

        if read_files and num_files > 0:
            for i in range(num_files):
                null_idx = payload_bytes.find(b'\x00', offset)
                if null_idx == -1:
                    return None
                offset = null_idx + 1
            offset += num_files * 4
            offset += num_files * 4

        offset += 6

        return {'service_name': service_name, 'read_files': read_files, 'num_files': num_files, 'payload_offset': offset}
    except Exception as e:
        print(f"Error parsing cloud meta: {e}")
        return None


_AP_RESPONSES = {}
_RESP_LOCK = threading.Lock()
RESP_READY = threading.Event()
PUB_READY = threading.Event()
TEST_LEVEL_BROADCAST_READY = threading.Event()

def _ensure_dir(path: str):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)

def _decode_ap_payload(raw: bytes):
    if raw is None:
        return None, b''
    if len(raw) >= 16:
        try:
            fields = struct.unpack('HHHHHHHH', raw[:16])
            version = fields[4]
            if version >= 3 and len(raw) >= 22:
                meta = struct.unpack('HHHHHHHHHHH', raw[:22])
                header_len = meta[8]
                if 16 <= header_len <= len(raw):
                    return meta, raw[header_len:]
                else:
                    return meta, raw[22:]
            else:
                if len(raw) >= 22:
                    meta = struct.unpack('HHHHHHHHHHH', raw[:22])
                    return meta, raw[22:]
                else:
                    return fields, raw[16:]
        except Exception:
            return None, raw
    return None, raw

def _send_stop_broadcast(client):
    print("Sending Stop Broadcast command to AP...")
    cmd = {
        "control": "STOP_BROADCAST",
        "TEST_LEVEL": "2"
    }
    body = json.dumps(cmd).encode("utf-8")
    header = _pack_meta_header_for_live(body)
    client.publish(MQTT_AP_SEND_TOPIC, header + body, qos=1)

def _start_response_listener(pub_client):
    """
    Listen for AP responses/control on CIA topic and store them in _AP_RESPONSES by message_id.
    Signals RESP_READY when subscribed.
    - Waits for TEST_LEVEL_BROADCAST with TEST_LEVEL=2.
    - Sends STOP_BROADCAST automatically once detected.
    """
    def on_connect(client, userdata, flags, reasonCode, properties=None):
        if reasonCode == 0:
            print("Response listener connected to MQTT broker")
            client.subscribe(MQTT_AP_RESPONSE_TOPIC, qos=1)
            RESP_READY.set()
        else:
            print(f"Failed to connect to MQTT broker: reasonCode={reasonCode}")

    def on_message(client, userdata, msg):
        try:
            _, body = _decode_ap_payload(msg.payload)
            if len(body) > 32 and body.startswith(b"UnitTest"):
                meta = parse_cloud_meta(body)
                if meta:
                    offset = meta.get('payload_offset', 0)
                    json_bytes = body[offset:]
                    try:
                        payload = json.loads(json_bytes.decode('utf-8', errors='replace'))
                    except json.JSONDecodeError:
                        return

                    msg_type = (payload.get("message_type") or payload.get("control") or "").strip().upper()
                    tl = str(payload.get("TEST_LEVEL", "")).strip()

                    # Handle Orchestrator Logic: wait for broadcast
                    if msg_type == "TEST_LEVEL_BROADCAST" and tl == "2":
                        if not TEST_LEVEL_BROADCAST_READY.is_set():
                            print(f"Received Test Level Broadcast: {tl}")
                            _send_stop_broadcast(pub_client)
                            TEST_LEVEL_BROADCAST_READY.set()
                        return

                    if tl != "2":
                        return

                    message_id = payload.get("message_id") or payload.get("timestamp")
                    if message_id:
                        with _RESP_LOCK:
                            _AP_RESPONSES[message_id] = {
                                "result": payload.get("result"),
                                "received_label": payload.get("received_label", ""),
                                "timestamp": payload.get("timestamp"),
                                "received_at": datetime.utcnow().isoformat(),
                            }
        except Exception as e:
            print(f"Failed to parse AP response: {e}")

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()
    return client

def _publish_to_ap(client, stats, expected_label, timestamp, band, message_id, extra=None):
    """
    Publish one TL=2 request to the AP. `extra` can carry cycle markers such as
    {'cycle': 2, 'sample_index': 1, 'first_in_cycle': True}.
    """
    payload = {
        "TEST_LEVEL": "2",
        "timestamp": timestamp,
        "band": band,
        "model_inference_label": expected_label,
        "all_stats": stats,
        "message_id": message_id,
        "sent_at": datetime.utcnow().isoformat(),
    }
    if extra:
        payload.update({k: v for k, v in extra.items() if v is not None})

    body = json.dumps(payload).encode("utf-8")
    header = _pack_meta_header_for_live(body)
    client.publish(MQTT_AP_SEND_TOPIC, header + body, qos=1)

def _write_report_header_if_needed(csv_path):
    _ensure_dir(csv_path)
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "cycle", "data_file", "line_idx", "message_id", "timestamp",
                "expected_label", "received_label", "status", "result", "latency_ms",
                "sent_at", "received_at"
            ])

def _handshake_with_ap(pub, attempts=3, timeout_sec=AP_RESPONSE_TIMEOUT_SEC, band='unknown during handshake'):
    """Probe AP readiness before the first real test message."""
    for i in range(1, attempts + 1):
        msg_id = f"__HANDSHAKE__-{uuid.uuid4().hex}"
        # Dummy stats for handshake
        dummy_stats = [0.0] * 50
        _publish_to_ap(
            pub,
            stats=dummy_stats,
            expected_label="handshake",
            timestamp=datetime.utcnow().isoformat(),
            band=band,
            message_id=msg_id
        )
        t0 = time.time()
        while time.time() - t0 < timeout_sec:
            with _RESP_LOCK:
                resp = _AP_RESPONSES.pop(msg_id, None)
            if resp:
                print(f"[handshake] AP ready (attempt {i})")
                return True
            time.sleep(0.05)
        print(f"[handshake] no response (attempt {i})")
    print("[handshake] proceeding without positive ack (AP may still be starting)")
    return False

def run_validation_mode():
    """
    Validation Mode (TL=2):
    Reads parsed CSV files (from data_collection/...) instead of JSON lines.
    Extracts the 50 REQUIRED_STATS in order.
    Sends to AP and verifies response.
    """
    # Check if TEST_LEVEL is explicitly set to something else
    env_tl = os.getenv("TEST_LEVEL")
    if env_tl and env_tl != "2":
        print(f"ad_unit_validator invoked with TEST_LEVEL={env_tl}, but it requires TEST_LEVEL=2. Exiting.")
        sys.exit(0)

    # Look for CSV files in data/test_mode recursively
    data_files = sorted(glob.glob(
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "ad_data_collection", "data", "test_mode", "**", "*.csv"),
        recursive=True
    ))
    if not data_files:
        print("No data files found in data/test_mode/**/*.csv. Nothing to validate.")
        return

    pub = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    def _on_pub_connect(client, userdata, flags, reasonCode, properties=None):
        if reasonCode == 0:
            PUB_READY.set()
    pub.on_connect = _on_pub_connect
    pub.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    pub.loop_start()

    resp_listener = _start_response_listener(pub)

    PUB_READY.wait(timeout=2.0)
    RESP_READY.wait(timeout=2.0)

    print("Waiting for TEST_LEVEL_BROADCAST (TEST_LEVEL=2) from AP...")
    if not TEST_LEVEL_BROADCAST_READY.wait(timeout=30.0):
        print("Timeout waiting for AP TEST_LEVEL_BROADCAST. Ensure AP is running with TEST_LEVEL=2. Exiting.")
        pub.loop_stop()
        resp_listener.loop_stop()
        sys.exit(1)

    print("Validator starting verification cycles. Press Ctrl+C to stop.")

    # Count total samples
    total_samples = 0
    for df in data_files:
        try:
            with open(df) as f:
                reader = csv.reader(f)
                next(reader, None) # header
                total_samples += sum(1 for row in reader)
        except: pass

    print(f"Loaded {total_samples} samples from {len(data_files)} files.")

    cycle = 0
    try:
        while cycle < VALIDATION_CYCLES:
            sample_idx_in_cycle = 0
            cycle += 1
            total, passed, failed, timeouts = 0, 0, 0, 0
            cycle_start = time.time()

            # Generate a dynamic report path for this cycle
            ts_str = datetime.utcnow().strftime('%Y-%m-%d_%H-%M-%S')
            report_path = os.path.join(REPORTS_DIR, f"ad_report_{ts_str}.csv")
            _write_report_header_if_needed(report_path)
            print(f"Cycle {cycle} starting... Results will be logged to: {report_path}")

            for data_file in data_files:
                # Extract band and test_label from path structure:
                # data/test_mode/{band}/{test_label}/{test_name}_{timestamp}.csv
                path_parts = Path(data_file).parts
                try:
                    tm_idx = list(path_parts).index('test_mode')
                    file_band = path_parts[tm_idx + 1] if tm_idx + 1 < len(path_parts) else "unknown"
                    file_test_label = path_parts[tm_idx + 2] if tm_idx + 2 < len(path_parts) else "unknown"
                except ValueError:
                    file_band = "unknown"
                    file_test_label = "unknown"

                # Strip 'G' suffix from band (e.g. "5G" -> 5) to match AP expectation
                band_stripped = file_band.rstrip('G')
                try:
                    file_band_int = int(band_stripped)
                except (ValueError, TypeError):
                    file_band_int = file_band

                with open(data_file) as f:
                    reader = csv.DictReader(f)
                    for line_idx, row in enumerate(reader, start=1):

                        # Extract 50 stats in order
                        try:
                            stats = []
                            for stat_name in REQUIRED_STATS:
                                val = row.get(stat_name, 0.0)
                                try:
                                    stats.append(float(val))
                                except:
                                    stats.append(0.0)

                            if len(stats) != 50:
                                # Should not happen if loop completes
                                print(f"[{data_file}:{line_idx}] Stat count mismatch: {len(stats)}")
                                continue

                            # Get metadata: band and expected_label come from the path structure
                            timestamp = row.get("timestamp", datetime.utcnow().isoformat())
                            band = file_band_int
                            expected_label = file_test_label

                        except Exception as e:
                            print(f"[{data_file}:{line_idx}] Error parsing row: {e}")
                            continue

                        sample_idx_in_cycle += 1
                        message_id = f"{timestamp}-{uuid.uuid4().hex}"
                        sent_at_iso = datetime.utcnow().isoformat()
                        send_time = time.time()

                        _publish_to_ap(
                            pub, stats, expected_label, timestamp, band, message_id,
                            extra={
                                "cycle": cycle,
                                "sample_index": sample_idx_in_cycle,
                                "first_in_cycle": (sample_idx_in_cycle == 1),
                            },
                        )

                        total += 1

                        # Wait for AP response
                        status = "TIMEOUT"
                        result = None
                        received_label = ""
                        received_at_iso = ""

                        while (time.time() - send_time) < AP_RESPONSE_TIMEOUT_SEC:
                            with _RESP_LOCK:
                                resp = _AP_RESPONSES.pop(message_id, None)
                            if resp:
                                result = resp.get("result")
                                received_label = resp.get("received_label", "")
                                received_at_iso = resp.get("received_at", datetime.utcnow().isoformat())
                                status = "PASS" if result == "pass" else "FAIL"
                                break
                            time.sleep(0.05)

                        if status == "TIMEOUT":
                            timeouts += 1
                        elif status == "PASS":
                            passed += 1
                        else:
                            failed += 1

                        latency_ms = int((time.time() - send_time) * 1000)
                        with open(report_path, "a", newline="") as fcsv:
                            writer = csv.writer(fcsv)
                            writer.writerow([
                                cycle, data_file, line_idx, message_id, timestamp,
                                expected_label, received_label, status, (result or ""), latency_ms,
                                sent_at_iso, received_at_iso
                            ])

                        print(f"[{status}] {data_file}:{line_idx} "
                              f"expected={expected_label} received={received_label} "
                              f"lat={latency_ms}ms (msg_id={message_id[:8]}...)")

            duration = time.time() - cycle_start
            print(f"=== Summary (cycle {cycle}) total={total} pass={passed} "
                  f"fail={failed} timeout={timeouts} in {duration:.1f}s ===")
            time.sleep(CYCLE_SLEEP_SEC)
    except KeyboardInterrupt:
        print("Validator stopped by user.")
    finally:
        pub.loop_stop()
        pub.disconnect()
        if resp_listener is not None:
            resp_listener.loop_stop()
            resp_listener.disconnect()

if __name__ == "__main__":
    run_validation_mode()
