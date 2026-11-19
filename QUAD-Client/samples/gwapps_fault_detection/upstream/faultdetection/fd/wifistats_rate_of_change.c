/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

// Improved calculate_rate_of_change function that handles:
// 1. Regular text lines (headers like "Chain Pair 2 Stats")
// 2. Simple numeric stats (stat_name = value)
// 3. Index format stats (stat_name = = 0:val0, 1:val1, 2:val2, ...)
// 4. Double equals signs
// 5. Array notation in stat names (e.g., stat_name[0] = value)
// 6. Section separators (lines with only '=' characters)

// - __Simple stats__: `stat_name = value`
// - __Integer index stats__: `stat_name = 0:val, 1:val, 2:val, ...`
// - __Negative index stats__: `stat_name = -2:val, -1:val, 0:val, ...`
// - __Range index stats__: `stat_name = 0-250 : val, 250-500 : val, ...`
// - __Colon-separated stats__: `stat_name: 0:val, 1:val, ...` (tx_mgmt_subtype_enq_ok)
// - __Table format stats__: `| val1| val2| val3|...`
// - __Stats with multiple `=` signs__: `stat_name (PARAM = X) = value`
// - __Section headers__: `=== WIFISTAT N ===`


#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <time.h>

// ============================================================================
// COPY-ONLY STATS ORGANIZED BY WIFISTAT SECTION
// These stats will be copied directly from current_wifistats.txt without
// calculating rate of change. Organized by WIFISTAT section for maintainability.
// ============================================================================

// WIFISTAT 1 - HTT_TX_PDEV_STATS_CMN_TLV and related
static const char* WIFISTAT_1_COPY_STATS[] = {
    // Headers
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
    
    // HTT_TX_PDEV_STATS_CMN_TLV
    "mac_id",
    
    // HTT_TX_PDEV_MU_EDCA_PARAMS_STATS_TLV
    "relaxed_mu_edca",
    "mumimo_aggressive_mu_edca",
    "mumimo_relaxed_mu_edca",
    "muofdma_aggressive_mu_edca",
    "muofdma_relaxed_mu_edca",
    "latency_mu_edca",
    "psd_boost_mu_edca",
    
    // AP EDCA PARAMETERS FOR UL MUMIMO
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
    
    // AP EDCA PARAMETERS FOR UL OFDMA
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
    
    // Calibration and timing stats
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
    
    NULL
};

// WIFISTAT 2 - Only these specific stats should be copied (not have rate of change calculated)
static const char* WIFISTAT_2_COPY_STATS[] = {
    "mac_id",
    "mac_id__word",
    "HTT_RX_PDEV_FW_STATS_TLV",
    "HTT_RX_PDEV_FW_STATS_TLV:",
    
    NULL
};

// WIFISTAT 3 - HTT_TX_HWQ_STATS_CMN_TLV stats to be copied
static const char* WIFISTAT_3_COPY_STATS[] = {
    // Header
    "HTT_TX_HWQ_STATS_CMN_TLV",
    "HTT_TX_HWQ_STATS_CMN_TLV:",
    
    // Stats
    "mac_id",
    "hwq_id",
    "sched_id_proc",
    
    NULL
};

