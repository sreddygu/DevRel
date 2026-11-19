# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

import re
import struct


def extract_and_overwrite(file_path):
    quote_pattern = re.compile(r'"(.*?)"')
    quoted_lines = []

    # Read and extract quoted strings
    with open(file_path, encoding='utf-8', errors='ignore') as file:
        for line in file:
            matches = quote_pattern.findall(line)
            quoted_lines.extend(matches)

    # Overwrite the file with each quoted string on a new line
    with open(file_path, 'w', encoding='utf-8') as file:
        for quote in quoted_lines:
            file.write(f'"{quote}"\n')

def find_error_msgs(input_file_path, regex_file_path):
    matched_lines = []

    # Load regex patterns from the pattern file
    with open(regex_file_path, encoding='utf-8') as regex_file:
        patterns = [re.compile(line.strip()) for line in regex_file if line.strip()]

    # Check each line in the input file against all regex patterns
    with open(input_file_path, encoding='utf-8', errors='ignore') as input_file:
        for line in input_file:
            if any(pattern.search(line) for pattern in patterns):
                matched_lines.append(line)

    return ''.join(matched_lines)

def clean_trailing_backslashes(file_path, output_path):
    problematic_lines = []

    with open(file_path, encoding="utf-8") as infile, \
         open(output_path, "w", encoding="utf-8") as outfile:
        for i, line in enumerate(infile, start=1):
            original = line.rstrip("\n")
            stripped = original.rstrip()
            if stripped.endswith("\\") and not stripped.endswith("\\\\"):
                problematic_lines.append((i, stripped))
                # Remove the trailing backslash and any whitespace before it
                cleaned = stripped[:-1].rstrip()
                outfile.write(cleaned + "\n")
            else:
                outfile.write(original + "\n")

    print("Lines ending with a single trailing backslash (and cleaned):")
    for line_num, content in problematic_lines:
        print(f"Line {line_num}: {content}")

# Example usage
# clean_trailing_backslashes("debug_logs/msg_error_python.txt", "debug_logs/msg_error_python_cleaned.txt")


def find_trailing_backslashes(file_path):
    problematic_lines = []
    with open(file_path, encoding="utf-8") as file:
        for i, line in enumerate(file, start=1):
            stripped = line.rstrip("\n").rstrip()
            # Check if it ends with a single backslash
            if stripped.endswith("\\") and not stripped.endswith("\\\\"):
                problematic_lines.append((i, stripped))

    print("Lines ending with a single trailing backslash:")
    for line_num, content in problematic_lines:
        print(f"Line {line_num}: {content}")







