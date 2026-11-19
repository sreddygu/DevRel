'''
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 '''

import glob
import io
import json
import os
import re
import shutil
import struct
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
import pandas as pd
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
SAVE_TAR = os.getenv("SAVE_TAR", "false").lower() == "true"
SESSION_TIMEOUT_SEC = float(os.getenv("SESSION_TIMEOUT_SEC", "30.0"))

class SessionManager:
    def __init__(self):
        self.last_msg_time = 0
        self.current_session_id = None

    def get_session_id(self):
        current_time = time.time()
        if self.current_session_id is None or (current_time - self.last_msg_time) > SESSION_TIMEOUT_SEC:
            self.current_session_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            print(f"[collector] New session started: {self.current_session_id}")
        self.last_msg_time = current_time
        return self.current_session_id

# CIA DataCollection service topic format (wildcard matches any device UID)
MQTT_TELEMETRY_TOPIC = 'OUT/+/ANAMOLY_DETECTION/DataCollection/payload'

META_FORMAT = 'HHHHHHHH'
META_SIZE = struct.calcsize(META_FORMAT)

# --- User Provided Script Constants and Functions ---

WIFISTATS_GLOB = "tl1_wifistats_*.txt"
JSON_GLOB      = "tl1_sample_*.json"
FD_LOGS_GLOB   = "*fd_logs.txt" # Added for anomaly detection

APPEND = True
INCLUDE_SECTION_IN_COLNAME = True