// WIFISTAT 4 - PHY/MAC warm-reset reasons and HW workaround counters to be copied
static const char* WIFISTAT_4_COPY_STATS[] = {
    // Headers
    "PDEV_PHY_WARM_RESET_REASONS",
    "PDEV_PHY_WARM_RESET_REASONS:",
    "HTT_HW_WAR_STATS_TLV",
    "HTT_HW_WAR_STATS_TLV:",

    // Warm-reset counters
    "warm_reset",
    "mac_warm_reset",
    "phy_warm_reset",
    "phy_warm_reset_ucode_trig",
    "mac_warm_reset_restore_cal",
    "phy_warm_reset_m3_ssr",

    // PDEV_PHY_WARM_RESET_REASONS counters
    "phy_warm_reset_reason_phy_m3",
    "phy_warm_reset_reason_tx_hw_stuck",
    "phy_warm_reset_reason_num_cca_rx_frame_stuck",
    "phy_warm_reset_reason_wal_rx_recovery_rst_rx_busy",
    "phy_warm_reset_reason_wal_rx_recovery_rst_mac_hang",
    "phy_warm_reset_reason_mac_reset_converted_phy_reset",
    "phy_warm_reset_reason_tx_lifetime_expiry_cca_stuck",
    "phy_warm_reset_reason_tx_consecutive_flush9_war",
    "phy_warm_reset_reason_tx_hwsch_reset_war",
    "phy_warm_reset_reason_hwsch_wdog_or_cca_wdog_war",
    "hwsch_dev_reset_war",

    // HTT_HW_WAR_STATS_TLV counters (hw_war 0 .. hw_war 170)
    "hw_war 0",
    "hw_war 1",
    "hw_war 2",
    "hw_war 3",
    "hw_war 4",
    "hw_war 5",
    "hw_war 6",
    "hw_war 7",
    "hw_war 8",
    "hw_war 9",
    "hw_war 10",
    "hw_war 11",
    "hw_war 12",
    "hw_war 13",
    "hw_war 14",
    "hw_war 15",
    "hw_war 16",
    "hw_war 17",
    "hw_war 18",
    "hw_war 19",
    "hw_war 20",
    "hw_war 21",
    "hw_war 22",
    "hw_war 23",
    "hw_war 24",
    "hw_war 25",
    "hw_war 26",
    "hw_war 27",
    "hw_war 28",
    "hw_war 29",
    "hw_war 30",
    "hw_war 31",
    "hw_war 32",
    "hw_war 33",
    "hw_war 34",
    "hw_war 35",
    "hw_war 36",
    "hw_war 37",
    "hw_war 38",
    "hw_war 39",
    "hw_war 40",
    "hw_war 41",
    "hw_war 42",
    "hw_war 43",
    "hw_war 44",
    "hw_war 45",
    "hw_war 46",
    "hw_war 47",
    "hw_war 48",
    "hw_war 49",
    "hw_war 50",
    "hw_war 51",
    "hw_war 52",
    "hw_war 53",
    "hw_war 54",
    "hw_war 55",
    "hw_war 56",
    "hw_war 57",
    "hw_war 58",
    "hw_war 59",
    "hw_war 60",
    "hw_war 61",
    "hw_war 62",
    "hw_war 63",
    "hw_war 64",
    "hw_war 65",
    "hw_war 66",
    "hw_war 67",
    "hw_war 68",
    "hw_war 69",
    "hw_war 70",
    "hw_war 71",
    "hw_war 72",
    "hw_war 73",
    "hw_war 74",
    "hw_war 75",
    "hw_war 76",
    "hw_war 77",
    "hw_war 78",
    "hw_war 79",
    "hw_war 80",
    "hw_war 81",
    "hw_war 82",
    "hw_war 83",
    "hw_war 84",
    "hw_war 85",
    "hw_war 86",
    "hw_war 87",
    "hw_war 88",
    "hw_war 89",
    "hw_war 90",
    "hw_war 91",
    "hw_war 92",
    "hw_war 93",
    "hw_war 94",
    "hw_war 95",
    "hw_war 96",
    "hw_war 97",
    "hw_war 98",
    "hw_war 99",
    "hw_war 100",
    "hw_war 101",
    "hw_war 102",
    "hw_war 103",
    "hw_war 104",
    "hw_war 105",
    "hw_war 106",
    "hw_war 107",
    "hw_war 108",
    "hw_war 109",
    "hw_war 110",
    "hw_war 111",
    "hw_war 112",
    "hw_war 113",
    "hw_war 114",
    "hw_war 115",
    "hw_war 116",
    "hw_war 117",
    "hw_war 118",
    "hw_war 119",
    "hw_war 120",
    "hw_war 121",
    "hw_war 122",
    "hw_war 123",
    "hw_war 124",
    "hw_war 125",
    "hw_war 126",
    "hw_war 127",
    "hw_war 128",
    "hw_war 129",
    "hw_war 130",
    "hw_war 131",
    "hw_war 132",
    "hw_war 133",
    "hw_war 134",
    "hw_war 135",
    "hw_war 136",
    "hw_war 137",
    "hw_war 138",
    "hw_war 139",
    "hw_war 140",
    "hw_war 141",
    "hw_war 142",
    "hw_war 143",
    "hw_war 144",
    "hw_war 145",
    "hw_war 146",
    "hw_war 147",
    "hw_war 148",
    "hw_war 149",
    "hw_war 150",
    "hw_war 151",
    "hw_war 152",
    "hw_war 153",
    "hw_war 154",
    "hw_war 155",
    "hw_war 156",
    "hw_war 157",
    "hw_war 158",
    "hw_war 159",
    "hw_war 160",
    "hw_war 161",
    "hw_war 162",
    "hw_war 163",
    "hw_war 164",
    "hw_war 165",
    "hw_war 166",
    "hw_war 167",
    "hw_war 168",
    "hw_war 169",
    "hw_war 170",

    NULL
};

// WIFISTAT 5 - HTT_HW_STATS_INTR_MISC_TLV and related stats to be copied
static const char* WIFISTAT_5_COPY_STATS[] = {
    // Headers
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
    
    // HTT_HW_STATS_INTR_MISC_TLV stats
    "mac_id",
    "hw_intr_name",
    "mask",
    "count",
    "last_unpause_ppdu_id",
    
    NULL
};

