# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

import os

import requests

RAW_STATS = {
    # WIFISTAT 1 - HTT_TX_PDEV_STATS_CMN_TLV and related
    "HTT_TX_PDEV_STATS_CMN_TLV",
    "HTT_TX_PDEV_STATS_CMN_TLV:",
    "HTT_TX_PDEV_MU_EDCA_PARAMS_STATS_TLV",
    "HTT_TX_PDEV_MU_EDCA_PARAMS_STATS_TLV:",
    "AP EDCA PARAMETERS FOR UL MUMIMO",
    "AP EDCA PARAMETERS FOR UL MUMIMO:",
    "AP EDCA PARAMETERS FOR UL OFDMA",
    "AP EDCA PARAMETERS FOR UL OFDMA:",
    "HTT_STATS_TX_PDEV_WIFI_RADAR_TAG",
    "HTT_STATS_TX_PDEV_WIFI_RADAR_TAG:",
    "mac_id",
    "relaxed_mu_edca",
    "mumimo_aggressive_mu_edca",
    "mumimo_relaxed_mu_edca",
    "muofdma_aggressive_mu_edca",
    "muofdma_relaxed_mu_edca",
    "latency_mu_edca",
    "psd_boost_mu_edca",
    "ul_mumimo_less_aggressive[0]",
    "ul_mumimo_medium_aggressive[0]",
    "ul_mumimo_highly_aggressive[0]",
    "ul_mumimo_default_relaxed[0]",
    "ul_mumimo_less_aggressive[1]",
    "ul_mumimo_medium_aggressive[1]",
    "ul_mumimo_highly_aggressive[1]",
    "ul_mumimo_default_relaxed[1]",
    "ul_mumimo_less_aggressive[2]",
    "ul_mumimo_medium_aggressive[2]",
    "ul_mumimo_highly_aggressive[2]",
    "ul_mumimo_default_relaxed[2]",
    "ul_mumimo_less_aggressive[3]",
    "ul_mumimo_medium_aggressive[3]",
    "ul_mumimo_highly_aggressive[3]",
    "ul_mumimo_default_relaxed[3]",
    "ul_muofdma_less_aggressive[0]",
    "ul_muofdma_medium_aggressive[0]",
    "ul_muofdma_highly_aggressive[0]",
    "ul_muofdma_default_relaxed[0]",
    "ul_muofdma_less_aggressive[1]",
    "ul_muofdma_medium_aggressive[1]",
    "ul_muofdma_highly_aggressive[1]",
    "ul_muofdma_default_relaxed[1]",
    "ul_muofdma_less_aggressive[2]",
    "ul_muofdma_medium_aggressive[2]",
    "ul_muofdma_highly_aggressive[2]",
    "ul_muofdma_default_relaxed[2]",
    "ul_muofdma_less_aggressive[3]",
    "ul_muofdma_medium_aggressive[3]",
    "ul_muofdma_highly_aggressive[3]",
    "ul_muofdma_default_relaxed[3]",
    "capture_in_progress",
    "calibration_in_progress",
    "periodicity (ms)",
    "latest_req_timestamp (ms)",
    "latest_resp_timestamp (ms)",
    "Full_calibration_timing (ms)",
    "latest_wifi_radar_cal_type",
    "latest_wifi_radar_cal_fail_reason",
    "wifi_radar_licensed",
    "wifi_radar_cal_init_tx_gain",
    "wifi_radar_tx_gain",
    "calibration_timing",
    "Rx gain for chain index",

    # WIFISTAT 2
    "mac_id__word",
    "HTT_RX_PDEV_FW_STATS_TLV",
    "HTT_RX_PDEV_FW_STATS_TLV:",

    # WIFISTAT 3 - HTT_TX_HWQ_STATS_CMN_TLV
    "HTT_TX_HWQ_STATS_CMN_TLV",
    "HTT_TX_HWQ_STATS_CMN_TLV:",
    "hwq_id",
    "sched_id_proc",

    # WIFISTAT 5 - HTT_HW_STATS_INTR_MISC_TLV and related
    "HTT_HW_STATS_INTR_MISC_TLV",
    "HTT_HW_STATS_INTR_MISC_TLV:",
    "HTT_HW_STATS_PDEV_ERRS_TLV",
    "HTT_HW_STATS_PDEV_ERRS_TLV:",
    "HTT_HW_STATS_WHAL_TX_TLV",
    "HTT_HW_STATS_WHAL_TX_TLV:",
    "HTT_STATS_WHAL_WSI_TLV",
    "HTT_STATS_WHAL_WSI_TLV:",
    "HTT_HW_WAR_STATS_TLV",
    "HTT_HW_WAR_STATS_TLV:",
    "hw_intr_name",
    "mask",
    "count",
    "last_unpause_ppdu_id",

    # WIFISTAT 8 - HTT_TX_DE_CMN_STATS_TLV
    "HTT_TX_DE_CMN_STATS_TLV",
    "HTT_TX_DE_CMN_STATS_TLV:",

    # WIFISTAT 9 - HTT_TX_PDEV_RATE_STATS_TLV
    "HTT_TX_PDEV_RATE_STATS_TLV",
    "HTT_TX_PDEV_RATE_STATS_TLV:",
    "ack_rssi",
    "pdev_up_time_us_low",
    "pdev_up_time_us_high",
    "tx_success_time_us_low",
    "tx_success_time_us_high",
    "tx_fail_time_us_low",
    "tx_fail_time_us_high",

    # WIFISTAT 10 - HTT_RX_PDEV_PPDU_DUR_STATS_TLV and HTT_RX_PDEV_RATE_STATS_TLV
    "HTT_RX_PDEV_PPDU_DUR_STATS_TLV",
    "HTT_RX_PDEV_RATE_STATS_TLV",
    "HTT_RX_PDEV_RATE_STATS_TLV:",
    "rssi_mgmt",
    "rssi_data",
    "rssi_comb",
    "rssi_in_dbm",
    "rssi_chain[0]",
    "rssi_chain[1]",
    "rssi_chain[2]",
    "rssi_chain[3]",
    "rssi_chain[4]",
    "rssi_chain[5]",
    "rssi_chain[6]",
    "rssi_chain[7]",
    "rx_ul_fd_rssi: nss[0]",
    "rx_ul_fd_rssi: nss[1]",
    "rx_ul_fd_rssi: nss[2]",
    "rx_ul_fd_rssi: nss[3]",
    "rx_ul_fd_rssi: nss[4]",
    "rx_ul_fd_rssi: nss[5]",
    "rx_ul_fd_rssi: nss[6]",
    "rx_ul_fd_rssi: nss[7]",
    "per_chain_rssi_pkt_type",
    "rx_per_chain_rssi_in_dbm[0]",
    "rx_per_chain_rssi_in_dbm[1]",
    "rx_per_chain_rssi_in_dbm[2]",
    "rx_per_chain_rssi_in_dbm[3]",
    "rx_per_chain_rssi_in_dbm[4]",
    "rx_per_chain_rssi_in_dbm[5]",
    "rx_per_chain_rssi_in_dbm[6]",
    "rx_per_chain_rssi_in_dbm[7]",
    "rx_ppdu_dur_hist_us",

    # WIFISTAT 12 - HTT_TX_SELFGEN_CMN_STATS_TLV
    "HTT_TX_SELFGEN_CMN_STATS_TLV",
    "HTT_TX_SELFGEN_CMN_STATS_TLV:",
    " ",

    # WIFISTAT 17 - HTT_TX_PDEV_MU_MIMO_SCH_STATS_TLV
    "HTT_TX_PDEV_MU_MIMO_SCH_STATS_TLV",
    "HTT_TX_PDEV_MU_MIMO_SCH_STATS_TLV:",
    "grp_id",

    # WIFISTAT 21 - WMI_CTRL_PATH_CONN_STATS_TLV
    "WMI_CTRL_PATH_CONN_STATS_TLV",
    "WMI_CTRL_PATH_CONN_STATS_TLV: (pdev_id:0)",

    # WIFISTAT 47 - ML peer stats
    "HTT_ML_PEER_DETAILS_TLV",
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

    # WIFISTAT 48 - HTT_ODD_PDEV_MANDATORY_TLV
    "HTT_ODD_PDEV_MANDATORY_TLV",
    "HTT_ODD_PDEV_MANDATORY_TLV:",
}


