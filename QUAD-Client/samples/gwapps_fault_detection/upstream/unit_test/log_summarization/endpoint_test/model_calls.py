# Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries.
# All rights reserved.
# Confidential and Proprietary - Qualcomm Technologies, Inc.

import logging
import os
import time

import boto3
import qgenie
import requests
from botocore.exceptions import BotoCoreError, ClientError

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


def call_internal_endpoint_with_tar(tar_file_path, poll_interval=30, max_wait_seconds=1800):
    """
    Submit a tar file to the internal LLM API endpoint, poll for completion,
    and return the summary text.

    Steps:
      1. POST the tar file as multipart form data to INTERNAL_LLM_API_URL
      2. Extract request_id from the initial {"status": "pending", "request_id": "..."} response
      3. Poll GET {base_url}/{request_id} every poll_interval seconds
      4. Return response["summary"] when status == "completed"
      5. Raise RuntimeError on status == "failed" or timeout

    Args:
        tar_file_path:     Path to the .tar file to submit.
        poll_interval:     Seconds between status-check requests (default 30).
        max_wait_seconds:  Maximum total seconds to wait before timing out (default 900 = 15 min).

    Returns:
        The summary string from the completed response.

    Raises:
        RuntimeError: If the endpoint reports failure or the wait exceeds max_wait_seconds.
    """
    from dotenv import load_dotenv
    load_dotenv()

    base_url = os.getenv(
        "INTERNAL_LLM_API_URL",
        "http://winml-linux.qualcomm.com:9010/api/v1/connectivity"
    )

    # --- Step 1: POST the tar file as multipart form data ---
    tar_filename = os.path.basename(tar_file_path)
    logging.info("Submitting tar file '%s' to %s", tar_filename, base_url)

    with open(tar_file_path, "rb") as f:
        submit_response = requests.post(
            base_url,
            files={"file": (tar_filename, f, "application/x-tar")},
            timeout=60,
        )
    submit_response.raise_for_status()
    initial_data = submit_response.json()

    request_id = initial_data.get("request_id")
    if not request_id:
        raise RuntimeError(f"No request_id in initial response: {initial_data}")

    top_level_entries = initial_data.get("top_level_entries", [])
    logging.info(
        "Submitted '%s' → request_id=%s  top_level_entries=%s",
        tar_filename, request_id, top_level_entries
    )
    print(f"  Submitted  : {tar_filename}")
    print(f"  Request ID : {request_id}")
    print(f"  Entries    : {top_level_entries}")
    print(f"  Polling every {poll_interval}s (max {max_wait_seconds}s) ...")

    # --- Step 2: Poll for completion ---
    poll_url = f"{base_url}/{request_id}"
    elapsed = 0

    while elapsed < max_wait_seconds:
        time.sleep(poll_interval)
        elapsed += poll_interval

        poll_resp = requests.get(poll_url, timeout=30)
        poll_resp.raise_for_status()
        poll_data = poll_resp.json()
        status = poll_data.get("status")

        logging.info("[%ds] request_id=%s  status=%s", elapsed, request_id, status)
        print(f"  [{elapsed:>4}s] status={status}")

        if status == "completed":
            summary = poll_data.get("summary")
            if not summary:
                raise RuntimeError(
                    f"Status is 'completed' but no summary in response: {poll_data}"
                )
            logging.info("request_id=%s completed successfully.", request_id)
            return summary

        if status == "failed":
            error_msg = poll_data.get("error_message", "unknown error")
            raise RuntimeError(
                f"Endpoint reported failure for request_id={request_id}: {error_msg}"
            )

        # status is "pending" or "processing" — keep polling

    raise RuntimeError(
        f"Timed out after {max_wait_seconds}s waiting for request_id={request_id}"
    )


def generate_llm_response(MODEL, custom_prompt, call_type, agent_name=None):
    import os
    import traceback

    from dotenv import load_dotenv

    context_length = 0
    if call_type == 'wifi':
        context_length = 500
    elif call_type == 'hostapd':
        context_length = 3000
    else:
        context_length = 8192

    use_bedrock = os.getenv("USE_BEDROCK", "false").lower() == "true"

    if use_bedrock:
        load_dotenv()
        AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
        BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID")

        if not BEDROCK_MODEL_ID:
            logging.error("BEDROCK_MODEL_ID not set in environment variables")
            return "Error: BEDROCK_MODEL_ID not configured"

        try:
            bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        except (BotoCoreError, ClientError) as e:
            logging.error("Failed to create Bedrock client: %s", e)
            return f"Error: Failed to create Bedrock client - {str(e)}"

        try:
            messages = [
                {"role": "user", "content": [{"text": custom_prompt}]}
            ]
            inference_config = {
                "temperature": 0.0,
                "maxTokens": context_length,
            }

            resp = bedrock_client.converse(
                modelId=BEDROCK_MODEL_ID,
                messages=messages,
                inferenceConfig=inference_config
            )

            print("#########")
            print("Bedrock response:")
            print(resp)
            print("#########")

            parts = resp.get("output", {}).get("message", {}).get("content", [])
            text = "".join(p.get("text", "") for p in parts).strip()
            if not text:
                text = "No response from model."
            return text

        except Exception as e:
            print("❌ Exception occurred in generate_llm_response:")
            traceback.print_exc()
            return f"Error: {str(e)}"

    else:
        # Check if QGENIE_API_KEY is present in environment variables
        load_dotenv()
        qgenie_api_key = os.getenv("QGENIE_API_KEY")

        if qgenie_api_key:
            # Use QGenie client if API key is available
            client = qgenie.QGenieClient(max_retries=1, debug=False)

            messages = [
                {
                    "role": "user",
                    "content": custom_prompt,
                },
            ]

            try:
                response = client.chat(
                    model='anthropic::claude-4-5-sonnet',
                    messages=messages,
                    temperature=0.0,
                    max_tokens=context_length
                )
                return response.choices[0].message.content

            except Exception as e:
                return f"Error: {str(e)}"
        else:
            # Use internal LLM API if QGENIE_API_KEY is not available
            internal_llm_api_url = os.getenv("INTERNAL_LLM_API_URL", "http://winml-linux.qualcomm.com:9010/api/v1/connectivity")

            try:
                payload = {
                    "prompt": custom_prompt,
                    "max_tokens": context_length,
                    "temperature": 0.0
                }

                response = requests.post(
                    internal_llm_api_url,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=3000  # 5 minutes timeout for LLM calls
                )

                if response.status_code == 200:
                    response_data = response.json()
                    return response_data["choices"][0]["text"]
                else:
                    return f"Error: API returned status code {response.status_code}"

            except Exception as e:
                return f"Error accessing internal LLM API: {str(e)}"