// WIFISTAT 6 - HTT_TX_TQM stats and TQM error/reset counters to be copied
static const char* WIFISTAT_6_COPY_STATS[] = {
    // Section headers (with and without trailing colon)
    "TQM_ERROR_RESET_STATS",
    "TQM_ERROR_RESET_STATS:",
    "HTT_TX_TQM_GEN_MPDU_STATS_TLV_V",
    "HTT_TX_TQM_GEN_MPDU_STATS_TLV_V:",
    "HTT_TX_TQM_LIST_MPDU_STATS_TLV_V",
    "HTT_TX_TQM_LIST_MPDU_STATS_TLV_V:",
    "HTT_TX_TQM_LIST_MPDU_CNT_TLV_V",
    "HTT_TX_TQM_LIST_MPDU_CNT_TLV_V:",
    "HTT_TX_TQM_PDEV_STATS_TLV_V",
    "HTT_TX_TQM_PDEV_STATS_TLV_V:",

    // TQM tracking counters (top block)
    "add_msdu",
    "q_empty",
    "q_not_empty",
    "drop_notification",
    "desc_threshold",
    "hwsch_tqm_invalid_status",
    "missed_tqm_gen_mpdus",
    "total_msduq_timestamp_updates",
    "total_msduq_timestamp_updates_by_get_mpdu_head_info_cmd",
    "total_msduq_timestamp_updates_by_empty_to_nonempty_status",
    "total_get_mpdu_head_info_cmds_by_sched_algo_la_query",
    "total_get_mpdu_head_info_cmds_by_tac",
    "total_gen_mpdu_cmds_by_sched_algo_la_query",
    "active_tqm_tids",
    "inactive_tqm_tids",
    "tqm_active_msduq_flows",
    "hi_prio_q_not_empty",
    "q_empty_failure",
    "q_not_empty_failure",
    "add_msdu_failure",

    // TQM_ERROR_RESET_STATS counters
    "tqm_cache_ctl_err",
    "tqm_soft_reset",
    "tqm_reset_total_num_in_use_link_descs",
    "tqm_reset_worst_case_num_lost_link_descs",
    "tqm_reset_worst_case_num_lost_host_tx_bufs_count",
    "tqm_reset_num_in_use_link_descs_internal_tqm",
    "tqm_reset_num_in_use_link_descs_wbm_idle_link_ring",
    "tqm_reset_time_to_tqm_hang_delta_ms",
    "tqm_reset_recovery_time_ms",
    "tqm_reset_num_peers_hdl",
    "tqm_reset_cumm_dirty_hw_mpduq_proc_cnt",
    "tqm_reset_cumm_dirty_hw_msduq_proc",
    "tqm_reset_flush_cache_cmd_su_cnt",
    "tqm_reset_flush_cache_cmd_other_cnt",
    "tqm_reset_flush_cache_cmd_trig_type",
    "tqm_reset_flush_cache_cmd_skip_cmd_status_null",

    // Index-format stats listed here so should_copy_stat() routes them to a
    // verbatim copy instead of the per-index delta path further below
    "gen_mpdu_end_reason",
    "list_mpdu_end_reason",
    "list_mpdu_cnt_hist",

    // HTT_TX_TQM_PDEV_STATS_TLV_V counters
    "msdu_count",
    "mpdu_count",
    "remove_msdu",
    "remove_mpdu",
    "remove_msdu_ttl",
    "send_bar",
    "bar_sync",
    "notify_mpdu",
    "sync_cmd",
    "write_cmd",
    "hwsch_trigger",
    "ack_tlv_proc",
    "gen_mpdu_cmd",
    "gen_list_cmd",
    "remove_mpdu_cmd",
    "remove_mpdu_tried_cmd",
    "mpdu_queue_stats_cmd",
    "mpdu_head_info_cmd",
    "msdu_flow_stats_cmd",
    "remove_msdu_cmd",
    "remove_msdu_ttl_cmd",
    "flush_cache_cmd",
    "update_mpduq_cmd",
    "enqueue",
    "enqueue_notify",
    "notify_mpdu_at_head",
    "notify_mpdu_state_valid",
    "sched_udp_notify1",
    "sched_udp_notify2",
    "sched_nonudp_notify1",
    "sched_nonudp_notify2",
    "tqm_enqueue_msdu_count",
    "tqm_dropped_msdu_count",
    "tqm_dequeue_msdu_count",

    NULL
};

// WIFISTAT 8 - HTT_TX_DE_CMN_STATS_TLV stats to be copied
static const char* WIFISTAT_8_COPY_STATS[] = {
    // Header
    "HTT_TX_DE_CMN_STATS_TLV",
    "HTT_TX_DE_CMN_STATS_TLV:",
    
    // Stats
    "mac_id",
    
    NULL
};

// WIFISTAT 9 - HTT_TX_PDEV_RATE_STATS_TLV stats to be copied
static const char* WIFISTAT_9_COPY_STATS[] = {
    // Header
    "HTT_TX_PDEV_RATE_STATS_TLV",
    "HTT_TX_PDEV_RATE_STATS_TLV:",
    
    // Stats
    "mac_id",
    "ack_rssi",
    "pdev_up_time_us_low",
    "pdev_up_time_us_high",
    "tx_success_time_us_low",
    "tx_success_time_us_high",
    "tx_fail_time_us_low",
    "tx_fail_time_us_high",
    
    NULL
};

// WIFISTAT 10 - HTT_RX_PDEV_PPDU_DUR_STATS_TLV and HTT_RX_PDEV_RATE_STATS_TLV stats to be copied
static const char* WIFISTAT_10_COPY_STATS[] = {
    // Headers
    "HTT_RX_PDEV_PPDU_DUR_STATS_TLV",
    "HTT_RX_PDEV_RATE_STATS_TLV",
    "HTT_RX_PDEV_RATE_STATS_TLV:",
    
    // Stats
    "mac_id",
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
    
    NULL
};

// WIFISTAT 12 - HTT_TX_SELFGEN_CMN_STATS_TLV stats to be copied
static const char* WIFISTAT_12_COPY_STATS[] = {
    // Header
    "HTT_TX_SELFGEN_CMN_STATS_TLV",
    "HTT_TX_SELFGEN_CMN_STATS_TLV:",
    " ",
    
    // Stats
    "mac_id",
    
    NULL
};

