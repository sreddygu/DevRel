# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

import os
import re

import numpy as np


def extract_wifistats_1(lines, reason):
    extracted_lines = []

    if reason == "data_stall":
        scalar_keywords = [
            "ppdu_ok",
            "tx_xretry",
            "pdev_resets",
            "mpdu_count_tqm",
            "msdu_count_tqm",
            "num_data_ppdus_tried_ota"
        ]

        section_headers = {
            "HTT_TX_PDEV_STATS_FLUSH_TLV_V": "flush_errs",
            "HTT_TX_PDEV_STATS_MLO_ABORT_TLV_V": "mlo_abort_cnt",
            "HTT_TX_PDEV_STATS_MLO_TXOP_ABORT_TLV_V": "mlo_txop_abort_cnt"
        }

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if any(k in line for k in scalar_keywords):
                extracted_lines.append(line)

            for header, data_key in section_headers.items():
                if header in line:
                    extracted_lines.append(line)
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if data_key in next_line:
                            extracted_lines.append(next_line)
                            i += 1
            i += 1

    elif reason == "beacon_stuck":
        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if "HTT_TX_PDEV_STATS_FLUSH_TLV_V" in line:
                extracted_lines.append(line)
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line.startswith("flush_err"):
                        extracted_lines.append(next_line)
                        j += 1
                    else:
                        break
                i = j - 1  # Skip processed lines

            elif "tx_xretry" in line or "ppdu_ok" in line:
                extracted_lines.append(line)

            i += 1

    return extracted_lines



def extract_wifistats_2(lines, reason):
    if reason == "data_stall":
        keywords = [
            "ppdu_recvd",
            "mpdu_cnt_fcs_ok",
            "udp_msdu_cnt",
            "tcp_ack_msdu_cnt"
        ]
        return [
            line.strip() for line in lines
            if any(keyword in line for keyword in keywords) and ('=' in line or ':' in line)
        ]
    return []

def extract_wifistats_3(lines, reason):
    reason_to_hwq = {
        "data_stall": "hwq_id = 7",
        "beacon_stuck": "hwq_id = 0",
        "fail_to_connect": "hwq_id = 4",
        "client_disconnect": "hwq_id = 4"
    }

    target_hwq = reason_to_hwq.get(reason)
    if not target_hwq:
        return []

    extracted = []
    capturing = False
    temp_block = []

    for line in lines:
        if target_hwq in line:
            capturing = True
            temp_block = [line]
            continue
        if capturing:
            temp_block.append(line)
            if "cmd_result" in line:
                extracted.extend(temp_block)
                capturing = False

    return [line.strip() for line in extracted]

def extract_wifistats_8(lines, reason):
    if reason in {"fail_to_connect", "client_disconnect"}:

        target_section = "HTT_TX_DE_EAPOL_PACKETS_STATS_TLV"
        excluded_keys = {
            "rc4_packets",
            "eap_packets",
            "eapol_start_packets",
            "eapol_logoff_packets",
            "eapol_encap_asf_packets"
        }

        extracted_lines = []
        stats = {}

        i = 0
        while i < len(lines):
            line = lines[i].strip()

            if target_section in line:
                extracted_lines.append(line)  # Add the section header
                i += 1
                while i < len(lines):
                    next_line = lines[i].strip()
                    if next_line.endswith(":") and "HTT_TX_DE_" in next_line:
                        break  # Next section starts
                    if "=" in next_line:
                        key, value = next_line.split("=")
                        key = key.strip()
                        value = int(value.strip())
                        if key not in excluded_keys:
                            extracted_lines.append(next_line)
                            stats[key] = value
                    i += 1
                break  # Only one section per wifistats 8 block
            i += 1

        # Calculate derived statistics if all required values are present
        if all(k in stats for k in ["m1_packets", "m1_compl_fail", "m3_packets", "m3_compl_fail", "g1_packets", "g1_compl_fail", "m1_success", "m3_success"]):
            m1_fail = stats["m1_compl_fail"] / stats["m1_packets"] if stats["m1_packets"] != 0 else 0
            m3_fail = stats["m3_compl_fail"] / stats["m3_packets"] if stats["m3_packets"] != 0 else 0
            g1_fail = stats["g1_compl_fail"] / stats["g1_packets"] if stats["g1_packets"] != 0 else 0
            m1_m3_rate = stats["m1_success"] / stats["m3_success"] if stats["m3_success"] != 0 else 0

            extracted_lines.append(f"m1_fail = {m1_fail:.2f}")
            extracted_lines.append(f"m3_fail = {m3_fail:.2f}")
            extracted_lines.append(f"g1_fail = {g1_fail:.2f}")
            extracted_lines.append(f"m1_m3_rate = {m1_m3_rate:.2f}")

        return extracted_lines
    return []

