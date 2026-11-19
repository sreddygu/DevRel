'''
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 '''

import os
import struct
import threading
import time
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

MQTT_HOST = os.getenv("MQTT_BROKER", "192.168.1.100")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_KEEPALIVE = 60

# TOPIC_RX = "AD Unit Test App:/AD Unit Test App:/:INPUT_PARAMS" #old frmwrk
# CIA publishes to OUT topics, so we need to subscribe to OUT/{device_uid}/AD_UNIT_TEST_APP/DebugLogs
# For now, using wildcard for device_uid
# TOPIC_RX = "OUT/1811834953/ANAMOLY_DETECTION/DebugLogs/payload"
# TOPIC_TX = "IN/1811834953/ANAMOLY_DETECTION/DebugLogs"
TOPIC_RX = "OUT/+/ANAMOLY_DETECTION/DebugLogs/payload"
TOPIC_TX = "IN/+/ANAMOLY_DETECTION/DebugLogs"

DEBUG_DIR = Path(os.path.dirname(__file__))
DEBUG_DIR.mkdir(parents=True, exist_ok=True)

DELAY_BEFORE_START_SECONDS = 5

ENDIAN = "<"
HEADER_FMT = f"{ENDIAN}8H"
HEADER_SIZE = 16  # bytes
EXPECT_WIRE_HEADER = True

SRC_APP_ID_TEST_APP = 27
DST_APP_ID_CIA = 26
DST_APP_ID_ANAMOLY_DET = 13
CHANNEL = 1
MSG_TYPE_CONTROL = 2
MSG_TYPE_DATA = 1
PROTOCOL_VERSION = 1
APP_MSG_DEBUG = 5
APP_MSG_SUB_START = 1
APP_MSG_SUB_STOP = 2

SUBSCRIBE_QOS = 1
PUBLISH_QOS = 1
RETAIN = False


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def pack_header(*, src, dst, channel, msg_type, version, app_msg_id, subcat, body_len) -> bytes:
    """Pack the 8 x uint16 wire header (LITTLE-ENDIAN)."""
    for name, val in {
        "src": src, "dst": dst, "channel": channel, "msg_type": msg_type,
        "version": version, "app_msg_id": app_msg_id, "subcat": subcat,
    }.items():
        if not (0 <= int(val) <= 0xFFFF):
            raise ValueError(f"{name} must be uint16: {val}")
    return struct.pack(
        HEADER_FMT,
        int(src), int(dst), int(channel), int(msg_type),
        int(version), int(app_msg_id), int(subcat),
        int(body_len) & 0xFFFF,
    )


def build_cloud_meta_data(service_name: str) -> bytes:
    """Build cloud_meta_data structure for CIA."""
    # Service name (32 bytes, zero-padded)
    name_bytes = service_name.encode('utf-8')[:32].ljust(32, b'\0')

    # read_files flag (false for control messages)
    read_files = struct.pack('?', False)

    # number_of_files (0 for control messages)
    number_of_files = struct.pack('B', 0)

    # V2 fields (no files_size since read_files == False)
    # headerLen = 32 + 1 + 1 + 2 + 2 + 2 = 40 bytes total metadata payload for CIA
    cloud_len = 40
    v2_fields = struct.pack(f"{ENDIAN}3H", cloud_len, 2, 0)

    return name_bytes + read_files + number_of_files + v2_fields

def parse_cloud_meta(payload_bytes):
    """Parse cloud_meta_data header."""
    try:
        offset = 0
        service_name = payload_bytes[offset:offset+32].decode('utf-8', errors='ignore').strip('\x00')
        offset += 32
        read_files = struct.unpack('?', payload_bytes[offset:offset+1])[0]
        offset += 1
        num_files = struct.unpack('B', payload_bytes[offset:offset+1])[0]
        offset += 1

        if read_files and num_files > 0:
            # Skip num_files null-terminated file path strings
            for i in range(num_files):
                null_idx = payload_bytes.find(b'\x00', offset)
                if null_idx == -1:
                    print(f"[{now_str()}] Malformed cloud meta: no null terminator for file path {i}")
                    return None
                offset = null_idx + 1

            # Skip data types array
            offset += num_files * 4

            # Skip V2 files_size array
            offset += num_files * 4

        # Skip V2 trailer: headerLen (uint16) + headerVersion (uint16) + nextHeaderEnum (uint16)
        offset += 6

        return {'service_name': service_name, 'read_files': read_files, 'num_files': num_files, 'payload_offset': offset}
    except Exception as e:
        print(f"[{now_str()}] Error parsing cloud meta: {e}")
        return None