// WIFISTAT 17 - HTT_TX_PDEV_MU_MIMO_SCH_STATS_TLV stats to be copied
static const char* WIFISTAT_17_COPY_STATS[] = {
    // Header
    "HTT_TX_PDEV_MU_MIMO_SCH_STATS_TLV",
    "HTT_TX_PDEV_MU_MIMO_SCH_STATS_TLV:",
    
    // Stats
    "grp_id",
    
    NULL
};

// WIFISTAT 18 - peer powersave entry/exit counters and dwell histogram
static const char* WIFISTAT_18_COPY_STATS[] = {
    "peer_powersave_entry_value",
    "peer_powersave_exit_value",
    "peer_powersave_pspoll_trigger",
    "peer_powersave_uapsd_trigger",
    "peer_powersave_histogram[0]",
    "peer_powersave_histogram[1]",
    "peer_powersave_histogram[2]",

    NULL
};

// WIFISTAT 21 - WMI_CTRL_PATH_CONN_STATS_TLV stats to be copied
static const char* WIFISTAT_21_COPY_STATS[] = {
    // Header
    "WMI_CTRL_PATH_CONN_STATS_TLV",
    "WMI_CTRL_PATH_CONN_STATS_TLV: (pdev_id:0)",
    
    NULL
};

// WIFISTAT 47 - ML peer stats to be copied
static const char* WIFISTAT_47_COPY_STATS[] = {
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
    
    NULL
};

// WIFISTAT 37 - HTT_PHY_STATS_TLV and related stats to be copied
static const char* WIFISTAT_37_COPY_STATS[] = {
    // Headers
    "HTT_PHY_STATS_TLV",
    "HTT_PHY_STATS_TLV:",
    "HTT_PHY_COUNTERS_TLV",
    "HTT_PHY_COUNTERS_TLV:",
    "HTT_PHY_RESET_STATS_TLV",
    "HTT_PHY_RESET_STATS_TLV:",
    "HTT_PHY_RESET_COUNTERS_TLV",
    "HTT_PHY_RESET_COUNTERS_TLV:",
    "HTT_PHY_TPC_STATS_TLV",
    "HTT_PHY_TPC_STATS_TLV:",
    
    // HTT_PHY_STATS_TLV
    "false_radar_cnt",
    "radar_cs_cnt",
    
    // HTT_PHY_COUNTERS_TLV
    "rx_ofdma_timing_err_cnt",
    "mactx_abort_cnt",
    "macrx_abort_cnt",
    "phytx_abort_cnt",
    "phyrx_abort_cnt",
    "phyrx_defer_abort_cnt",
    "rx_gain_adj_lstf_event_cnt",
    "rx_gain_adj_non_legacy_cnt",
    "rx_pkt_cnt_11a",
    "rx_pkt_cnt_11b",
    "rx_pkt_cnt_11n",
    "rx_pkt_cnt_11ac",
    "rx_pkt_cnt_11ax",
    "rx_pkt_cnt_gf",
    "rx_pkt_cnt_eht",
    "rx_pkt_cnt_rsvd",
    "rx_pkt_crc_pass_cnt_11a",
    "rx_pkt_crc_pass_cnt_11b",
    "rx_pkt_crc_pass_cnt_11n",
    "rx_pkt_crc_pass_cnt_11ac",
    "rx_pkt_crc_pass_cnt_11ax",
    "rx_pkt_crc_pass_cnt_gf",
    "rx_pkt_crc_pass_cnt_eht",
    "rx_pkt_crc_pass_cnt_rsvd",
    "per_blk_err_cnt_unknown",
    "per_blk_err_cnt_lsig_error",
    "per_blk_err_cnt_htsig_error",
    "per_blk_err_cnt_vhtsig_error",
    "per_blk_err_cnt_hesig_error",
    "per_blk_err_cnt_rxtd_ota",
    "per_blk_err_cnt_rxtd_fatal",
    "per_blk_err_cnt_demf",
    "per_blk_err_cnt_robe",
    "per_blk_err_cnt_pmi",
    "per_blk_err_cnt_txfd",
    "per_blk_err_cnt_txtd",
    "per_blk_err_cnt_phyrf",
    "per_blk_err_cnt_cck1_fail_or_na1",
    "per_blk_err_cnt_cck2_fail_or_na2",
    "per_blk_err_cnt_cck7_fail_or_na3",
    "rx_ota_err_cnt_voting_fail",
    "rx_ota_err_cnt_weak_det_fail",
    "rx_ota_err_cnt_strong_sig_fail",
    "rx_ota_err_cnt_cck_fail",
    "rx_ota_err_cnt_power_surge",
    "rx_ota_err_cnt_power_drop",
    "rx_ota_err_cnt_btcf_timing_timeout",
    "rx_ota_err_cnt_btcf_packet_detect",
    "rx_ota_err_cnt_coarse_timing_timeout",
    "rx_pkt_cnt_ext_wur",
    "rx_pkt_cnt_ext_az",
    "rx_pkt_cnt_ext_rsvd",
    "rx_pkt_crc_pass_cnt_ext_wur",
    "rx_pkt_crc_pass_cnt_ext_az",
    "rx_pkt_crc_pass_cnt_ext_rsvd",
    "rx_pkt_mu_cnt_11ax_ofdma",
    "rx_pkt_mu_cnt_11ax_hybrid",
    "rx_pkt_mu_cnt_11be_ofdma",
    "rx_pkt_mu_cnt_11be_hybrid",
    "rx_pkt_mu_cnt_11ax_mimo",
    "rx_pkt_mu_cnt_11be_mimo",
    "rx_pkt_mu_cnt_11ax_ofdma_pass",
    "rx_pkt_mu_cnt_11ax_hybrid_pass",
    "rx_pkt_mu_cnt_11be_ofdma_pass",
    "rx_pkt_mu_cnt_11be_hybrid_pass",
    "rx_pkt_mu_cnt_11ax_mimo_pass",
    "rx_pkt_mu_cnt_11be_mimo_pass",
    "rx_pkt_mu_cnt_rsvd",
    "tx_pkt_cnt_11a",
    "tx_pkt_cnt_11b",
    "tx_pkt_cnt_11n",
    "tx_pkt_cnt_11ac",
    "tx_pkt_cnt_11ax",
    "tx_pkt_cnt_11gf",
    "tx_pkt_cnt_eht",
    "tx_pkt_cnt_wur",
    "tx_pkt_cnt_az",
    "tx_pkt_cnt_rsvd",
    "phy_tx_abort_cnt_pre_phy_desc_tlv",
    "phy_tx_abort_cnt_phy_desc_tlv",
    "phy_tx_abort_cnt_lsiga_tlv",
    "phy_tx_abort_cnt_lsigb_tlv",
    "phy_tx_abort_cnt_per_user_tlv",
    "phy_tx_abort_cnt_hesigb_tlv",
    "phy_tx_abort_cnt_service_tlv",
    "phy_tx_abort_cnt_pkt_end_tlv",
    
    // HTT_PHY_RESET_STATS_TLV
    "reset_stats : nfcal_iteration_count_home",
    "reset_stats : nfcal_iteration_count_scan",
    "reset_stats : nfcal_iteration_count_periodic",
    
    // HTT_PHY_RESET_COUNTERS_TLV
    "reset_counts : cf_active_low_fail_cnt",
    "reset_counts : cf_active_low_pass_cnt",
    "reset_counts : phy_off_through_vreg_cnt",
    "reset_counts : force_calibration_cnt",
    "reset_counts : rf_mode_switch_phy_off_cnt",
    "reset_counts : temperature_recal_cnt",
    
    NULL
};