def extract_wifistats_9(lines, reason):
    if reason in {"data_stall", "fail_to_connect", "client_disconnect"}:

        exact_keys = ["rts_cnt", "rts_success", "tx_mcs", "tx_nss", "tx_bw"]
        pattern = re.compile(rf"^({'|'.join(re.escape(k) for k in exact_keys)})\s*=")

        return [line.strip() for line in lines if pattern.match(line.strip())]
    return []

def extract_wifistats_10(lines, reason):
    if reason in {"data_stall", "fail_to_connect", "client_disconnect"}:

        exact_keys = ["rx_mcs", "rx_nss", "rx_bw"]
        pattern = re.compile(rf"^({'|'.join(re.escape(k) for k in exact_keys)})\s*=")

        return [line.strip() for line in lines if pattern.match(line.strip())]
    return []

def extract_wifistats_19(lines, reason):
    if reason in {"data_stall", "beacon_stuck"}:

        keyword = "HTT_PDEV_STATS_CCA_COUNTERS_TLV"
        indices = [i for i, line in enumerate(lines) if keyword in line]

        if not indices:
            return []

        last_index = indices[-1]

        try:
            header_line = lines[last_index + 1]
            value_line = lines[last_index + 2]
        except IndexError:
            return []

        headers = [h.strip() for h in header_line.strip('|').split('|') if h.strip()]
        values = [v.strip() for v in value_line.strip('|').split('|') if v.strip()]

        if len(headers) != len(values):
            return []

        return [f"{key} = {value}" for key, value in zip(headers, values)]
    return []

def extract_wifistats_21(lines, reason):
    if reason in {"fail_to_connect", "client_disconnect"}:
        keywords = [
            'tx_mgmt_subtype_enq_ok:',
            'tx_mgmt_subtype_tx_comp_ok:',
            'tx_mgmt_subtype_tx_comp_fail:',
            'tx_mgmt_subtype_enq_fail:'
        ]

        return [line.strip() for line in lines if any(keyword in line for keyword in keywords)]
    return []

def extract_wifistats_30(lines, reason):
    if reason in {'data_stall'}:

        target_keys = {
            'rx_mcs_ext',
            'rx_gi_ext[0]',
            'rx_gi_ext[1]',
            'rx_gi_ext[2]',
            'rx_gi_ext[3]',
            'rx_bw'
        }

        return [line.strip() for line in lines if any(line.strip().startswith(f"{key} =") for key in target_keys)]
    return []


