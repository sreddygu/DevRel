# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

# assets.pyx
# -----------
# Cython source file that embeds IP text assets as compiled string constants.
# This file is compiled to a native .so extension during the Docker build.
# The .pyx source and the original .txt files are NOT present in the final image.
#
# Build with:
#   python setup_assets.py build_ext --inplace

KNOWLEDGE_BASE = r"""# Connectivity


## 1. Scan

### 1. No or long interval Beacon from AP

- Beacon stuck

- Delayed Beacon Tx



### 2. No Probe Response

- Beacon drop

- Delayed channel access


### 3. ML Probe discovery


### 4. MBSSID scan fail

1. Fail to scan Tx+IAP

2. Fail to scan Non‑Tx+IAP

3. Out of band scan fail



### 5. 5.8G band scan fail

1. In‑band scan fail

2. Out‑of‑band scan fail

3. AP's Beacon and FILS tx behavior

4. STA's probe request behavior




## 2. Authentication

1. No Auth Response (Drop Auth Request)

2. Auth Resp with fail status code




## 3. Association

1. No Assoc Resp (Drop Assoc Request)

2. Assoc Resp with fail code





## 4. 4‑Way Handshaking

1. Handshake timeout

2. No Tx EAPOL – M1/M3

3. No Rx EAPOL – M2/M4





## 5. Connection Stability

### 1. Tx path stability

- Tx stuck

- Tx packet drop




### 2. Rx path stability

- Rx stuck

- Rx packet drop




## 6. Roaming

1. Inter‑band roaming

2. Inter‑AP roaming

3. MLO self‑roaming

4. 802.11 vk



## 7. Disconnection

### 1. Disconnection initiated by AP

- Kickout STA

  - Inactive timeout

  - Excessive retry

  - Not awake from PS mode

  - Unknown reason

- Key update fail

- Disconnected after CSA




### 2. Disconnection initiated by STA

- Beacon miss

- Excessive retry

- DHCP fail


## 8. Start‑up Failure

1. Bootloader failure

2. Modem load failure

3. Interface up failure


Connection steps

Issue symptom

Mandatory log list

 SCAN

STA fails to discover AP

AP is not in the scan list of STA

STA doesn't start Authentication while keep repeating Probe Req

WiFi FW Logs

wifistats wifiX 1: Stats about AMSDUs, AMPDUs posted, flush errors, phy errors.

wifistats wifiX 2: Stats about RX related information.

wifistats wifiX 3: Stats about HWQ, HW sched_cmd results.

wifistats wifiX 4: Stats about scheduler.

wifistats wifiX 5: Stats about HW WARs, warm resets.

wifistats wifiX 5 --wmi: online cal status

wifistats wifiX 6: Stats about TQM.

wifistats wifiX 8: Stats about TCL/EAPOL/DHCP.

wifistats wifiX 9: Stats about TX MPDUs, MCS, NSS, BW.

wifistats wifiX 10: Stats about RX MPDUs, MCS, NSS, BW.

wifistats wifiX 19: Stats about CCA histogram

wifistats wifiX 20: Stats about pdev level beacon stats

wifistats wifiX 24: Ring backpressure histogram per HW ring.

wifistats wifiX 37: Packet dropped in PHY

cnss_diag -pc | grep -e MGMT_TXRX -e KICKOUT -e VDEV_MGR_AP_KEEPALIVE -e CONN_DBG -e BEACON -e security -e EAPOL

Host Logs

cfg80211tool athx / mldx link_id x csl 1

cfg80211tool athx dbgLVL 0x80c00000 : for MLME (auth/assoc/deauth/disassoc)

cfg80211tool athx dbgLVL_high 0x60000 : for eapol/peer create/delete

cfg80211tool athX qdf_cv_lvl 0x1f000a : mlme cmds

cfg80211tool athX qdf_cv_lvl 0x67000a : VDEV SM

cfg80211tool athx / mldx link_id x txrx_stats 260

cfg80211tool athx / mldx link_id x txrx_stats 261

apstats -v -i  athX / mldx -L x

apstats -r -i wifiX

Hostapd Logs

Supplicant logs if STA is WDS; windows based 3rd party client (netsh wlan show wlanreport)

Packet Logs

pktlogconf -r wifi$a

pktlogconf -a wifi$a -elite,rcu,rcf -s 30000000;

sleep 1000; pktlogconf -d wifi$a;

cp /proc/ath_pktlog/wifi$a /tmp/xx.dat

Sniffer Logs

Mandatory log capture script :

Debug script

Auth/Assoc

Fails to complete Auth/Assoc procedure

No Auth/Assoc response from AP

Fail/Error status code in Auth/Assoc Resp.

4-way handshake

AP fails Key install

No EAPOL message to (M1,M3) / from (M2, M4) STA

Fail to install PTK/GTK after M3 message from STA

Connection stability

Unreliable data communication between AP and STA

AP Tx/Rx stuck

High tx retry

specific packet drop

Roaming

Roaming is not happen or failed

Roaming is not triggered

Deauth/disassoc at target band/AP

Disconnection

WiFi link is disconnected unexpectedly

STA leave AP by sending deauth/disassoc message

AP kick out STA by sending deauth/disassoc message

For DogFood issues, we will be collecting limited logs - Dogfooding Logs across Subsystem - UX - Qualcomm Confluence

1. Scan issue

Scan issue

Issue Symptom

No/Long interval Beacon

No AP beacon during STA's dwell time in AP channel

In sniffer, observe no beacon or  interval > 100ms

Trace Beacon Tx stats with wifistats 19/20 to see continuous beacon drop/stuck and on VAP and PDEV

wifistats wifiX 19 --vdevid <vdev_id> <optional_arg> --wmi /* for per VAP*/

wifistats wifiX 20 <optional_arg> --wmi /*for per radio */

No Probe response from AP

No AP Probe resp during STA's dwell time in AP channel

In sniffer, observe no probe resp or  delayed probe resp

Trace Probe req/resp message flow

lite_mon wifi0 -filter_mo 0x00030 (Filter both probe request and probe response frames of type monitor other)

ML Probe discovery

Not able to discover partner link

MLO_MGR, MLOIE, and SCM level debugs with wpa_supplicant debug logs along with configs (wireless and INI) will be required for initial triage.

Wireless config.

Debug log of wpa_supplicant.

Console logs with MLO_MGR and MLOIE level debugs enabled (pertaining logs will have "ML Probe:" prefix).

Output of cat /proc/wifiX/ic_config (to verify the Multi-link Probe response update time).

The driver logs will have the prefix "ML Probe:" to them, and the logs are added in respective modules. Supplicant debug logs have "ML_STA:" and "MLD:" prefix added to them.

MBSSID Scan fail

Tx-VAP or Non Tx-VAP scan fail

No issue with beacon and probe resp interval, but not able to discover non Tx-vap

6G Band Scan fail

STA fails to discover 6G VAP during OOB and inband scan

Check if Probe resp, FILS, Beacon in 6G channel tx count is normal

apstats -r -i wifi0 : MBSSID/EMA_AP stats and RNR stats

apstats -v -i ath0 : Offload probe response, FILS, Beacon stats, Probe request stats

1.1. No/Long interval beacon

Beacon issue

Issue Symptom & Triage

Beacon Stuck

Beacon offload Tx procedure

Host driver -> <beacon template> -> FW -> <rx SWBA interrupt-> form Beacon based on template + populates time related field -> enqueue beacon to HWQ> -> HW -> Tx beacon at TBTT -> FW -> HW ...

Check if Beacon success count keep increasing at VAP level

with apstats -v -i athx | grep Beacon

Beacon success                  = 0

Beacon failed                   = 9011

If beacon stop is observed, check beacon HWQ stats to understand beacon tx failure reason

wifistats wifi0 3 1

HTT_TX_HWQ_STATS_CMN_TLV:

mac_id = 0

hwq_id = 0                      ---- > Beacon HWQ

xretry = 0

underrun_cnt = 0

flush_cnt = 41              ----> Beacon Flush Count incremented due to flush error

filt_cnt = 1

HTT_TX_HWQ_CMD_RESULT_STATS_TLV_V:

cmd_result =  0:755, 1:0, 2:0, 3:1, 4:0, 5:0, 6:0, 7:41, 8:0, 9:0, 10:0, 11:0, 12:0,

0 : Tx Success count at HWQ id 0

7 : Tx Fail count with reason 7 meaning failed due to flush error

in case of flush error, need to understand specific flush error reason based on wifistats 1

wifistats wifi0 1

HTT_TX_PDEV_STATS_FLUSH_TLV_V:

flush_errs =  0:0, 1:0, 2:0, 3:0, 4:0, 5:354, 6:61, 7:8, 8:0, 9:0, 10:0, 11:0, 12:0, 13:0, 14:0, 15:0, 16:0, 17:0, 18:0, 19:0, 20:0, 21:0, 22:0, 23:0, 24:0, 25:0, 26:0, 27:0, 28:0,
29:0, 30:0, 31:0, 32:0, 33:0, 34:0, 35:0, 36:0, 37:0, 38:2, 39:0, 40:0, 41:0, 42:0, 43:0, 44:0, 45:0, 46:0, 47:0, 48:0, 49:0, 50:0, 51:0, 52:80, 53:0, 54:0, 55:0

If the beacon count is not increasing at any result reason codes , need to investigate why the beacon is not being generated.

wifistats wifi0 19/20 --wmi (19 : for per VAP, 20: for per Radio)

Delayed Beacon Tx

If beacon delay is observed, check radio fw stats to understand beacon tx drop due to expiration to send over the air

wifistats wifi0 3

HTT_TX_HWQ_CMD_RESULT_STATS_TLV_V:

cmd_result =  0:755, 1:0, 2:0, 3:1, 4:0, 5:0, 6:0, 7:41, 8:0, 9:0, 10:0, 11:0, 12:0,

3 : Tx Fail due to life span expiry at HWQ id 0 which means HW has been holding beacons for 50ms then unable to send them

Exam if Channel access delay is causing beacon tx expiration or latency

Check CCA threshold value by reading register

athdiag --wifi 2 --get --address=0x500158 -quiet (in WKK case)

Try with other CCA threshold value to see if issue symtom is changed

cfg80211tool wifi0 cca_threshold xx_dbm

or, in BDF, adjust AGC_CCA_DETECT_THRESHOLD_5G.agcCcaEnergyThr[0].xxx

Check if phy reset keeps increasing and it's impacting on beacon latency

wifistats wifiX 5 | grep phy_warm_reset

phy_warm_reset = 37

phy_warm_reset_reason_num_cca_rx_frame_stuck = 0
phy_warm_reset_reason_wal_rx_recovery_rst_rx_busy = 37

Trace Beacon tx status and timestamp in detail

cnss_diag -c -p | grep -e "BEACON TX" -e "MGMT_TXRX_SENT_FROM_LOCAL" -e "WOW_BEACON_OFFLOAD_TX"

2. Authentication

Auth/Assoc issue

issue triage

No Auth/Assoc Response

Check if hostapd received auth/assoc req and sent response to driver

hostapd -g /var/run/hostapd/global -ddd -P /var/run/hostapd-global.pid -f /tmp/hostapd.log&

Trace host driver and FW auth/assoc message exchange status

Host driver trace log : cfg80211tool athx csl 1

FW trace log : cnss_diag -c | grep "CONN_DBG"

if hostapd doesn't receive request or sent response but not seen in the air, check if FW received Auth/assoc frame

Rx side : wifistats wifi0 2 |grep fw_ring_mgmt_subtype
fw_ring_mgmt_subtype =  0:0, 1:0, 2:0, 3:0, 4:11003, 5:15, 6:0, 7:0, 8:270646, 9:0, 10:0, 11:0, 12:0, 13:1, 14:0, 15:0,

Tx side : wifistats wifi0 1 |grep fw_tx_mgmt_subtype
fw_tx_mgmt_subtype =  0:0, 1:0, 2:0, 3:0, 4:0, 5:2746, 6:0, 7:0, 8:76531, 9:0, 10:0, 11:0, 12:19, 13:457, 14:0, 15:0

Auth/Assoc Res with Fail code

2.1. No Auth Response (Drop Auth Request)

No Auth Response issues

Parsing Failure in Auth request

In case of WEP, there is some case for AP to drop Auth request due to some parsing failure with

Invalid Auth sequence number

SEQ in WEP authentication should be one of 4

Auth request IE is too long

If the encrypted Challenge is not included in Auth request (SEQ=3)

AP policy to drop Auth request

MAX Client reached

MAX_CLIENT varies and is dependent on the platform and radio. Auth request dropped by driver without any response. Hostapd also would not receive this frame

console log in failure case :

"the peer count exceeds the configured number"

Auth flooding attack

Auth request would be dropped when there is DoS attack with Auth req frame In one second duration, if AP receives more than 32 auth requests, subsequent auth requests would be dropped for 1 sec.

console log in failure case :

"Err: auth_cnt 32 bigger than max_auth 32"

2.2. Auth Response with fail status code

Auth response with fail status code issue

Auth Req with invalid Algorithm

"Authentication Algorithm" in request should be one below list otherwise AP sends Auth response with fail status code

Auth reject during CSA

When receving Auth request in CSA procedure, AP send Auth response with fail status code

Auth Response status code : IEEE80211_STATUS_REJECT_TEMP (30)

ACL Rejection

Current Policy - ACCEPT or DENY

Auth Response status code : IEEE80211_STATUS_REFUSED (37)

SAE exchange fail case

Fail in SAE commit

Password mismatch can cause failure

SAE COMMIT not the first message from STA "SAE: Unexpected Status Code"

Auth Response Status code- WLAN_STATUS_UNSPECIFIED_FAILURE (0x1)

SAE commit need to have 0x7e as status code for MLO (H2E)

Not having H2E may result in ML-IE parsing failure

SAE COMMIT Parse failure

Auth Response Status code - WLAN_STATUS_UNSPECIFIED_FAILURE (0x1)

SAE Group not supported

Auth Response Status code - WLAN_STATUS_FINITE_CYCLIC_GROUP_NOT_SUPPORTED

SAE Reflection Attack

Drop Auth request without sending Auth-response (SAE_SILENTLY_DISCARD)

Anti-clogging token required

WLAN_STATUS_ANTI_CLOGGING_TOKEN_REQ

Fail in SAE confirm

SAE CONFIRM received in the wrong state

Drop the auth request without any response

"SAE: Silently ignore unexpected Confirm from peer"

Wrong SAE password

Auth response sent with status code WLAN_STATUS_CHALLENGE_FAIL (0xf)

AKM not supported

Auth frame from STA indicates algorithm type

Usual Supported types

AKM - 0(open), 2(FT), 3(SAE) etc..

The AKM type in the auth request frame should be among the list of AKMs in the "wpa_key_mgmt." entry in the hostapd conf file.

Wpa_key_mgmt is populated based on the combination of values in "encryption", "sae", "wpa_key_mgmt" entries in /etc/config/wireless

Status-code 13 (UNSUPPORTED_AUTH_ALGORITHM) would be sent in case of unsupported AKM

In case of SAE if transaction is anything other than "commit" or "confirm" from the STA, It would result in TRANSACTION_SEQUENCE_ERROR (status-code=14)

3. Association

3.1. No Assoc Response (Drop Assoc Request)

Assoc request drop case

Assoc frame received with wrong BSSID - "wrong bssid"

Station already associated as non-ML received the (re)assoc with ML capabilities and PMF not enabled in the existing STA - "Dropping Assoc req frame because ML-IE is included for Non-MLO peer"

Station already associated as ML STA, but received (re)assoc with no ML-IE - "Dropping Assoc req frame because ML-IE is not included for MLO peer"

Assoc request length does not match the cumulative lengths reported by the IEs - "reached the end of frame"

Assoc request received while previous assoc request still being processed - "recv another assoc frame when previous is in progress"

3.2. Assoc response with Error status code

Assoc frame received without Auth - IEEE80211_REASON_ASSOC_NOT_AUTHED (9)

Supported capability mismatch

'pure11n' is enabled and Assoc frame received with no HT-CAPS - IEEE80211_STATUS_NO_HT (27)

'pure11ac' is enabled and assoc frame received with no VHT-CAPS - IEEE80211_STATUS_NO_VHT(104)

'pure11ax' is enabled and assoc frame received with no HE-CAPS - IEEE80211_STATUS_NO_VHT(104)

Supported rates mismatch or not meeting VAP configured requirements - IEEE80211_STATUS_BASIC_RATE (18)

Short slot time capability mismatch between STA and AP - IEEE80211_STATUS_CAPINFO (10)

VAP invalid state or not meeting configured requirements

Assoc request received when channel-switch in progress - IEEE80211_STATUS_REJECT_TEMP (30)

Assoc request on 6GHz received with lower than threshold RSSI - IEEE80211_STATUS_POOR_CHAN_CONDITION (34)

ACL Rejection (configured in hostapd conf) - WLAN_STATUS_UNSPECIFIED_FAILURE (1)

Invalid RSN-IE or violation

MFP Violation - mismatch between AP and STA's MFP requirement/capability - IEEE80211_STATUS_MFP_VIOLATION (31)

Assoc request received without RSNIE when VAP configured for security - IEEE80211_STATUS_INVALID_RSNE_CAP (45)

if AKM is not supported - WLAN_STATUS_AKMP_NOT_VALID (43)

if Group cipher is not supported - WLAN_STATUS_GROUP_CIPHER_NOT_VALID (41)

if Pairwise cipher is not supported - WLAN_STATUS_PAIRWISE_CIPHER_NOT_VALID (42)

if hostapd conf demands MFP Required but STA is not MFP-Capable - WLAN_STATUS_ROBUST_MGMT_FRAME_POLICY_VIOLATION (31)

MLO related assoc fail

Station requesting link-id in STA-profile which AP MLD does not have

MAX-PEER reached on the partner link

Assoc link itself was rejected by the link-rejection logic - IEEE80211_REASON_ASSOC_TOOMANY (5)

SA Query cycle : Assoc response with TEMPORARILY-REJECTED to the station sending assoc request

4. 4-way Handshaking

4way handshaking issue

issue triage

EAPOL reception fail

Check EAPOL stats if num of EAPOL message is matched with the expected one.

cfg80211tool athx txrx_stats 8

cfg80211tool ath0 txrx_stats 260

apstats -i ath0 -v

Trace EAPOL message exchange status of hostapd

hostapd -g /var/run/hostapd/global -ddd -P /var/run/hostapd-global.pid -f /tmp/hostapd.log&

if hostapd has sent EAPOL M1/M3 Tx but not seen in the air, trace fw status to send EAPOL message

cnss_diag -c -p | grep -e "security" -e "WAL_DBGID_TX_EAPOL_PKT

Hostapd level frame drop

STA is not in associated state when EAPOL is received - "IEEE 802.1X data frame from not associated"

EAPOL uses WPA-IE instead of RSN IE - "Ignore EAPOL-Key with unexpected type %d in RSN mode"

KEY data decryption failure - "RSN: AES unwrap failed"

EAPOL received in wrong state - "received EAPOL-Key msg 2/4 in invalid state"

EAPOL M2 message handling failure case

WPA IE mismatch - AP disconnects the STA (deauth) - "WPA IE from (Re)AssocReq did not match with msg 2/4"

Invalid MIC in M2 - "invalid MIC in msg 2/4 of 4-Way Handshake"

KDE parsing failure - "received EAPOL-Key msg 2/4 with invalid Key Data contents"

RSNXE mismatch between assoc-req and M2 - "RSNXE from (Re)AssocReq did not match the one in EAPOL-Key msg 2/4"

EAPOL M4 message handling failure case

KDE parse error - "received EAPOL-Key msg 4/4 with invalid Key Data contents"

Invalid MAC address in MAC KDE - "MLD: Mismatching or missing MLD address in EAPOL-Key msg 4/4"

5. Connection Stability

Connection Stability issue

Issue Symptom & Triage

Tx path stability

Tx stuck

AP drop data frames sending

Rx path stability

5.1. Tx path stability

Tx path stability

Issue Symptom & Triage

Tx stuck

Tx data frame drop

Narrow down which layer stopped sending data frame

Check Host data frame tx status

SFE case: cfg80211tool ath0 txrx_stats 260

Check FW/HW data frame tx status

wifistats wifi2 1

hw_queued - PPDU that Q to HWQ

ppdu_ok - PPDU Tx OK

mpdu_count_tqm - mpdu that received ACK

msdu_count_tqm - MSDU that received ACK

mpdus_ack_failed - mpdu didn't receive ACK

mpdus_expired - mpdu hold in Q for too long and didn't send out

5.2. Rx path stability

Rx path stability

Issue Symptom & Triage

Rx stuck

Check if AP is receiving any OBSS beacon (Beacon is seen at sniffer log)

wifistats wifi2 2

fw_ring_mgmt_subtype = 0:17, 1:0, 2:0, 3:0, 4:12485, 5:1, 6:0, 7:0, 8:117824, 9:0, 10:3, 11:12, 12:0, 13:714, 14:0, 15:0,

Index 8 is beacon, and if your AP is in noisy test environment, there should be OBSS beacon, and this count should keep increasing, if not, that means the HW Rx is getting wrong

Check if frames are dropped at phy layer

wifistats wifi2 37

runTime_nf_chain0 = -101 - The current runtime noise floor

ani_level = -5 - The current runtime ANI level

rx_pkt_cnt[] - The rx pkt_cnt at various mode at phy

rx_pkt_crc_pass_cnt[] - The same as above and pass the CRC

Rx data frame drop

Narrow down which layer packet drop is happening

Check Host data frame Rx status

SFE case: cfg80211tool ath2 txrx_stats 261

Check FW/HW data frame Rx status

wifistats wifi2 2

ppdu_recvd - PPDU received in FW

mpdu_cnt_fcs_ok - MPDU received in FW and FCS ok

mpdu_cnt_fcs_err - MPDU error

Rx drop by AST failures

Rx packet not reaching the host radio driver due to no match with the AST table.

Rx drop by de-crypt errors

When there is a secure connection and there are issues in receiving packets; one can check if there are decrypt errors on the received path.

wifistats wifi0 2

HTT_RX_PDEV_FW_RING_MPDU_ERR_TLV_V:

fw_ring_mpdu_err =  0:0, 1:48870, 2:41730, 3:0, 4:0, 5:0, 6:0, 7:0, 8:0, 9:0, 10:0, 11:0, 12:0, 13:0, 14:0, 15:0

The index 3 value indicates the receive decrypt error.

Rx drop by PN Failure

There are REO errors in the end from 0-14. Index 11 gives the REO PN failure stats.

6. Roaming

7. Disconnection

Disconnection issue

Issue Symptom & Triage

Disconnection initiated by AP

AP sends Deauth/Disassoc to STA

cfg80211tool ath0 csl 1 &  cfg80211tool athX dbgLVL_high 0x20000

[13604.559839] wlan: [0:I:ANY] [INACT] vap-1(ath21): [72:55:27:bc:ee:84]station kicked out due to excessive retries associd 172 (from target) reason 2

Disconnection initiated by STA

STA send Deauth/Disassoc to AP

cfg80211tool ath0 csl 1 &  cfg80211tool athX dbgLVL_high 0x20000

[16033.383964] wlan: [0:I:ANY] [AUTH] vap-1(ath21): [72:55:27:bc:ee:84]Received Deauth with reason 3

7.1. Disconnection initiated by AP

Disconnection initiated by AP

Issue Symptom & Triage

kickout STA

Check if STA inactive time was reached threshold and ensure if STA indeed didn't send any frame in sniffer

wifistats wifi0 11 --mac aa:75:51:10:2c:fb |grep time

inactive_time = 1

cnss_diag -pc | grep -e VDEV_MGR_AP_KEEPALIVE -e STA_KICKOUT

Kick out STA reasons

WMI_PEER_STA_KICKOUT_REASON_UNSPECIFIED = 0

WMI_PEER_STA_KICKOUT_REASON_XRETRY = 1

WMI_PEER_STA_KICKOUT_REASON_INACTIVITY = 2

WMI_PEER_STA_KICKOUT_REASON_IBSS_DISCONNECT = 3

WMI_PEER_STA_KICKOUT_REASON_TDLS_DISCONNECT = 4

WMI_PEER_STA_KICKOUT_REASON_SA_QUERY_TIMEOUT = 5

WMI_PEER_STA_KICKOUT_REASON_ROAMING_EVENT = 6

WMI_PEER_STA_KICKOUT_REASON_PMF_ERROR = 7

Key update fail

Disconnect after CSA

Enable MLME debug logs to obtain more information

cfg80211tool athx dbgLVL 0x80ce0000

7.2. Disconnection initiated by STA

Disconnection initiated by STA

Issue Symptom & Triage

Beacon miss

Check if STA got faced beacon miss with the event print

dmesg | grep "Beacon Miss Detected"

collect the below stats periodically(20 secs).

wifistats wifi0 19 - cca histogram

sniffer logs from both the AP and the STA

Check RX stuck with below logs

for 5g: devmem 0xCAAA10c; devmem 0xCAAA110 ; devmem 0xCAAA114

for 2g: devmem 0xCB2A10C; devmem 0xCB2A110; devmem 0xCB2A114

Delay in receiving Assoc Resp after Assoc Request

Enable below commands on AP and also hostapd logs in debug mode

cfg80211tool mldX link_id Y dbgLVL 0x80c00000

cfg80211tool mldX link_id Y csl 1

Excessive retry

8. Startup Failures

8.1. Boot failure

Device did not boot

Debug Steps: Console logs, Crash dump / mini dump

8.2. Module load failure

Failure to load any of the kernel modules listed in /lib/wifi/qca-wifi-modules

Debug Steps: dmesg logs: look for bus errors, device mismatch errors

check if device is enumerated: lspci -m

8.3. Interface up failure

Debug Steps

Obtain vap configurations: cat /proc/athN/iv_config

Obtain MLME state machine history: cfg80211tool athN sm_history

Serialization history: cfg80211tool athN ser_history

Enable MLME logs

State machine debug: cfg80211tool athX qdf_cv_lvl 0x68000a

MLME debug: cfg80211tool athX qdf_cv_lvl 0x69000a
"""