MANUAL_STAT_NAME_OVERRIDES = {
    'Control_Stats/Rx_Management':'Control_Stats/Rx_Management',
    'Control_Stats/Tx_Management':'Control_Stats/Tx_Management',
    'cmd_result(sec=3;hwq_id=0;mac_id=0)[0]':'cmd_result/mac_id_0_hwq_id_0_type_0',
    'cmd_result(sec=3;hwq_id=0;mac_id=0)[1]':'cmd_result/mac_id_0_hwq_id_0_type_1',
    'cmd_result(sec=3;hwq_id=0;mac_id=0)[2]':'cmd_result/mac_id_0_hwq_id_0_type_2',
    'cmd_result(sec=3;hwq_id=0;mac_id=0)[3]':'cmd_result/mac_id_0_hwq_id_0_type_3',
    'cmd_result(sec=3;hwq_id=0;mac_id=0)[4]':'cmd_result/mac_id_0_hwq_id_0_type_4',
    'cmd_result(sec=3;hwq_id=0;mac_id=0)[5]':'cmd_result/mac_id_0_hwq_id_0_type_5',
    'cmd_result(sec=3;hwq_id=0;mac_id=0)[6]':'cmd_result/mac_id_0_hwq_id_0_type_6',
    'cmd_result(sec=3;hwq_id=0;mac_id=0)[7]':'cmd_result/mac_id_0_hwq_id_0_type_7',
    'cmd_result(sec=3;hwq_id=0;mac_id=0)[8]':'cmd_result/mac_id_0_hwq_id_0_type_8',
    'cmd_result(sec=3;hwq_id=0;mac_id=0)[9]':'cmd_result/mac_id_0_hwq_id_0_type_9',
    'cmd_result(sec=3;hwq_id=0;mac_id=0)[10]':'cmd_result/mac_id_0_hwq_id_0_type_10',
    'cmd_result(sec=3;hwq_id=0;mac_id=0)[11]':'cmd_result/mac_id_0_hwq_id_0_type_11',
    'cmd_result(sec=3;hwq_id=0;mac_id=0)[12]':'cmd_result/mac_id_0_hwq_id_0_type_12',
    'cmd_result(sec=3;hwq_id=4;mac_id=0)[0]':'cmd_result/mac_id_0_hwq_id_4_type_0',
    'cmd_result(sec=3;hwq_id=4;mac_id=0)[1]':'cmd_result/mac_id_0_hwq_id_4_type_1',
    'cmd_result(sec=3;hwq_id=4;mac_id=0)[2]':'cmd_result/mac_id_0_hwq_id_4_type_2',
    'cmd_result(sec=3;hwq_id=4;mac_id=0)[3]':'cmd_result/mac_id_0_hwq_id_4_type_3',
    'cmd_result(sec=3;hwq_id=4;mac_id=0)[4]':'cmd_result/mac_id_0_hwq_id_4_type_4',
    'cmd_result(sec=3;hwq_id=4;mac_id=0)[5]':'cmd_result/mac_id_0_hwq_id_4_type_5',
    'cmd_result(sec=3;hwq_id=4;mac_id=0)[6]':'cmd_result/mac_id_0_hwq_id_4_type_6',
    'cmd_result(sec=3;hwq_id=4;mac_id=0)[7]':'cmd_result/mac_id_0_hwq_id_4_type_7',
    'cmd_result(sec=3;hwq_id=4;mac_id=0)[8]':'cmd_result/mac_id_0_hwq_id_4_type_8',
    'cmd_result(sec=3;hwq_id=4;mac_id=0)[9]':'cmd_result/mac_id_0_hwq_id_4_type_9',
    'cmd_result(sec=3;hwq_id=4;mac_id=0)[10]':'cmd_result/mac_id_0_hwq_id_4_type_10',
    'cmd_result(sec=3;hwq_id=4;mac_id=0)[11]':'cmd_result/mac_id_0_hwq_id_4_type_11',
    'cmd_result(sec=3;hwq_id=4;mac_id=0)[12]':'cmd_result/mac_id_0_hwq_id_4_type_12',
    'ppdu_ok(sec=1;mac_id=0)':'ppdu_ok',
    'tx_xretry(sec=1;mac_id=0)':'tx_xretry',
    'fw_rx_mgmt_subtype(sec=48)[0]':'fw_rx_mgmt_subtype/type_0',
    'fw_rx_mgmt_subtype(sec=48)[2]':'fw_rx_mgmt_subtype/type_2',
    'fw_rx_mgmt_subtype(sec=48)[4]':'fw_rx_mgmt_subtype/type_4',
    'fw_rx_mgmt_subtype(sec=48)[11]':'fw_rx_mgmt_subtype/type_11',
    'fw_rx_mgmt_subtype(sec=48)[12]':'fw_rx_mgmt_subtype/type_12',
    'fw_tx_mgmt_subtype(sec=48)[1]':'fw_tx_mgmt_subtype/tx_mgmt_1',
    'fw_tx_mgmt_subtype(sec=48)[3]':'fw_tx_mgmt_subtype/tx_mgmt_3',
    'fw_tx_mgmt_subtype(sec=48)[5]':'fw_tx_mgmt_subtype/tx_mgmt_5',
    'fw_tx_mgmt_subtype(sec=48)[10]':'fw_tx_mgmt_subtype/tx_mgmt_10',
    'fw_tx_mgmt_subtype(sec=48)[11]':'fw_tx_mgmt_subtype/tx_mgmt_11',
    'fw_tx_mgmt_subtype(sec=48)[12]':'fw_tx_mgmt_subtype/tx_mgmt_12',
    'm1_packets(sec=8;mac_id=0)':'m1_packets',
    'm3_packets(sec=8;mac_id=0)':'m3_packets',
    'm1_success(sec=8;mac_id=0)':'m1_success',
    'm3_success(sec=8;mac_id=0)':'m3_success',
    'rssi_mgmt(sec=10;mac_id=0)':'rssi_mgmt',
    'rssi_data(sec=10;mac_id=0)':'rssi_data',
    'rssi_comb(sec=10;mac_id=0)':'rssi_comb',
    'rssi_in_dbm(sec=10;mac_id=0)':'rssi_in_dbm',
}

def _is_within_directory(directory: str, target: str) -> bool:
    abs_directory = os.path.abspath(directory)
    abs_target = os.path.abspath(target)
    return os.path.commonpath([abs_directory]) == os.path.commonpath([abs_directory, abs_target])