def extract_wifistats_40(lines, reason):
    if reason in {"data_stall", "fail_to_connect", "client_disconnect"}:

        keywords = {
            "ppdus_tried_su": None,
            "ppdus_ack_failed_su": None,
            "mpdus_tried_su": None,
            "mpdus_failed_su": None
        }

        # Track the last occurrence of each keyword
        for line in lines:
            for key in keywords:
                if line.strip().startswith(f"{key} ="):
                    keywords[key] = line.strip()

        # Filter out any that weren't found
        extracted_lines = [line for line in keywords.values() if line]

        # Calculate PER and Ack_failed_pct if all required stats are present
        if all(keywords.values()):
            def sum_values(line):
                return sum(int(part.split(':')[1]) for part in line.split('=')[1].split(',') if ':' in part)

            mpdus_tried_su_sum = sum_values(keywords["mpdus_tried_su"])
            mpdus_failed_su_sum = sum_values(keywords["mpdus_failed_su"])
            ppdus_tried_su_sum = sum_values(keywords["ppdus_tried_su"])
            ppdus_ack_failed_su_sum = sum_values(keywords["ppdus_ack_failed_su"])

            per = mpdus_failed_su_sum / mpdus_tried_su_sum if mpdus_tried_su_sum != 0 else 0
            ack_failed_pct = ppdus_ack_failed_su_sum / ppdus_tried_su_sum if ppdus_tried_su_sum != 0 else 0

            extracted_lines.append(f"PER = {per:.2f}")
            extracted_lines.append(f"Ack_failed_pct = {ack_failed_pct:.2f}")

        return extracted_lines
    return []


def extract_wifistats_47(lines, reason):
    header = "HTT_ML_PEER_DETAILS_TLV"

    target_keys = {
        "remote_mld_mac_addr",
        "ml_peer_flags",
        "num_links",
        "ml_peer_id",
        "primary_link_idx",
        "primary_chip_id",
        "link_init_count",
        "non_str",
        "is_emlsr_active",
        "is_stako",
        "num_local_links",
        "allocated",
        "emlsr_support",
        "participating_chips_bitmap",
        "status_required_bits",
    }

    extracted = []
    in_section = False

    for raw in lines:
        line = raw.strip()

        if header in line:
            extracted.append(line)
            in_section = True
            continue

        if in_section and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in target_keys:
                extracted.append(line)

        if in_section and line.endswith(":") and line.isupper() and header not in line:
            break

    return extracted


def extract_wifistats_48(lines, reason):
    if reason in {"fail_to_connect", "client_disconnect"}:

        target_keys = {"fw_tx_mgmt_subtype", "fw_rx_mgmt_subtype"}
        extracted_lines = []

        for line in lines:
            stripped_line = line.strip()
            for key in target_keys:
                if stripped_line.startswith(f"{key} ="):
                    extracted_lines.append(stripped_line)
                    break  # No need to check the other key once matched

        return extracted_lines
    return []


'''
def process_runs(folder_name, reason):
    """
    Process all wifiXwifistats# files in the given folder and call the corresponding extract_wifistats_# method.

    Parameters:
        folder_name (str): The folder containing the wifiXwifistats# files.
        reason (str): The reason for extraction (e.g., "data_stall", "beacon_stuck").
    """
    # Initialize an empty list to store the results
    results = []

    # Iterate over all files in the given folder
    for root, dirs, files in os.walk(folder_name):
        for file in files:
            # Match files with the pattern wifiXwifistats#
            match = re.match(r'wifi(\\d)+wifistats(\\d+)\\.txt', file)
            if match:
                # Extract the stat_id from the filename
                radio_id = int(match.group(1))
                stat_id = int(match.group(2))

                # Read the file content
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    lines = f.readlines()

                # Dynamically call the corresponding extract_wifistats_# method
                method_name = f'extract_wifistats_{stat_id}'
                if method_name in globals():
                    extracted_lines = globals()[method_name](lines, reason)
                    if extracted_lines:
                        results.append(f'wifi{radio_id}wifistats{stat_id}\n' + '\n'.join(extracted_lines) + '\n')

    # Return the aggregated results as a single string
    return '\n'.join(results)
'''