// WIFISTAT 48 - HTT_ODD_PDEV_MANDATORY_TLV stats to be copied
static const char* WIFISTAT_48_COPY_STATS[] = {
    // Header
    "HTT_ODD_PDEV_MANDATORY_TLV",
    "HTT_ODD_PDEV_MANDATORY_TLV:",
    
    NULL
};

// Master list combining all WIFISTAT sections
static const char** COPY_ONLY_STATS_BY_SECTION[] = {
    WIFISTAT_1_COPY_STATS,
    WIFISTAT_2_COPY_STATS,
    WIFISTAT_3_COPY_STATS,
    WIFISTAT_4_COPY_STATS,
    WIFISTAT_5_COPY_STATS,
    WIFISTAT_6_COPY_STATS,
    WIFISTAT_8_COPY_STATS,
    WIFISTAT_9_COPY_STATS,
    WIFISTAT_10_COPY_STATS,
    WIFISTAT_12_COPY_STATS,
    WIFISTAT_17_COPY_STATS,
    WIFISTAT_18_COPY_STATS,
    WIFISTAT_21_COPY_STATS,
    WIFISTAT_37_COPY_STATS,
    WIFISTAT_47_COPY_STATS,
    WIFISTAT_48_COPY_STATS,
    NULL
};

// Helper function to check if a stat name should be copied directly
static int should_copy_stat(const char *stat_name) {
    // Trim whitespace from stat name
    while (*stat_name && isspace(*stat_name)) stat_name++;
    
    // Check against all WIFISTAT sections
    for (int section = 0; COPY_ONLY_STATS_BY_SECTION[section] != NULL; section++) {
        const char** section_stats = COPY_ONLY_STATS_BY_SECTION[section];
        
        for (int i = 0; section_stats[i] != NULL; i++) {
            const char* pattern = section_stats[i];
            size_t pattern_len = strlen(pattern);
            
            if (strncmp(stat_name, pattern, pattern_len) == 0) {
                // Check that the match is at a word boundary (followed by space, '=', '[', or end)
                const char *after = stat_name + pattern_len;
                if (*after == '\0' || *after == ' ' || *after == '=' || *after == '\t' || *after == '[') {
                    return 1;
                }
            }
        }
    }
    return 0;
}

// Helper function to check if a line contains index format (e.g., "0:123, 1:456" or "-2:0,-1:0" or "0-250 : 465")
static int is_index_format(const char *str) {
    // Look for pattern like "digit:digit" or "-digit:digit" or "digit-digit : digit" (range format)
    const char *p = str;
    while (*p) {
        // Skip whitespace
        while (*p && isspace(*p)) p++;
        
        // Check for optional minus sign followed by digit
        if (*p == '-' && isdigit(*(p+1))) {
            p += 2;
            // Check if we have colon followed by digit or minus
            if (*p == ':' && (isdigit(*(p+1)) || *(p+1) == '-')) {
                return 1;
            }
        } else if (isdigit(*p)) {
            // Skip digits
            while (*p && isdigit(*p)) p++;
            
            // Check for range format: "digit-digit : digit"
            if (*p == '-' && isdigit(*(p+1))) {
                p++;
                while (*p && isdigit(*p)) p++;
                // Skip whitespace before colon
                while (*p && isspace(*p)) p++;
                if (*p == ':') {
                    return 1;
                }
            }
            // Check for simple format: "digit:digit"
            else if (*p == ':' && (isdigit(*(p+1)) || *(p+1) == '-')) {
                return 1;
            }
        }
        p++;
    }
    return 0;
}