def safe_tar_extract(tar: tarfile.TarFile, path: str) -> None:
    for member in tar.getmembers():
        member_path = os.path.join(path, member.name)
        if _is_within_directory(path, member_path):
            tar.extract(member, path=path)
        else:
            print(f"⚠️ Skipping suspicious tar member: {member.name}")

def _find_latest_by_mtime(root: str, pattern: str, prefer_dir: str | None = None) -> str | None:
    if prefer_dir and os.path.isdir(prefer_dir):
        preferred = [
            p for p in glob.glob(os.path.join(prefer_dir, pattern))
            if os.path.isfile(p)
        ]
        if preferred:
            return max(preferred, key=os.path.getmtime)

    candidates = []
    for walk_root, _, _ in os.walk(root):
        if prefer_dir and os.path.abspath(walk_root) == os.path.abspath(prefer_dir):
            continue
        candidates.extend(glob.glob(os.path.join(walk_root, pattern)))

    candidates = [os.path.abspath(c) for c in candidates if os.path.isfile(c)]
    if not candidates:
        return None
    return max(candidates, key=os.path.getmtime)

def format_json_timestamp(ts_iso: object) -> str | None:
    if not isinstance(ts_iso, str):
        return None
    s = ts_iso.strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            continue
    sanitized = s.replace('T', ' ').rstrip('Z')
    if '.' not in sanitized:
        sanitized = sanitized + '.000000'
    return sanitized

def parse_num(s: str):
    s = s.strip()
    if s == "":
        return s
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return s

def parse_pairs(text: str) -> list[tuple[str, object]]:
    t = text.strip()
    t = t.replace(" : ", ":").replace("  :", ":").replace(": ", ":")
    if t.startswith(","):
        t = t[1:].lstrip()
    pairs: list[tuple[str, object]] = []
    if "," in t:
        tokens = [tok.strip() for tok in t.split(",") if tok.strip()]
    else:
        tokens = [tok.strip() for tok in t.split() if ":" in tok]
    for tok in tokens:
        if ":" not in tok:
            continue
        k, v = tok.split(":", 1)
        pairs.append((k.strip(), parse_num(v)))
    return pairs

def ctx_suffix(ctx: dict[str, object | None], include_section: bool) -> str:
    parts = []
    keys_order = ["sec", "chain_pair", "hwq_id", "mac_id"] if include_section else ["chain_pair", "hwq_id", "mac_id"]
    for key in keys_order:
        val = ctx.get(key)
        if val is not None:
            parts.append(f"{key}={val}")
    return f"({';'.join(parts)})" if parts else ""

def normalize_name(name: str) -> str:
    return name.strip().rstrip(":")

section_delim = re.compile(r'^\s*===\s*WIFISTAT\s+(\d+)\s*===')
colon_header_re = re.compile(r'^\s*([A-Za-z0-9_\[\] .\-/%]+):\s*(.*)$')
chain_pair_re = re.compile(r'^\s*Chain\s+Pair\s+(\d+)\s+Stats', re.IGNORECASE)
pure_equals_re = re.compile(r'^=+$')