'''
def make_debug_control(subcat: int) -> bytes:
    """Create debug control message to send via CIA to ANAMOLY_DETECTION.
    
    Message structure sent to CIA:
    [meta_data (dst=CIA)] + [cloud_meta_data (service=DebugLogs)] + [control_message]
    
    The control_message is what CIA will forward to ANAMOLY_DETECTION via MQTT.
    """
    # Build the control message that will be forwarded to ANAMOLY_DETECTION
    control_msg = pack_header(
        src=SRC_APP_ID_TEST_APP,
        dst=DST_APP_ID_ANAMOLY_DET,
        channel=CHANNEL,
        msg_type=MSG_TYPE_CONTROL,
        version=PROTOCOL_VERSION,
        app_msg_id=APP_MSG_DEBUG,
        subcat=subcat,
        body_len=0,
    )
    
    # Build cloud_meta_data for CIA service routing
    cloud_meta = build_cloud_meta_data("DebugLogs")
    
    # Combine: cloud_meta_data + control_message (this is the "payload" for CIA)
    payload = cloud_meta + control_msg
    
    # Build outer meta_data header (to CIA)
    # Note: body_len in meta_data.len field should be the meta_data size itself (16)
    outer_meta = pack_header(
        src=SRC_APP_ID_TEST_APP,
        dst=DST_APP_ID_CIA,
        channel=CHANNEL,
        msg_type=MSG_TYPE_DATA,
        version=PROTOCOL_VERSION,
        app_msg_id=APP_MSG_DEBUG,
        subcat=subcat,
        body_len=16,  # meta_data.len is size of meta_data itself
    )
    
    return outer_meta + payload
'''

def make_debug_control(subcat: int) -> bytes:
    """
    Build the exact framed message that CIA expects to receive on IN/... and
    deliver to ANAMOLY_DETECTION over the transport:
      [meta_data (for AD)] + [cloud_meta_data] + [body]
    No extra "outer header to CIA" is included when publishing on IN/...
    """
    # AD-facing control header (first 16 bytes on the wire)
    control_hdr = pack_header(
        src=SRC_APP_ID_TEST_APP,
        dst=DST_APP_ID_CIA,
        channel=CHANNEL,
        msg_type=MSG_TYPE_DATA,
        version=PROTOCOL_VERSION,
        app_msg_id=APP_MSG_DEBUG,
        subcat=subcat,
        body_len=16,  # meta_data.len is size of meta_data itself
    )

    # cloud_meta_data: "DebugLogs", read_files=false, number_of_files=0
    cloud_meta = build_cloud_meta_data("DebugLogs")

    # (Optional) A tiny control body. If your AD doesn't expect a body, leave it empty.
    body = b""  # e.g., b'{"action":"start"}' for START

    # Final payload sent to the broker on IN/...:
    return control_hdr + cloud_meta + body


def hexstr(b: bytes) -> str:
    return " ".join(f"{x:02X}" for x in b)