// Helper function to check if a line is just a separator (only '=' and whitespace)
static int is_separator_line(const char *str) {
    const char *p = str;
    while (*p) {
        if (*p != '=' && *p != ' ' && *p != '\t' && *p != '\n' && *p != '\r') {
            return 0;
        }
        p++;
    }
    return 1;
}

// Helper function to check if a line is a table row (starts with '|' and contains numeric data)
static int is_table_row(const char *str) {
    // Skip leading whitespace
    while (*str && isspace(*str)) str++;
    
    // Check if line starts with '|'
    if (*str != '|') return 0;
    
    // Check if line contains at least one digit (to distinguish data rows from header rows)
    const char *p = str + 1;
    while (*p) {
        if (isdigit(*p) || (*p == '-' && isdigit(*(p+1)))) {
            return 1;
        }
        p++;
    }
    return 0;
}

// Calculate rate of change between two wifistat files
int calculate_rate_of_change(const char *reference_path, const char *current_path, const char *output_path)
{
    FILE *ref_file = fopen(reference_path, "r");
    FILE *cur_file = fopen(current_path, "r");
    FILE *out_file = fopen(output_path, "w");

    if (!ref_file || !cur_file || !out_file) {
        fprintf(stderr, "Failed to open files for rate of change calculation\n");
        if (ref_file) fclose(ref_file);
        if (cur_file) fclose(cur_file);
        if (out_file) fclose(out_file);
        return -1;
    }

    long end_ts_offset = -1;
    {
        time_t ts_now = time(NULL);
        struct tm *ts_local = localtime(&ts_now);
        fprintf(out_file, "Start Timestamp: %s", asctime(ts_local));

        fprintf(out_file, "End Timestamp: ");
        end_ts_offset = ftell(out_file);
        // Reserve exactly 25 bytes (24 spaces + '\n') to be overwritten with
        // asctime() output once the calculation loop finishes.
        fprintf(out_file, "                        \n");
    }
    fprintf(out_file, "=== RATE OF CHANGE WIFISTATS ===\n\n");

    char ref_line[2048], cur_line[2048];
    int in_wifistat_19 = 0;  // Flag to track if we're in WIFISTAT 19 section
    
    while (fgets(ref_line, sizeof(ref_line), ref_file) != NULL &&
           fgets(cur_line, sizeof(cur_line), cur_file) != NULL) {
        
        // Check if this is a separator line (only '=' characters)
        if (is_separator_line(cur_line)) {
            fputs(cur_line, out_file);
            continue;
        }
        
        // Check if this is a section header like "=== WIFISTAT 19 ===" or "=== WIFISTAT 21 ==="
        // Skip leading whitespace first
        const char *trimmed = cur_line;
        while (*trimmed && isspace(*trimmed)) trimmed++;
        if (strncmp(trimmed, "===", 3) == 0) {
            // Check if this is WIFISTAT 19
            if (strstr(trimmed, "WIFISTAT 19")) {
                in_wifistat_19 = 1;
                fputs(cur_line, out_file);
                continue;
            }
            // Check if this is a different WIFISTAT section (end of WIFISTAT 19)
            else if (strstr(trimmed, "WIFISTAT") && in_wifistat_19) {
                in_wifistat_19 = 0;
                fputs(cur_line, out_file);
                continue;
            }
            fputs(cur_line, out_file);
            continue;
        }
        
        // If we're in WIFISTAT 19 section, just copy the line from current file
        if (in_wifistat_19) {
            fputs(cur_line, out_file);
            continue;
        }
        
        // Check if this is a table row with numeric data
        if (is_table_row(ref_line) && is_table_row(cur_line)) {
            // Parse pipe-separated values and calculate rate of change
            long long ref_values[64];
            long long cur_values[64];
            int ref_count = 0;
            int cur_count = 0;
            
            // Parse reference line
            char ref_copy[2048];
            strlcpy(ref_copy, ref_line, sizeof(ref_copy));
            
            char *ref_saveptr;
            char *ref_token = strtok_r(ref_copy, "|", &ref_saveptr);
            while (ref_token && ref_count < 64) {
                long long val;
                if (sscanf(ref_token, "%lld", &val) == 1) {
                    ref_values[ref_count++] = val;
                }
                ref_token = strtok_r(NULL, "|", &ref_saveptr);
            }
            
            // Parse current line
            char cur_copy[2048];
            strlcpy(cur_copy, cur_line, sizeof(cur_copy));
            
            char *cur_saveptr;
            char *cur_token = strtok_r(cur_copy, "|", &cur_saveptr);
            while (cur_token && cur_count < 64) {
                long long val;
                if (sscanf(cur_token, "%lld", &val) == 1) {
                    cur_values[cur_count++] = val;
                }
                cur_token = strtok_r(NULL, "|", &cur_saveptr);
            }
            
            // Calculate rate of change and output in table format
            fprintf(out_file, "|");
            int min_count = (ref_count < cur_count) ? ref_count : cur_count;
            for (int i = 0; i < min_count; i++) {
                long long rate = cur_values[i] - ref_values[i];
                fprintf(out_file, "%10lld|", rate);
            }
            fprintf(out_file, "\n");
            continue;
        }
        
        // Check if line starts with '|' but is not a data row (e.g., table header)
        if (cur_line[0] == '|' || (isspace(cur_line[0]) && strchr(cur_line, '|'))) {
            // This is likely a table header or non-numeric table row, just copy it
            fputs(cur_line, out_file);
            continue;
        }
        
        // Check if this is a header line starting with "HTT_TX" or similar patterns
        // These should be copied as-is without any processing
        const char *line_start = cur_line;
        while (*line_start && isspace(*line_start)) line_start++;
        if (strncmp(line_start, "HTT_TX", 6) == 0 ||
            strncmp(line_start, "HTT_PDEV", 8) == 0 ||
            strncmp(line_start, "WMI_CTRL", 8) == 0) {
            // Check if line ends with colon (possibly followed by descriptive text)
            char *colon = strchr(cur_line, ':');
            if (colon) {
                char *after_colon = colon + 1;
                while (*after_colon && isspace(*after_colon)) after_colon++;
                // If no equals sign and text after colon is not index format, it's a header
                if (!strchr(cur_line, '=') && 
                    (*after_colon == '\0' || *after_colon == '\n' || *after_colon == '\r' || 
                     *after_colon == '(' || !is_index_format(after_colon))) {
                    fputs(cur_line, out_file);
                    continue;
                }
            }
        }
        
        // Find separator in the line - could be '=' or ':'
        // Use strrchr to find the LAST occurrence (for lines with multiple '=' like "TOTAL STREAMS = 2) = 0")
        char *ref_sep = strrchr(ref_line, '=');
        char *cur_sep = strrchr(cur_line, '=');
        
        // If no '=' found, try ':' (for stats like "tx_mgmt_subtype_enq_ok:  0:0, 1:1, ...")
        // For colon, we want the first occurrence since it's the stat name separator
        if (!ref_sep) {
            ref_sep = strchr(ref_line, ':');
            // Check if this is a header line (colon at end with descriptive text, not index format)
            if (ref_sep) {
                char *after_colon = ref_sep + 1;
                // Skip whitespace
                while (*after_colon && isspace(*after_colon)) after_colon++;
                // If what follows is not index format, this is a header line
                if (!is_index_format(after_colon)) {
                    fputs(cur_line, out_file);
                    continue;
                }
            }
        }
        if (!cur_sep) {
            cur_sep = strchr(cur_line, ':');
            // Check if this is a header line (colon at end with descriptive text, not index format)
            if (cur_sep) {
                char *after_colon = cur_sep + 1;
                // Skip whitespace
                while (*after_colon && isspace(*after_colon)) after_colon++;
                // If what follows is not index format, this is a header line
                if (!is_index_format(after_colon)) {
                    fputs(cur_line, out_file);
                    continue;
                }
            }
        }
        
        if (!ref_sep || !cur_sep) {
            // No separator found - this is a header or text line, just copy it
            fputs(cur_line, out_file);
            continue;
        }
        
        // Extract the stat name (everything before separator)
        size_t name_len = ref_sep - ref_line;
        char stat_name[256];
        if (name_len >= sizeof(stat_name)) {
            // Name too long, just copy the line
            fputs(cur_line, out_file);
            continue;
        }
        strlcpy(stat_name, ref_line, name_len + 1);
        
        // Check if this stat should be copied directly without rate of change calculation
        if (should_copy_stat(stat_name)) {
            fputs(cur_line, out_file);
            continue;
        }
        
        // Determine the separator character used
        char sep_char = *ref_sep;
        
        // Skip past separator and any whitespace/extra '=' signs
        char *ref_val_start = ref_sep + 1;
        char *cur_val_start = cur_sep + 1;
        
        // Skip whitespace and additional '=' signs (for double equals case)
        while (*ref_val_start && (isspace(*ref_val_start) || *ref_val_start == '=')) {
            ref_val_start++;
        }
        while (*cur_val_start && (isspace(*cur_val_start) || *cur_val_start == '=')) {
            cur_val_start++;
        }
        
        // Check if this is index format
        if (is_index_format(ref_val_start) && is_index_format(cur_val_start)) {
            // Handle index format: "0:val0, 1:val1, 2:val2, ..."
            // Check if original line had double equals (e.g., "stat = = 0:1, 1:2")
            char *check_double_eq = ref_sep + 1;
            int has_double_equals = 0;
            while (*check_double_eq && isspace(*check_double_eq)) check_double_eq++;
            if (*check_double_eq == '=') {
                has_double_equals = 1;
            }
            
            // Output stat name with proper formatting
            if (sep_char == ':') {
                // For colon separator, just use colon
                fprintf(out_file, "%s: ", stat_name);
            } else if (has_double_equals) {
                fprintf(out_file, "%s= = ", stat_name);
            } else {
                fprintf(out_file, "%s= ", stat_name);
            }
            
            // Parse all index:value pairs from reference into an array
            typedef struct {
                char key[64];  // Store the key as string (could be "0", "-2", or "0-250")
                long long value;
            } IndexValue;
            
            IndexValue ref_values[256];
            IndexValue cur_values[256];
            int ref_count = 0;
            int cur_count = 0;
            
            // Parse reference values
            char ref_copy[2048];
            strlcpy(ref_copy, ref_val_start, sizeof(ref_copy));
            
            char *ref_saveptr;
            char *ref_token = strtok_r(ref_copy, ",", &ref_saveptr);
            while (ref_token && ref_count < 256) {
                // Find the colon separator
                char *colon = strchr(ref_token, ':');
                if (colon) {
                    // Extract key (everything before colon, trimmed)
                    char key[64];
                    int key_len = colon - ref_token;
                    if (key_len >= sizeof(key)) key_len = sizeof(key) - 1;
                    strlcpy(key, ref_token, key_len + 1);
                    
                    // Trim whitespace from key
                    char *key_start = key;
                    while (*key_start && isspace(*key_start)) key_start++;
                    char *key_end = key_start + strlen(key_start) - 1;
                    while (key_end > key_start && isspace(*key_end)) *key_end-- = '\0';
                    
                    // Extract value (everything after colon)
                    long long val;
                    if (sscanf(colon + 1, "%lld", &val) == 1) {
                        strlcpy(ref_values[ref_count].key, key_start, sizeof(ref_values[ref_count].key));
                        ref_values[ref_count].value = val;
                        ref_count++;
                    }
                }
                ref_token = strtok_r(NULL, ",", &ref_saveptr);
            }
            
            // Parse current values
            char cur_copy[2048];
            strlcpy(cur_copy, cur_val_start, sizeof(cur_copy));
            
            char *cur_saveptr;
            char *cur_token = strtok_r(cur_copy, ",", &cur_saveptr);
            while (cur_token && cur_count < 256) {
                // Find the colon separator
                char *colon = strchr(cur_token, ':');
                if (colon) {
                    // Extract key (everything before colon, trimmed)
                    char key[64];
                    int key_len = colon - cur_token;
                    if (key_len >= sizeof(key)) key_len = sizeof(key) - 1;
                    strlcpy(key, cur_token, key_len + 1);
                    
                    // Trim whitespace from key
                    char *key_start = key;
                    while (*key_start && isspace(*key_start)) key_start++;
                    char *key_end = key_start + strlen(key_start) - 1;
                    while (key_end > key_start && isspace(*key_end)) *key_end-- = '\0';
                    
                    // Extract value (everything after colon)
                    long long val;
                    if (sscanf(colon + 1, "%lld", &val) == 1) {
                        strlcpy(cur_values[cur_count].key, key_start, sizeof(cur_values[cur_count].key));
                        cur_values[cur_count].value = val;
                        cur_count++;
                    }
                }
                cur_token = strtok_r(NULL, ",", &cur_saveptr);
            }
            
            // Calculate rate of change for each index in current values
            int first = 1;
            for (int i = 0; i < cur_count; i++) {
                const char *cur_key = cur_values[i].key;
                long long cur_val = cur_values[i].value;
                long long ref_val = 0;
                
                // Find matching key in reference values
                for (int j = 0; j < ref_count; j++) {
                    if (strcmp(ref_values[j].key, cur_key) == 0) {
                        ref_val = ref_values[j].value;
                        break;
                    }
                }
                
                // Calculate rate of change
                long long rate = cur_val - ref_val;
                
                if (!first) fprintf(out_file, ", ");
                fprintf(out_file, "%s:%lld", cur_key, rate);
                first = 0;
            }
            fprintf(out_file, "\n");
            
        } else {
            // Try to parse as simple numeric value
            long long ref_val = 0, cur_val = 0;
            int ref_parsed = sscanf(ref_val_start, "%lld", &ref_val);
            int cur_parsed = sscanf(cur_val_start, "%lld", &cur_val);
            
            if (ref_parsed == 1 && cur_parsed == 1) {
                // Simple numeric stat
                long long rate = cur_val - ref_val;
                fprintf(out_file, "%s= %lld\n", stat_name, rate);
            } else if (ref_parsed == 1 || cur_parsed == 1) {
                // One parsed successfully, treat missing value as 0
                long long rate = cur_val - ref_val;
                fprintf(out_file, "%s= %lld\n", stat_name, rate);
            } else {
                // Not a numeric value we can parse, just copy the current line
                fputs(cur_line, out_file);
            }
        }
    }

    fclose(ref_file);
    fclose(cur_file);

    if (end_ts_offset >= 0) {
        time_t ts_end = time(NULL);
        struct tm *ts_end_local = localtime(&ts_end);
        const char *end_str = asctime(ts_end_local);  // 25 bytes: "Day Mon DD HH:MM:SS YYYY\n"
        fflush(out_file);
        if (fseek(out_file, end_ts_offset, SEEK_SET) == 0) {
            if (fwrite(end_str, 1, 25, out_file) != 25) {
                fprintf(stderr, "Failed to write end timestamp to: %s\n", output_path);
            }
        } else {
            fprintf(stderr, "Failed to seek for end timestamp in: %s\n", output_path);
        }
    }

    fclose(out_file);
    
    fprintf(stderr, "Rate of change calculated and saved to: %s\n", output_path);
    return 0;
}