def parse_hostapd_logs(file_path, reason):
    with open(file_path) as file:
        lines = [line.strip() for line in file.readlines()]

    events = []
    disassoc_macs = []

    # --- First Pass: Collect all disassociated MAC addresses ---
    for line in lines:
        disassoc_match = re.search(r'daemon\.info hostapd: .*STA ([0-9a-f:]+) IEEE 802\.11: disassociated', line)
        disassoc_match_2 = re.search(r'mld0: STA ([0-9a-f:]+) IEEE 802\.11: disassociated', line)
        if disassoc_match:
            mac = disassoc_match.group(1)
            disassoc_macs.append(mac)
            event_type = 'Disassociation' if reason == 'client_disconnect' else 'Fail to Connect'
            detail = f'STA {mac} disconnected from AP' if reason == 'client_disconnect' else f'STA {mac} fail to connect to AP'
            log_match = disassoc_match.group(0)

            existing_event = next((e for e in events if e['MAC Address'] == mac and e['Log Match'] == log_match), None)
            if existing_event:
                existing_event['Line'] += f"\n{line}"
            else:
                events.append({
                    'MAC Address': mac,
                    'Event': event_type,
                    'Details': detail,
                    'Log Match': log_match,
                    'Line': line
                })
        elif disassoc_match_2:
            mac = disassoc_match_2.group(1)
            disassoc_macs.append(mac)
            event_type = 'Disassociation' if reason == 'client_disconnect' else 'Fail to Connect'
            detail = f'STA {mac} disconnected from AP' if reason == 'client_disconnect' else f'STA {mac} fail to connect to AP'
            log_match = disassoc_match_2.group(0)

            existing_event = next((e for e in events if e['MAC Address'] == mac and e['Log Match'] == log_match), None)
            if existing_event:
                existing_event['Line'] += f"\n{line}"
            else:
                events.append({
                    'MAC Address': mac,
                    'Event': event_type,
                    'Details': detail,
                    'Log Match': log_match,
                    'Line': line
                })

    # --- Second Pass: For each MAC, scan the entire log for related events ---
    for mac_address in disassoc_macs:
        for line in lines:
            # STA Initiated Disconnect
            sta_initiate_match = re.search(rf'\[{mac_address}\]Received Deauth with reason (\d+)', line)
            if sta_initiate_match:
                reason_code = sta_initiate_match.group(1)
                log_match = sta_initiate_match.group(0)
                existing_event = next((e for e in events if e['MAC Address'] == mac_address and e['Log Match'] == log_match), None)
                if existing_event:
                    existing_event['Line'] += f"\n{line}"
                else:
                    events.append({
                        'MAC Address': mac_address,
                        'Event': 'STA Initiated Disconnection',
                        'Details': f'STA has initiated disconnection from the AP with Deauth reason {reason_code}',
                        'Log Match': log_match,
                        'Line': line
                    })
                continue

            # AP Kickout - Reason Code
            ap_kickout_match = re.search(
                rf'sending\s+DISASSOC\s+to\s+{mac_address},\s+mlme\s+disassoc\s+reason\s+(\d+)', line)
            if ap_kickout_match:
                reason_code = ap_kickout_match.group(1)
                events.append({
                    'MAC Address': mac_address,
                    'Event': 'AP Kickout',
                    'Details': f'An external system has issued a command that makes the AP kick out STA {mac_address}.',
                    'Log Match': ap_kickout_match.group(0),
                    'Line': line
                })
                continue

            # AP Kickout - Excessive Retries
            if 'station kicked out due to excessive retries associd' in line:
                events.append({
                    'MAC Address': mac_address,
                    'Event': 'AP Kickout',
                    'Details': f'AP kick out STA {mac_address} due to excessive retries',
                    'Log Match': line,
                    'Line': line
                })
                continue

            # Hostapd Disconnect
            hostapd_disconnect_match = re.search(rf'ap_sta_disconnect (STA|addr) {mac_address} reason=', line)
            if hostapd_disconnect_match:
                events.append({
                    'MAC Address': mac_address,
                    'Event': 'Fail to Connect',
                    'Details': f'Hostapd Initiated Disconnect - STA {mac_address} Fail to Connect to AP due to hostapd initiated disconnect',
                    'Log Match': hostapd_disconnect_match.group(0),
                    'Line': line
                })
                continue

    # --- Third Pass: Capture all lines with 'reason' or 'Reason' ---
    deauth_patterns = [
        r'Deauth with reason \d+', #generic
        r'Deauthenticating Station .* Reason: .* \(\d+\)', #cisco
        r'deauth: reason=\d+', #ubiquiti
        r'deauthenticated .* \(Reason: \d+=.*\)' #linux
    ]

    combined_pattern = re.compile('|'.join(deauth_patterns), re.IGNORECASE)
    matched_lines = [line for line in lines if combined_pattern.search(line)]

    if matched_lines:
        events.append({
            'MAC Address': 'Unknown',
            'Event': 'Deauth Reason Codes',
            'Details': 'Syslog lines containing deauthentication reason codes',
            'Log Match': 'deauth reason',
            'Line': '\n'.join(matched_lines)
        })



    # --- Fourth Pass: Check fail-to-connect reasons that don't require disassociation ---
    fail_patterns = [
    (r'SAE: Confirm mismatch', 'Fail to Connect', 'wrong password'),
    (r'the peer count exceeds the configured number', 'Fail to Connect', 'max clients reached'),

    # client protocol mismatch
    # (r'MLD: Error in max simultaneous links, advertised: 0x[0-9a-fA-F]+ current: 0x[0-9a-fA-F]+', 'Fail to Connect', f'mismatch in MLD capabilities between client and AP'),
    # (r'nl80211: key_mgmt_suites=0x[0-9a-fA-F]+', 'Fail to Connect', f'PMF capability mismatch between client and AP'),

    # ASSOC failures
    (r'wrong bssid', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to wrong BSSID'),
    (r'Dropping Assoc req frame because ML-IE is (included for Non-MLO peer|not included for MLO peer)', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to MLO Assoc failure'),
    (r'reached the end of frame|recv another assoc frame when previous is in progress|Dropping Assoc when previous assoc is in progress', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to protocol parsing failure'),
    (r'Assoc request rejected as Channel switch is in progress', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to assoc request received when channel-switch in progress'),
    (r'Invalid WPA key mgmt', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to AKM is not supported'),
    (r'RSN: Trying to use non-FT AKM suite, but MDIE included', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to STA uses non-FT AKM but includes MDIE in its Ies'),
    (r'OWE: No Diffie-Hellman Parameter element', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to STA uses OWE AKM, but DH IE is not in the STA IE list'),
    (r'Invalid WPA group cipher', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to group cipher is not supported'),
    (r'Invalid RSN pairwise cipher', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to pairwise cipher is not supported'),
    (r'Management frame protection required(, but client did not enable it| with SAE, but client did not enable it)', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to hostapd conf demands MFP –Required but STA is not MFP-Capable'),
    (r'Management frame protection cannot use TKIP', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to Management frame protection gets enabled, but STA has TKIP in its pairwise cipher list'),
    (r'Unsupported management group', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to the management group cipher does not match the configured group (usually WPA_CIPHER_AES_128_CMAC by default)'),
    (r'RSN: Trying to use FT, but MDIE not included', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to FT is supported by STA, but MDIE is not included in its IEs'),
    (r'RSN: Attempted to use unknown MIDE', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to FT is supported by STA, but MDIE not matching the configured value'),
    (r'No PMKSA cache entry found', 'Fail to Connect', 'Assoc Failure - Fail to Connect to AP due to PMKID sent by STA is not found in the hostap PMK cache'),

    # Split EAPOL Handshake Failures
    (r'Ignore EAPOL-Key with unexpected type \d+ in RSN mode', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to EAPOL uses WPA-IE instead of RSN IE'),
    (r'RSN: AES unwrap failed', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to KEY data decryption failure'),
    (r'received EAPOL-Key msg \d+/\d+ in invalid state', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to EAPOL received in wrong state'),
    (r'WPA IE from \(Re\)AssocReq did not match with msg \d+/\d+', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to WPA IE mismatch'),
    (r'RSN: MLD: Invalid MLD address', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to invalid mac address in MAC KDE'),
    (r'RSN: MLD: Invalid link ID', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to invalid link ID in one of the Link KDEs'),
    (r'RSN: MLD: invalid MAC address', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to invalid link ID in one of the Link KDEs'),
    (r'RSN: MLD: Expecting \d+ MLD links in msg \d+, but got', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to number of link KDEs not matching the number of links from assoc request'),
    (r'invalid MIC in msg \d+/\d+ of 4-Way Handshake', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to invalid MIC in M2'),
    (r'RSN Selection element from \(Re\)AssocReq did not match the one in EAPOL-Key msg \d+/\d+', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to RSN Override selection mismatch between assoc request and M2'),
    (r'received EAPOL-Key msg \d+/\d+ with invalid Key Data contents', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to KDE parse error'),
    (r'MLD: Mismatching or missing MLD address in EAPOL-Key msg \d+/\d+', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to Invalid MAC address in MAC KDE'),
    (r'IEEE 802.1X data frame from not associated', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to STA is not in associated state when EAPOL is received (may not be very likely)'),
    (r'RSNXE from (Re)AssocReq did not match the one in EAPOL-Key msg 2/4', 'Fail to Connect', 'EAPOL Handshake Failure - Fail to Connect to AP due to RSNXE mismatch between assoc-req and M2'),

    # Auth protocol parsing failures
    (r'invalid seq seq num: \d+ not supported for algo 0x\d+', 'Fail to Connect', 'Protocol Parsing Failure in Auth - Fail to Connect to AP due to invalid auth sequence number'),
    (r'shared key auth ie too long', 'Fail to Connect', 'Protocol Parsing Failure in Auth - Fail to Connect to AP due to shared key auth IE is too long'),
    (r'shared key auth no challenge', 'Fail to Connect', 'Protocol Parsing Failure in Auth - Fail to Connect to AP due to challenge is not included in auth req'),
    (r'Err:Invalid algorithm:', 'Fail to Connect', 'Protocol Parsing Failure in Auth - Fail to Connect to AP due to received auth request with invalid algorithm'),
    (r'Err: auth_cnt \d+ bigger than max_auth \d+', 'Fail to Connect', 'Protocol Parsing Failure in Auth - Fail to Connect to AP due to auth flood issue'),
    (r'Err:VAP 0 in CSA', 'Fail to Connect', 'Protocol Parsing Failure in Auth - Fail to Connect to AP due to received auth request while CSA is in progress'),

    #Auth response delayed
    (r'defer AUTH for:', 'Fail to Connect', 'Auth Response Delayed - Fail to Connect to AP due to auth response delayed'),

    #SAE Exchange Failure
    (r'SAE: Unexpected Status Code', 'Fail to Connect', 'SAE Exchange Failure - Fail to Connect to AP due to SAE Commit not being the first message from STA'),
    (r'SAE: Silently ignore unexpected Confirm from peer', 'Fail to Connect', 'SAE Exchange Failure - Fail to Connect to AP due to SAE Confirm received in the wrong state -> drop the auth request without any response'),

    # Blacklist
    # (r'STA is in black list', 'Fail to Connect', f'Access Control - Fail to Connect to AP due to STA being in black list'),

    # FT Roaming failures
    (r'FT: Failed to parse FT IEs', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to Failed to parse FT IEs'),
    (r'FT: No RSNIE in Reassoc Req', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to No RSNIE present in FT Reassoc frame'),
    (r'FT: Invalid MDIE', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to MDIE not present or invalid'),
    (r'FT: Invalid FTIE', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to FTIE not present or invalid'),
    (r'FT: Invalid FTIE - no R0KH-ID', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to R0KH missing in FTIE'),
    (r'FT: No PMKID in RSNIE', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to PMKID missing in RSNIE'),
    (r'FT: Invalid key mgmt', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to Invalid AKM or cipher in the FT Auth RSNIE'),
    (r'FT: Invalid pairwise cipher', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to Invalid AKM or cipher in the FT Auth RSNIE'),
    (r'FT: SNonce mismatch', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to FT ANONCE mismatch'),
    (r'FT: ANonce mismatch', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to FT SNONCE mismatch'),
    (r'FT: No R0KH-ID subelem in FTIE', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to R0KH missing'),
    (r'FT: R0KH-ID in FTIE did not match with the current R0KH-ID', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to R0KH mismatch with FT-Auth'),
    (r'FT: No R1KH-ID subelem in FTIE', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to R1KH missing'),
    (r'FT: Unknown R1KH-ID used', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to R1KH mismatch'),
    (r'FT: No matching PMKR1Name \(PMKID\)', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to PMKID missing or mismatch'),
    (r'FT: Invalid MIC in FTIE', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to Invalid FTIE MIC'),
    (r'FT: Unexpected IE count in MIC', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to FTIE MIC element count mismatch'),
    (r'FT: FTE indicated that STA uses RSNXE, but RSNXE was not included', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to RSNX expected but not found in FT Reassoc'),
    (r'PMKR1Name mismatch in FT 4-way handshake', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to PMKR1Name does not match any of the PMKIDs used in M2 RSNIE'),
    (r'FT: No FTIE in FT 4-way handshake message \d+/\d+', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to MDIE or FTIE not present in M2'),
    (r'FT: No MDIE in FT 4-way handshake message \d+/\d+', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to MDIE or FTIE not present in M2'),
    (r'FT: MDIE mismatch', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to MDIE mismatch between AP and STA'),
    (r'FT: FTIE mismatch', 'Fail to Connect', 'FT Roaming Failure - Fail to Connect to AP due to FTIE mismatch between Assoc request and M2'),
    ]



    for line in lines:
        for pattern, event_type, detail in fail_patterns:
            if re.search(pattern, line):
                log_match = pattern
                existing_event = next((e for e in events if e['Log Match'] == log_match and e['Event'] == event_type and e['Details'] == detail), None)
                if existing_event:
                    existing_event['Line'] += f"\n{line}"
                else:
                    events.append({
                        'MAC Address': 'Unknown',
                        'Event': event_type,
                        'Details': detail,
                        'Log Match': log_match,
                        'Line': line
                    })
                break

    return events



def extract_deauth_reason_definitions(log_text):
    # Mapping of reason codes to definitions
    reason_definitions = {
        0: "Reserved",
        1: "Unspecified reason",
        2: "Previous authentication no longer valid",
        3: "station is leaving (or has left) IBSS or ESS",
        4: "Disassociated due to inactivity",
        5: "Disassociated because AP is unable to handle all currently associated stations",
        6: "Class 2 frame received from nonauthenticated station",
        7: "Class 3 frame received from nonassociated station",
        8: "Disassociated because sending station is leaving (or has left) BSS",
        9: "Station requesting (re)association is not authenticated with responding station",
        10: "Disassociated because the information in the Power Capability element is unacceptable",
        11: "Disassociated because the information in the Supported Channels element is unacceptable",
        12: "Reserved",
        13: "Invalid information element, i.e., an information element defined in this standard for which the content does not meet the specifications in Clause 7",
        14: "Message integrity code (MIC) failure",
        15: "4-Way Handshake timeout",
        16: "Group Key Handshake timeout",
        17: "Information element in 4-Way Handshake different from (Re)Association Request/Probe Response/Beacon frame",
        18: "Invalid group cipher",
        19: "Invalid pairwise cipher",
        20: "Invalid AKMP",
        21: "Unsupported RSN information element version",
        22: "Invalid RSN information element capabilities",
        23: "IEEE 802.1X authentication failed",
        24: "Cipher suite rejected because of the security policy",
        32: "Disassociated for unspecified, QoS-related reason",
        33: "Disassociated because QAP lacks sufficient bandwidth for this QSTA",
        34: "Disassociated because excessive number of frames need to be acknowledged, but are not acknowledged due to AP transmissions and/or poor channel conditions",
        35: "Disassociated because QSTA is transmitting outside the limits of its TXOPs",
        36: "Requested from peer QSTA as the QSTA is leaving the QBSS (or resetting)",
        37: "Requested from peer QSTA as it does not want to use the mechanism",
        38: "Requested from peer QSTA as the QSTA received frames using the mechanism for which a setup is required",
        39: "Requested from peer QSTA due to timeout",
        40: "Peer QSTA does not support the requested cipher suite",
        98: "Cisco defined",
        99: "Cisco defined - Used when the reason code sent in a deassoc req or deauth by the client is invalid – invalid length, invalid value etc"
    }

    # Patterns to match reason codes in various formats
    patterns = [
        r'Deauth with reason (\d+)',
        r'Deauthenticating Station .* Reason: .*?\((\d+)\)',
        r'deauth: reason=(\d+)',
        r'deauthenticated .* \(Reason: (\d+)=',
        r'Received Deauth with reason (\d+)',
        r'reason_code=(\d+)'
    ]

    matched_reasons = set()

    for line in log_text.splitlines():
        for pattern in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                code = int(match.group(1))
                matched_reasons.add(code)

    # Format the output
    results = []
    for code in sorted(matched_reasons):
        if code in reason_definitions:
            results.append(f"reason {code}: {reason_definitions[code]}")
        elif 25 <= code <= 31 or 46 <= code <= 65535:
            results.append(f"reason {code}: Reserved")
        else:
            results.append(f"reason {code}: Unknown reason code")

    return results











def convert_syslog_to_pcap(syslog_path, output_pcap_path):
    def hex_string_to_bytes(hex_string):
        return bytes(int(b, 16) for b in hex_string.strip().split())

    def write_pcap_global_header(f):
        # PCAP Global Header for little-endian, Ethernet, no time zone adjustment
        f.write(struct.pack('<IHHIIII',
                            0xa1b2c3d4,  # magic number
                            2, 4,        # version major, minor
                            0, 0,        # thiszone, sigfigs
                            65535,       # snaplen
                            1))          # network (Ethernet)

    def write_pcap_packet(f, ts_sec, ts_usec, packet_bytes):
        length = len(packet_bytes)
        f.write(struct.pack('<IIII', ts_sec, ts_usec, length, length))
        f.write(packet_bytes)

    def parse_frame_bytes(frame_str, direction):
        byte_array = frame_str.strip().split()
        if len(byte_array) < 4:
            return None
        # Modify duration field (3rd and 4th bytes)
        byte_array[2] = '02' if direction == 'cmd' else ('03' if direction == 'txstatus' else '01')
        byte_array[3] = '00'
        if direction == 'rx':
            byte_array[1] = f"{int(byte_array[1], 16) & 0xBF:02x}"
        return hex_string_to_bytes(' '.join(byte_array))

    with open(syslog_path) as f:
        lines = f.readlines()

    packets = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if 'MLME event frame' in line:
            match = re.search(r'^(\d+)\.(\d+).*MLME event frame - hexdump\(len=\d+\): (.*)', line)
            if match:
                ts_sec, ts_usec, frame_data = int(match[1]), int(match[2]), match[3]
                tx_status = 'txstatus' if i + 1 < len(lines) and 'Frame TX status' in lines[i + 1] else 'rx'
                packet = parse_frame_bytes(frame_data, tx_status)
                if packet:
                    packets.append((ts_sec, ts_usec, packet))
        elif 'CMD_FRAME - hexdump' in line:
            match = re.search(r'^(\d+)\.(\d+): CMD_FRAME - hexdump\(len=\d+\): (.*)', line)
            if match:
                ts_sec, ts_usec, frame_data = int(match[1]), int(match[2]), match[3]
                packet = parse_frame_bytes(frame_data, 'cmd')
                if packet:
                    packets.append((ts_sec, ts_usec, packet))
        i += 1

    with open(output_pcap_path, 'wb') as f:
        write_pcap_global_header(f)
        for ts_sec, ts_usec, packet in packets:
            write_pcap_packet(f, ts_sec, ts_usec, packet)

    print(f"PCAP file saved to {output_pcap_path}")