def process_runs(folder_name, reason):
    """
    Process WiFi wifistats from the given folder.

    Fast path:
      If 'current_wifistats.txt' exists, split it into sections on
      '=== WIFISTAT <NUMBER> ===' and call the corresponding
      extract_wifistats_<NUMBER>() for each section.

    Fallback:
      Otherwise, scan files named like 'wifi<radio_id>wifistats<stat_id>.txt'
      and call the corresponding extract_wifistats_<stat_id>() for each file.
    """
    results = []

    # --- Fast path: rate_of_change_wifistats.txt present ---
    current_stats_path = os.path.join(folder_name, 'rate_of_change_wifistats.txt')
    if os.path.isfile(current_stats_path):
        with open(current_stats_path) as f:
            all_lines = f.readlines()

        # Split into sections by '=== WIFISTAT <NUMBER> ==='
        section_pat = re.compile(r'^\s*===\s*WIFISTAT\s+(\d+)\s*===\s*$')
        sections = []  # list[(stat_id, lines)]
        current_id = None
        current_lines = []

        for line in all_lines:
            m = section_pat.match(line)
            if m:
                if current_id is not None:
                    sections.append((current_id, current_lines))
                current_id = int(m.group(1))
                current_lines = []
            else:
                if current_id is not None:
                    current_lines.append(line)

        if current_id is not None:
            sections.append((current_id, current_lines))

        for stat_id, lines in sections:
            method_name = f'extract_wifistats_{stat_id}'
            func = globals().get(method_name)
            if callable(func):
                extracted = func(lines, reason)
                if extracted:
                    results.append(f'WIFISTAT {stat_id}\n' + '\n'.join(extracted) + '\n')

        return '\n'.join(results)  # <-- fast path returns here

    # --- Fallback: per-file logic ---
    matched_any = False
    for root, dirs, files in os.walk(folder_name):
        for file in files:
            # Correct filename regex
            m = re.match(r'^wifi(\d+)wifistats(\d+)\.txt$', file)
            if not m:
                continue

            matched_any = True
            radio_id = int(m.group(1))
            stat_id = int(m.group(2))

            file_path = os.path.join(root, file)
            with open(file_path) as f:
                lines = f.readlines()

            method_name = f'extract_wifistats_{stat_id}'
            func = globals().get(method_name)
            if callable(func):
                extracted = func(lines, reason)
                if extracted:
                    results.append(
                        f'wifi{radio_id}wifistats{stat_id}\n' + '\n'.join(extracted) + '\n'
                    )

    if not matched_any:
        # Optional: make it explicit; remove if you prefer silent empty return
        print(f"[process_runs] No 'wifi<w> wifistats<n>.txt' files found in {folder_name}")

    return '\n'.join(results)  # <-- fallback always returns a string (maybe empty)




#------------------------------------------------------------------------------------------------------------------------------------


def remove_index_values_from_stats(text):
    """
    Removes '[index]:0' entries from comma-separated or space-separated statistical entries,
    while preserving '[index]:value' for non-zero values.
    Handles both '=' and ':' as delimiters.
    """
    def clean_line(line):
        if (':' in line and '=' not in line) and any(char.isdigit() for char in line):
            label, values = line.split(':', 1)
            cleaned_values = ' '.join(
                part.strip()
                for part in values.replace(',', '').split()
                if ':' in part and part.split(':')[1].strip() != '0'
            )
            return f"{label.strip()}: {cleaned_values}\n"
        elif '=' in line and ':' in line:
            label, values = line.split('=', 1)
            cleaned_values = ', '.join(
                part.strip()
                for part in values.split(',')
                if ':' in part and part.split(':')[1].strip() != '0'
            )
            return f"{label.strip()} = {cleaned_values}\n"
        return line

    return ''.join(clean_line(line) for line in text.splitlines(keepends=True))



def remove_commas(text):
    """
    Removes all commas from the input text.
    """
    return text.replace(',', '')