class DebugSession:
    def __init__(self):
        self.client = mqtt.Client(client_id="", clean_session=True)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.connected_evt = threading.Event()
        self.stop_evt = threading.Event()
        self.recording = threading.Event()
        self.file_counter = 0
        print(f"[{now_str()}] Debug folder: {DEBUG_DIR}")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print(f"[{now_str()}] Connected to MQTT {MQTT_HOST}:{MQTT_PORT}")
            client.subscribe(TOPIC_RX, qos=SUBSCRIBE_QOS)
            print(f"[{now_str()}] Subscribed to: {TOPIC_RX}")
            self.connected_evt.set()
        else:
            print(f"[{now_str()}] MQTT connect failed rc={rc}")

    def _on_disconnect(self, client, userdata, rc):
        print(f"[{now_str()}] Disconnected from MQTT (rc={rc})")

    def _on_message(self, client, userdata, msg):
        payload = msg.payload
        if not self.recording.is_set():
            print(f"[{now_str()}] Received (ignored; not recording) len={len(payload)} on {msg.topic}")
            return
        try:
            if EXPECT_WIRE_HEADER:
                if len(payload) < HEADER_SIZE:
                    print(f"[{now_str()}] Drop: payload too small for header ({len(payload)} bytes)")
                    return
                header = payload[:HEADER_SIZE]
                body = payload[HEADER_SIZE:]
                try:
                    src, dst, channel, msg_type, version, app_msg_id, subcat, length16 = struct.unpack(HEADER_FMT, header)
                    print(f"[{now_str()}] Received: src={src}, dst={dst}, app_msg_id={app_msg_id}, body_len={len(body)}")
                except struct.error as e:
                    print(f"[{now_str()}] Header unpack failed: {e}")
                    return

                # CIA forwards messages with cloud_meta_data prepended
                meta = parse_cloud_meta(body)
                if meta:
                    offset = meta.get('payload_offset', 0)
                    data = body[offset:]
                    print(f"[{now_str()}] Extracted debug log data (skipped {offset} bytes cloud_meta)")
                else:
                    data = body
            else:
                data = payload

            self.file_counter += 1
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            out_path = DEBUG_DIR / f"debug_{stamp}_{self.file_counter:04d}.txt"
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"[{now_str()}] Saved file: {out_path} ({len(data)} bytes)")
        except Exception as e:
            print(f"[{now_str()}] Error handling message: {e}")

    def run(self):
        self.client.connect(MQTT_HOST, MQTT_PORT, keepalive=MQTT_KEEPALIVE)
        self.client.loop_start()
        if not self.connected_evt.wait(timeout=10):
            raise RuntimeError("MQTT connection timed out")

        print(f"[{now_str()}] Waiting {DELAY_BEFORE_START_SECONDS}s before sending DEBUG START...")
        self._sleep_with_cancel(DELAY_BEFORE_START_SECONDS)

        self._publish_debug_start()
        self.recording.set()
        print(f"[{now_str()}] Recording enabled. Press Ctrl+C to stop...")

        # Loop forever until stop_evt is set
        while not self.stop_evt.is_set():
            time.sleep(0.5)

        self._publish_debug_stop()
        self.recording.clear()
        print(f"[{now_str()}] Recording disabled. Shutting down...")
        self.client.loop_stop()
        self.client.disconnect()

    def _publish_debug_start(self):
        payload = make_debug_control(APP_MSG_SUB_START)
        print(f"[{now_str()}] START payload HEX (first 64 bytes): {hexstr(payload[:64])}")
        print(f"[{now_str()}] Total payload size: {len(payload)} bytes")
        info = self.client.publish(TOPIC_TX, payload=payload, qos=PUBLISH_QOS, retain=RETAIN)
        info.wait_for_publish()
        print(f"[{now_str()}] >>> Sent DEBUG START to {TOPIC_TX}")

    def _publish_debug_stop(self):
        payload = make_debug_control(APP_MSG_SUB_STOP)
        print(f"[{now_str()}] STOP payload HEX (first 64 bytes): {hexstr(payload[:64])}")
        print(f"[{now_str()}] Total payload size: {len(payload)} bytes")
        info = self.client.publish(TOPIC_TX, payload=payload, qos=PUBLISH_QOS, retain=RETAIN)
        info.wait_for_publish()
        print(f"[{now_str()}] >>> Sent DEBUG STOP to {TOPIC_TX}")

    def _sleep_with_cancel(self, seconds: int):
        end = time.time() + seconds
        while time.time() < end and not self.stop_evt.is_set():
            time.sleep(0.2)


def main():
    session = DebugSession()
    try:
        session.run()
    except KeyboardInterrupt:
        print(f"[{now_str()}] KeyboardInterrupt—exiting...")
        session.stop_evt.set()
        try:
            session._publish_debug_stop()
        except Exception:
            pass
        try:
            session.client.loop_stop()
            session.client.disconnect()
        except Exception:
            pass
    except Exception as e:
        print(f"[{now_str()}] Fatal error: {e}")
        try:
            session.client.loop_stop()
            session.client.disconnect()
        except Exception:
            pass


if __name__ == "__main__":
    main()