def _log_prompt_and_response(call_type, prompt, response, backend):
    """Append the prompt and response to a log file under the prompts directory.

    Logging is disabled by default. Set the environment variable
    ENABLE_PROMPT_LOGGING=true to enable it.
    """
    if os.getenv("ENABLE_PROMPT_LOGGING", "false").lower() != "true":
        return
    import datetime
    log_dir = "/data/prompts"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "llm_calls.log")
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "=" * 80
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n{separator}\n")
        f.write(f"TIMESTAMP : {timestamp}\n")
        f.write(f"BACKEND   : {backend}\n")
        f.write(f"CALL_TYPE : {call_type}\n")
        f.write(f"{separator}\n")
        f.write("--- PROMPT ---\n")
        f.write(prompt)
        f.write("\n--- RESPONSE ---\n")
        f.write(str(response))
        f.write(f"\n{separator}\n")


def generate_llm_response(MODEL, custom_prompt, call_type, agent_name=None):
    if call_type == 'wifi':
        context_length = 500
    elif call_type == 'hostapd':
        context_length = 3000
    else:
        context_length = 8192

    internal_llm_api_url = "http://localhost:8001/v1/completions"
    model_name = os.getenv("HF_MODEL_NAME", "mistralai/Mistral-7B-Instruct-v0.2")
    payload = {
        "model": model_name,
        "prompt": custom_prompt,
        "max_tokens": context_length,
        "temperature": 0.0,
    }

    try:
        response = requests.post(
            internal_llm_api_url,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=3000,
        )
        if response.status_code == 200:
            result = response.json()["choices"][0]["text"]
            _log_prompt_and_response(call_type, custom_prompt, result, "vllm")
            return result
        return f"Error: API returned status code {response.status_code}"
    except Exception as e:
        return f"Error accessing internal LLM API: {str(e)}"