def remove_spaces_around_equals(text):
    """
    Removes spaces around equals signs and colons only in lines that contain index:value pairs.
    Preserves colons used in headers (e.g., 'HTT_TX_...:').
    """
    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        # Remove spaces around '='
        line = re.sub(r'\s*=\s*', '=', line)

        # Only remove spaces after colons if the line contains index:value patterns
        if re.search(r'\b\d+:\d+', line):
            line = re.sub(r'(?<=\w):\s+', ':', line)

        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines)


def remove_blank_wifistats_headers(text):
    lines = text.strip().split('\n')
    cleaned_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]
        if line.startswith('stat'):
            # Check if the next line is also a header or empty
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j >= len(lines) or lines[j].startswith('stat'):
                i = j  # Skip this header
                continue
        cleaned_lines.append(line)
        i += 1

    return '\n'.join(cleaned_lines)


def remove_equals_sign(text):
    """
    Removes '=' or ':' immediately after a label at the beginning of a line,
    while preserving colons in index:value pairs.
    """
    lines = text.strip().split('\n')
    transformed_lines = []

    for line in lines:
        original_line = line.strip()

        # Remove '=' or ':' only if it appears immediately after the label at the start
        original_line = re.sub(r'^([a-zA-Z_][\w]*)([:=])', r'\1', original_line)

        transformed_lines.append(original_line)

    return '\n'.join(transformed_lines)



def remove_htt_tx_lines(input_text):
    """
    Removes lines that start with 'HTT_TX' and end with ':' from the input text.

    Args:
        input_text (str): The original multiline text.

    Returns:
        str: The cleaned text with specified lines removed.
    """
    lines = input_text.split('\n')
    filtered_lines = [
        line for line in lines
        if not line.startswith('HTT_TX') #and line.strip().endswith(':'))
    ]
    return '\n'.join(filtered_lines)




def parse_statistical_values(input_text):
    lines = input_text.split('\n')
    values = []

    for line in lines:
        if line.lower().startswith('stat'):
            continue
        elif line.endswith(':'):
            continue
        elif re.search(r'\b\d+:\d+\b', line):
            values += [int(match.split(':')[1]) for match in re.findall(r'\b\d+:\d+\b', line)]
            match = re.search(r'\d+$', line.split(':')[0])
            if match:
                values.append(int(match.group()))
        else:
            match = re.search(r'\d+$', line)
            if match:
                values.append(int(match.group()))

    return values

def normalize_values(values):
    values = np.array(values)
    min_val = values.min()
    max_val = values.max()

    if max_val == min_val:
        return [0.0 for _ in values]

    normalized = (values - min_val) / (max_val - min_val)
    return normalized.tolist()

def replace_large_values_with_normalized(input_text):
    values = parse_statistical_values(input_text)
    normalized_values = normalize_values(values)

    value_mapping = {}
    for original, normalized in zip(values, normalized_values):
        if original > 999999:
            # Format to scientific notation and remove leading zero in exponent if present
            sci_str = f"{normalized:.2e}"
            sci_str = re.sub(r'e-0(\d)', r'e-\1', sci_str)
            value_mapping[original] = sci_str

    def replace_match(match):
        value = int(match.group())
        return value_mapping.get(value, match.group())

    cleaned_text = re.sub(r'\b\d+\b', replace_match, input_text)
    return cleaned_text

def clean_and_save_stats(text, folder_name):
    # Apply cleaning functions
    # text = remove_index_values_from_stats(text)
    # text = remove_commas(text)
    # text = remove_spaces_around_equals(text)
    # text = remove_blank_wifistats_headers(text)
    # text = remove_equals_sign(text)
    text = remove_htt_tx_lines(text)
    # text = replace_large_values_with_normalized(text)

    # Define the output file path
    output_file_path = os.path.join(folder_name, 'cleaned_stats.txt')

    # Write the cleaned text to the output file
    with open(output_file_path, 'w') as f:
        f.write(text)

    print(f"Cleaned stats have been saved to {output_file_path}")