def parse_wifistats_one_row(in_path: str, include_section_in_col: bool = True) -> dict[str, object]:
    if not os.path.exists(in_path):
        raise FileNotFoundError(f"File not found: {in_path}")

    single_row: dict[str, object] = {}
    section_id: int | None = None
    current_ctx: dict[str, object | None] = {"sec": None, "chain_pair": None, "hwq_id": None, "mac_id": None}
    current_colon_header: str | None = None
    col_count: dict[tuple[str, str, str, str], int] = {}

    def ensure_unique_col(base_name: str, context_sfx: str, inline_subctx: str | None, subkey: str | None) -> str:
        subctx_sfx = f"[{inline_subctx}]" if inline_subctx else ""
        subkey_sfx = f"[{subkey}]" if (subkey is not None and subkey != "") else ""
        key = (base_name, context_sfx, subctx_sfx, subkey_sfx)
        cnt = col_count.get(key, 0) + 1
        col_count[key] = cnt
        occ = "" if cnt == 1 else f"#{cnt}"
        return f"{base_name}{context_sfx}{subctx_sfx}{subkey_sfx}{occ}"

    with open(in_path, encoding="utf-8") as f:
        for idx, raw in enumerate(f, start=1):
            s = raw.strip()
            if not s:
                continue
            if pure_equals_re.match(s):
                continue

            msec = section_delim.match(s)
            if msec:
                section_id = int(msec.group(1))
                current_ctx["sec"] = section_id if include_section_in_col else None
                current_ctx["chain_pair"] = None
                current_ctx["hwq_id"] = None
                current_ctx["mac_id"] = None
                current_colon_header = None
                continue

            mch = chain_pair_re.match(s)
            if mch:
                current_ctx["chain_pair"] = int(mch.group(1))
                current_colon_header = None
                continue

            if "=" in s:
                left, right = s.split("=", 1)
                left = left.strip()
                right = right.strip()

                n_mixed = re.match(r'^(?P<base>[^:]+):\s*(?P<sub>[^=]+)$', left)
                inline_subctx = None
                base_name = normalize_name(left)
                if n_mixed:
                    base_name = normalize_name(n_mixed.group("base"))
                    inline_subctx = n_mixed.group("sub").strip()

                nb = re.match(r'^(?P<base>[A-Za-z0-9_]+)\[(?P<bidx>\d+)\]$', base_name)
                if nb:
                    base_name = nb.group("base")
                    inline_subctx = (inline_subctx + ";" if inline_subctx else "") + f"idx={nb.group('bidx')}"

                if base_name == "hwq_id":
                    try:
                        current_ctx["hwq_id"] = int(right.split()[0])
                    except Exception:
                        current_ctx["hwq_id"] = parse_num(right)
                elif base_name == "mac_id":
                    try:
                        current_ctx["mac_id"] = int(right.split()[0])
                    except Exception:
                        current_ctx["mac_id"] = parse_num(right)

                if base_name.startswith("HTT_"):
                    current_colon_header = None
                    continue

                context_sfx = ctx_suffix(current_ctx, include_section_in_col)
                rhs = (right or "").strip()
                pairs = parse_pairs(rhs) if (":" in rhs) else []

                if pairs:
                    for k, v in pairs:
                        col = ensure_unique_col(base_name, context_sfx, inline_subctx, k)
                        single_row[col] = v
                else:
                    col = ensure_unique_col(base_name, context_sfx, inline_subctx, None)
                    single_row[col] = parse_num(rhs)

                current_colon_header = None
                continue

            mcol = colon_header_re.match(s)
            if mcol:
                header = normalize_name(mcol.group(1))
                payload = mcol.group(2).strip() if mcol.group(2) else ""

                if header.startswith("HTT_") or header.upper().startswith("AP EDCA PARAMETERS"):
                    current_colon_header = None
                    continue

                context_sfx = ctx_suffix(current_ctx, include_section_in_col)

                if payload:
                    pairs = parse_pairs(payload) if (":" in payload) else []
                    if pairs:
                        for k, v in pairs:
                            col = ensure_unique_col(header, context_sfx, None, k)
                            single_row[col] = v
                    else:
                        col = ensure_unique_col(header, context_sfx, None, None)
                        single_row[col] = parse_num(payload)
                    current_colon_header = header
                else:
                    current_colon_header = header
                continue

            if current_colon_header:
                payload = s
                context_sfx = ctx_suffix(current_ctx, include_section_in_col)
                pairs = parse_pairs(payload) if (":" in payload) else []
                if pairs:
                    for k, v in pairs:
                        col = ensure_unique_col(current_colon_header, context_sfx, None, k)
                        single_row[col] = v
                else:
                    col = ensure_unique_col(current_colon_header, context_sfx, None, None)
                    single_row[col] = parse_num(payload)
                continue

            continue

    return single_row

