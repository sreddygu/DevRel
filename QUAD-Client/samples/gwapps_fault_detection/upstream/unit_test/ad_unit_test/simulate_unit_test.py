'''
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 '''

import json
import os
import random
import struct
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Validator sends requests to AP on this topic; simulator listens here
MQTT_AP_SEND_TOPIC = 'ANAMOLY_DETECTION:/ANAMOLY_DETECTION:/:INPUT_PARAMS'
# Simulator sends responses to validator on this topic; validator listens here
MQTT_AP_RESPONSE_TOPIC = 'OUT/12345678/ANAMOLY_DETECTION/UnitTest/payload'

# Broadcast topics
MQTT_BROADCAST_TOPIC = 'OUT/12345678/ANAMOLY_DETECTION/UnitTest/payload'
MQTT_CONTROL_TOPIC = 'ANAMOLY_DETECTION:/ANAMOLY_DETECTION:/:INPUT_PARAMS'

META_FORMAT = 'HHHHHHHHHHH'
META_SIZE = struct.calcsize(META_FORMAT)

SRC_APP_ID = 13 # ANAMOLY_DETECTION
DEST_APP_ID = 27 # AD_UNIT_TEST_APP
CHANNEL_RESP = 2
CHANNEL_INIT = 3
MSG_TYPE_DATA = 1
MSG_TYPE_CTRL = 2
APP_VER = 1
SUB_CATEGORY = 0

_msg_counter = 0
def _next_msg_id():
    global _msg_counter
    _msg_counter = (_msg_counter + 1) & 0xFFFF
    return _msg_counter

def build_cloud_meta_data(
    service_name: str,
    read_files: bool = False,
    num_files: int = 0,
) -> bytes:
    """Build cloud_meta_data structure for CIA."""
    name_bytes = service_name.encode("utf-8")[:32].ljust(32, b"\0")
    read_files_byte = struct.pack("?", read_files)
    num_files_byte = struct.pack("B", num_files)
    payload = name_bytes + read_files_byte + num_files_byte

    # V2 Trailer: headerLen (uint16) + headerVersion (uint16) + nextHeaderEnum (uint16)
    header_len = len(payload) + 6
    header_version = 2
    next_header_enum = 0
    payload += struct.pack("HHH", header_len, header_version, next_header_enum)

    return payload

def _pack_header(body_bytes: bytes, *, channel: int, msg_type: int) -> bytes:
    msg_id = _next_msg_id()
    length = len(body_bytes) & 0xFFFF
    header_len = META_SIZE
    header_version = 2
    next_header_enum = 0
    return struct.pack(
        META_FORMAT,
        SRC_APP_ID, DEST_APP_ID, channel, msg_type, APP_VER,
        msg_id, SUB_CATEGORY, length, header_len, header_version, next_header_enum
    )

class UnitTestSimulator:
    def __init__(self):
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.broadcasting = True
        self.stop_event = threading.Event()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        print("AP Simulator (UnitTest) connected")
        client.subscribe(MQTT_AP_SEND_TOPIC, qos=1)
        client.subscribe(MQTT_CONTROL_TOPIC, qos=1)

    def _on_message(self, client, userdata, msg):
        try:
            # Decode payload
            payload_data = msg.payload
            if len(payload_data) >= 16:
                try:
                    fields = struct.unpack('HHHHHHHH', payload_data[:16])
                    version = fields[4]
                    if version >= 3 and len(payload_data) >= 22:
                        meta = struct.unpack('HHHHHHHHHHH', payload_data[:22])
                        header_len = meta[8]
                        if 16 <= header_len <= len(payload_data):
                            payload_data = payload_data[header_len:]
                        else:
                            payload_data = payload_data[22:]
                    else:
                        if len(payload_data) >= 22:
                            payload_data = payload_data[22:]
                        else:
                            payload_data = payload_data[16:]
                except:
                    pass

            payload_str = payload_data.decode('utf-8', errors='ignore')

            try:
                payload = json.loads(payload_str)
            except json.JSONDecodeError:
                return

            # Check if it's a STOP command
            if payload.get("control") == "STOP_BROADCAST":
                print("Received STOP_BROADCAST command")
                self.broadcasting = False
                return

            # Process validation request
            self._process_validation_request(payload)

        except Exception as e:
            print(f"Error processing message: {e}")

    def _broadcast_loop(self):
        while self.broadcasting and not self.stop_event.is_set():
            payload = {
                "message_type": "TEST_LEVEL_BROADCAST",
                "TEST_LEVEL": "2",
                "timestamp": datetime.utcnow().isoformat()
            }
            json_bytes = json.dumps(payload).encode('utf-8')
            cloud_meta = build_cloud_meta_data("UnitTest")
            full_payload = cloud_meta + json_bytes
            header = _pack_header(full_payload, channel=CHANNEL_INIT, msg_type=MSG_TYPE_CTRL)
            self.client.publish(MQTT_BROADCAST_TOPIC, header + full_payload, qos=1)
            print("Broadcasting TEST_LEVEL=2")
            time.sleep(2)

    def _process_validation_request(self, payload):
        timestamp = payload.get("timestamp")
        message_id = payload.get("message_id")

        if not message_id:
            return

        expected = (payload.get("model_inference_label") or "pass").strip()
        label_pool = ["pass", "beacon_stuck", "data_stall", "fail_to_connect", "client_disconnect"]

        if random.random() < 0.7:
            received_label = expected
        else:
            alts = [x for x in label_pool if x != expected]
            received_label = random.choice(alts) if alts else expected

        result = "pass" if received_label == expected else "fail"

        response = {
            "TEST_LEVEL": "2",
            "timestamp": timestamp,
            "result": result,
            "received_label": received_label,
            "message_id": message_id,
        }
        json_bytes = json.dumps(response).encode('utf-8')
        cloud_meta = build_cloud_meta_data("UnitTest")
        full_payload = cloud_meta + json_bytes
        header = _pack_header(full_payload, channel=CHANNEL_RESP, msg_type=MSG_TYPE_DATA)
        self.client.publish(MQTT_AP_RESPONSE_TOPIC, header + full_payload, qos=1)
        print(f"Processed ts {timestamp} (id={str(message_id)[:8]}...): expected={expected} -> {result}")

    def run(self):
        self.client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self.client.loop_start()

        # Start broadcasting thread
        broadcast_thread = threading.Thread(target=self._broadcast_loop)
        broadcast_thread.start()

        try:
            while not self.stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping...")
            self.stop_event.set()
            self.broadcasting = False
            broadcast_thread.join()
            self.client.loop_stop()
            self.client.disconnect()

if __name__ == "__main__":
    sim = UnitTestSimulator()
    sim.run()