def load_meta(json_path: str) -> dict:
    with open(json_path, encoding="utf-8") as jf:
        raw = jf.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    meta = {}
    m = re.search(r'\btimestamp\s+([^\s]+)', raw)
    if m: meta["timestamp"] = m.group(1)
    m = re.search(r'\bband\s+([^\s]+)', raw)
    if m: meta["band"] = m.group(1)
    m = re.search(r'\bclients_per_band\s+([^\s]+)', raw)
    if m: meta["clients_per_band"] = parse_num(m.group(1))
    return meta

def _override_keys_flat(d: dict, mapping: dict) -> dict:
    out = {}
    def _to_num(x):
        try: return float(x)
        except (TypeError, ValueError): return None
    for k, v in d.items():
        new_k = mapping.get(k, k)
        if new_k in out:
            prev = out[new_k]
            a, b = _to_num(prev), _to_num(v)
            if a is not None and b is not None:
                out[new_k] = a + b
            else:
                out[new_k] = v if (v is not None and v != "") else prev
        else:
            out[new_k] = v
    return out

# --- MQTT and Orchestration Wrapper ---

def _decode_ap_payload(raw: bytes):
    if raw is None: return None, b''
    if len(raw) >= META_SIZE:
        try:
            meta = struct.unpack(META_FORMAT, raw[:META_SIZE])
            return meta, raw[META_SIZE:]
        except Exception:
            return None, raw
    return None, raw

def parse_cloud_meta(payload_bytes):
    """Parse cloud_meta_data header, matching parse_cloud_meta_length() in cia_services.c.

    Structure (V2):
      [32 bytes]              service_name (null-padded)
      [1 byte]                read_files (bool)
      [1 byte]                number_of_files (uint8)
      If read_files and number_of_files > 0:
        [variable]            number_of_files null-terminated file path strings
        [4 * num_files bytes] data type enums (uint32 each)
        [4 * num_files bytes] files_size array (uint32 each)  -- V2
      [2 bytes]               headerLen (uint16)              -- V2
      [2 bytes]               headerVersion (uint16)          -- V2
      [2 bytes]               nextHeaderEnum (uint16)         -- V2
    """
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
                    print(f"[collector] Malformed cloud meta: no null terminator for file path {i}")
                    return None
                offset = null_idx + 1  # advance past the null terminator

            # Skip data types array: num_files * sizeof(uint32_t) = num_files * 4 bytes
            offset += num_files * 4

            # Skip V2 files_size array: num_files * sizeof(uint32_t) = num_files * 4 bytes
            offset += num_files * 4

        # Skip V2 trailer: headerLen (uint16) + headerVersion (uint16) + nextHeaderEnum (uint16)
        offset += 6

        return {'service_name': service_name, 'read_files': read_files, 'num_files': num_files, 'payload_offset': offset}
    except Exception as e:
        print(f"Error parsing cloud meta: {e}")
        return None

def process_tar_content_and_save(tar_bytes, session_id):
    # Create temp directory for extraction
    extract_root = "temp_extraction"
    if os.path.exists(extract_root):
        shutil.rmtree(extract_root)
    os.makedirs(extract_root, exist_ok=True)

    try:
        file_obj = io.BytesIO(tar_bytes)
        with tarfile.open(fileobj=file_obj, mode="r:*") as tf:
            safe_tar_extract(tf, extract_root)

        # Find files (tar received from AP; search entire extract_root)
        INPUT_PATH = _find_latest_by_mtime(extract_root, WIFISTATS_GLOB)
        JSON_PATH  = _find_latest_by_mtime(extract_root, JSON_GLOB)

        if not INPUT_PATH or not JSON_PATH:
            print("[collector] Missing wifistats or json in tar")
            return

        # 1) Parse one wide row (dict) from input
        one_row_dict = parse_wifistats_one_row(INPUT_PATH, INCLUDE_SECTION_IN_COLNAME)

        # 2) Apply manual overrides to stat names (dict keys)
        one_row_dict = _override_keys_flat(one_row_dict, MANUAL_STAT_NAME_OVERRIDES)

        # 3) Enrich with JSON
        meta = load_meta(JSON_PATH)

        # (a) Add clients_per_band as 'Control_Stats/Total_Number_of_connected_clients'
        clients_per_band_val = meta.get("clients_per_band", None)
        try:
            clients_per_band_num = float(clients_per_band_val)
            if clients_per_band_num.is_integer():
                clients_per_band_num = int(clients_per_band_num)
        except (TypeError, ValueError):
            clients_per_band_num = clients_per_band_val
        one_row_dict["Control_Stats/Total_Number_of_connected_clients"] = clients_per_band_num

        # (b) Reformat timestamp from JSON to 'YYYY-MM-DD HH:MM:SS.%f'
        ts_iso = meta.get("timestamp", None)
        formatted_ts = format_json_timestamp(ts_iso)
        one_row_dict["timestamp"] = formatted_ts

        # 4) Convert to single-row DataFrame
        df = pd.DataFrame([one_row_dict])

        # 5) Build dynamic output path: data/test_mode/{band}/{TEST_LABEL}/{session_id}/TEST_NAME_{session_id}.csv
        band       = meta.get("band",       "unknown")
        test_label = meta.get("test_label", "unknown")
        test_name  = meta.get("test_name",  "unknown")

        # Sanitize timestamp for filename
        safe_ts = formatted_ts.replace(":", "-").replace(" ", "_") if formatted_ts else "unknown_ts"

        # Save raw tar if SAVE_TAR is enabled
        # Update output paths to be relative to the script's new directory (ad_data_collection)
        base_dir = Path(os.path.dirname(os.path.abspath(__file__)))

        if SAVE_TAR:
            tar_save_dir = base_dir / "data" / "data_collection" / str(band) / str(test_label) / session_id
            tar_save_dir.mkdir(parents=True, exist_ok=True)
            tar_save_path = tar_save_dir / f"{test_name}_{safe_ts}.tar"
            with open(tar_save_path, "wb") as tf_out:
                tf_out.write(tar_bytes)
            print(f"[collector] Saved tar to {tar_save_path}")

        output_dir = base_dir / "data" / "test_mode" / str(band) / str(test_label) / session_id
        output_dir.mkdir(parents=True, exist_ok=True)

        output_csv = output_dir / f"{test_name}_{session_id}.csv"

        # 6) Append to CSV, aligning to existing header if needed
        append_mode = ('a' if APPEND else 'w')
        write_header = (not output_csv.exists()) or (not APPEND)

        if output_csv.exists() and APPEND:
            existing_cols = pd.read_csv(output_csv, nrows=0).columns.tolist()
            union_cols = existing_cols + [c for c in df.columns if c not in existing_cols]
            df = df.reindex(columns=union_cols)

        df.to_csv(output_csv, mode=append_mode, index=False, header=write_header)
        print(f"[collector] Wrote 1 row to {output_csv} (append={APPEND}, header_written={write_header})")

    except Exception as e:
        print(f"[collector] Error processing extracted content: {e}")
    finally:
        if os.path.exists(extract_root):
            shutil.rmtree(extract_root)

def run_collect_mode():
    session_manager = SessionManager()

    def on_connect(client, userdata, flags, reasonCode, properties=None):
        if reasonCode == 0:
            print("Collector connected to MQTT broker")
            client.subscribe(MQTT_TELEMETRY_TOPIC, qos=1)
        else:
            print(f"Collector failed to connect: reasonCode={reasonCode}")

    def on_message(client, userdata, msg):
        try:
            _, body = _decode_ap_payload(msg.payload)
            if len(body) > 32 and body.startswith(b"DataCollection"):
                print("[collector] Received Cloud Meta payload")
                meta = parse_cloud_meta(body)
                if meta:
                    offset = meta.get('payload_offset', 0)
                    tar_content = body[offset:]
                    print(f"[collector] Extracted {len(tar_content)} bytes of tar content")
                    session_id = session_manager.get_session_id()
                    process_tar_content_and_save(tar_content, session_id)
                return
        except Exception as e:
            print(f"[collector] Error: {e}")

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    print("Collector running (TEST_LEVEL=1). Press Ctrl+C to stop.")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("Collector stopped.")

if __name__ == "__main__":
    run_collect_mode()
