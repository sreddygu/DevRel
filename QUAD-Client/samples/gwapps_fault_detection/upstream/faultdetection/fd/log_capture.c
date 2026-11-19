/*
 *  Copyright (c) Qualcomm Technologies, Inc. and/or its subsidiaries. 
 *  All rights reserved.
 *  Confidential and Proprietary - Qualcomm Technologies, Inc.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dirent.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <linux/limits.h>
#include "log_capture.h"
#include "syslog_processing.h"
#include "debugging.h"

#define FILE_PATH_LEN 1024
#define SYSLOG_RESET_INTERVAL_SECONDS (20 * 60)  // 20 minutes

int start_pkt_log()
{
	if(ath_build){
		log_message(LOG_LEVEL_AD_LIB_DEBUG,"PKT_LOG for ATH\n");
		DIR *dir = opendir(stat_folder_prefix);
		if (dir == NULL) {
        	perror("opendir failed");
		        return -1;
    		}
		char *radio_names[MAX_RADIOS];
	        struct dirent *entry;
	        int count = 0;
		int active_count = parse_center_freqs(active_freqs, MAX_RADIO_FREQS);
		if (active_count <= 0) {
 			log_message(LOG_LEVEL_AD_LIB_DEBUG, "Failed to detect active radio frequencies\n");
	     	 	closedir(dir);
		        return -1;
		}
		while ((entry = readdir(dir)) != NULL) {
    		    if ((strstr(entry->d_name, "pci") != NULL) || (strstr(entry->d_name, "ahb") != NULL)) {
	           	 int freq = get_radio_center_freq(entry->d_name); // returns MHz
	        	    int found = 0;
		            for (int j = 0; j < active_count; j++) {
        		        if (freq == active_freqs[j]) {
                		    found = 1;
		                    break;
        		        }
            		    }
		            if (found) {
        		        radio_names[count] = strdup(entry->d_name);
				if (radio_names[count] == NULL) {
		                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Memory allocation failed for radio name\n");
                		        closedir(dir);
		                        // Free previously allocated names
                		        for (int k = 0; k < count; k++) {
		                            free(radio_names[k]);
                        		}
		                        return -1;
        	            	}
                		count++;
		            } else {
	        	        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Skipping %s (freq %d not active)\n", entry->d_name, freq);
        	    	   }
               	   }
    		}
		log_message(LOG_LEVEL_AD_LIB_DEBUG,"ATH radio count %d\n");
		for (int i = 0; i < count; i++) {
			char pkt_size[FILE_PATH_LEN];
			char pkt_start[FILE_PATH_LEN];
			FILE *size_file = NULL;
		        FILE *start_file = NULL;
			int size_ret = 0, start_ret = 0;
			size_ret = snprintf(pkt_size, FILE_PATH_LEN, "echo 10000000 > /sys/kernel/debug/ath12k/%s/mac0/pktlog/size", radio_names[i]);
			start_ret = snprintf(pkt_start, FILE_PATH_LEN, "echo 1 > /sys/kernel/debug/ath12k/%s/mac0/pktlog/start", radio_names[i]);
			if(size_ret >= FILE_PATH_LEN || start_ret >= FILE_PATH_LEN){
				log_message(LOG_LEVEL_AD_LIB_DEBUG, "Path truncated for pktlog size command\n");
   			        for (int k = 0; k < count; k++) {
				        free(radio_names[k]);
    				}
				closedir(dir);
				return -1;
			}
			log_message(LOG_LEVEL_AD_LIB_DEBUG, "|--PKT_LOG--|size_cmd:%s\nstart_cmd:%s\n", pkt_size, pkt_start);
			size_file = popen(pkt_size, "w");
			if (size_file == NULL) {
			        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not run command: %s\n", pkt_size);
				for (int k = 0; k < count; k++) {
			            free(radio_names[k]);
        			}
			        closedir(dir);
			        return -1;
    			}
			pclose(size_file);
			start_file = popen(pkt_start, "w");
                        if (start_file == NULL) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not run command: %s\n", pkt_size);
				for (int k = 0; k < count; k++) {
			            free(radio_names[k]);
        			}
			        closedir(dir);
                                return -1;
                        }
                        pclose(start_file);
		}
		for(int i = 0; i < count; i++) {
			free(radio_names[i]);
		}
                if(dir){
                        closedir(dir);
                }
	} else {
	        char cmd[CMD_LEN];
        	int j = 0;
	        FILE *host_cmd;
        	init_aps_and_radios();
	        for(j = 0; j < radios_count; j++){
        	        strlcpy(cmd, PKT_CMD_1, CMD_LEN);
                	strlcat(cmd, radios[j], CMD_LEN);
	                strlcat(cmd, PKT_CMD_2, CMD_LEN);
        	        log_message(LOG_LEVEL_AD_LIB_DEBUG,"CMD: %s\n", cmd);
                	host_cmd = popen(cmd, "r");
	                if(host_cmd == NULL){
        	                log_message(LOG_LEVEL_AD_LIB_DEBUG,"could Not run packet log command\n");
                	        return -1;
                	}
	                if(host_cmd) pclose(host_cmd);
        	}
	}        return 0;
}

// Capture all wifistats and concatenate into a single file
// If pkt_log is true, also handles packet log operations (stop/copy/restart)
int capture_wifistats_to_file(int rad_id, const char *output_path, int pkt_log)
{
        char cmd[CMD_LEN];
        FILE *host_cmd;
        FILE *conf_fp;
        int band = cur_bands[rad_id];

        // Open output file for writing
        FILE *output_file = fopen(output_path, "w");
        if (output_file == NULL) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not open output file: %s\n", output_path);
                return -1;
        }

        // Write timestamp at the top of the file
        {
                time_t ts_now = time(NULL);
                struct tm *ts_local = localtime(&ts_now);
                fprintf(output_file, "Timestamp: %s", asctime(ts_local));
        }

        /**For Ath**/
        if(ath_build){
                DIR *dir = opendir(stat_folder_prefix);
                if (dir == NULL) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "opendir failed for path: %s\n", stat_folder_prefix);
                        fclose(output_file);
                        return -1;
                }

                log_message(LOG_LEVEL_AD_LIB_DEBUG, "[capture_wifistats] Looking for radio with band %d\n", band);
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "[capture_wifistats] Searching in directory: %s\n", stat_folder_prefix);

                struct dirent *entry;
                char *radio_name = NULL;
                int entry_count = 0;

                if ((entry = readdir(dir)) == NULL) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Entry readdir is null on first read\n");
                }

                while ((entry = readdir(dir)) != NULL) {
                        entry_count++;
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[capture_wifistats] Entry #%d: %s\n", entry_count, entry->d_name);
                        
                        if ((strstr(entry->d_name, "pci") != NULL) || (strstr(entry->d_name, "ahb") != NULL)) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "[capture_wifistats] Found pci/ahb entry: %s\n", entry->d_name);
                                
                                int freq = get_radio_center_freq(entry->d_name);
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "[capture_wifistats] freq variable (raw): %d\n", freq);
                                
                                freq = freq / 1000;
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "[capture_wifistats] freq divided by 1000: %d\n", freq);
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "[capture_wifistats] target band: %d\n", band);
                                
                                if(freq == band){
                                        radio_name = strdup(entry->d_name);
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[capture_wifistats] MATCH! Capturing wifistats for %s (band %d)\n", entry->d_name, freq);
                                        break;
                                } else {
                                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[capture_wifistats] NO MATCH: Read Frequency: %d for folder %s (looking for band %d)\n", freq, entry->d_name, band);
                                }
                        } else {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "[capture_wifistats] Skipping entry (not pci/ahb): %s\n", entry->d_name);
                        }
                }
                
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "[capture_wifistats] Total entries scanned: %d\n", entry_count);
                
                if (radio_name == NULL) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[capture_wifistats] ERROR: No radio found for band %d after scanning %d entries\n", band, entry_count);
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "[capture_wifistats] Directory path was: %s\n", stat_folder_prefix);
                        closedir(dir);
                        fclose(output_file);
                        return -1;
                }
                closedir(dir);

                // Capture and concatenate all wifistats
                for (int i = 0; i < ANOMALY_STAT_CNT; i++) {
                        char echo_path[FILE_PATH_LEN];
                        char read_path[FILE_PATH_LEN];
                        FILE *echo_file = NULL;
                        FILE *read_file = NULL;

                        snprintf(echo_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, radio_name, suffix_echo);
                        snprintf(read_path, FILE_PATH_LEN, "%s%s%s", stat_folder_prefix, radio_name, suffix_read);

                        char echo_cmd[CMD_LEN];
                        snprintf(echo_cmd, sizeof(echo_cmd), "echo %d > %s", anomaly_stat[i], echo_path);
                        echo_file = popen(echo_cmd, "w");
                        if (echo_file == NULL) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not run echo command: %s\n", echo_cmd);
                                continue;
                        }
                        pclose(echo_file);

                        // Read the wifistat and append to output file
                        read_file = fopen(read_path, "r");
                        if (read_file == NULL) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not open wifistat file: %s\n", read_path);
                                continue;
                        }

                        fprintf(output_file, "=== WIFISTAT %d on %dG ===\n", anomaly_stat[i], band);
                        char line[1024];
                        while (fgets(line, sizeof(line), read_file) != NULL) {
                                fputs(line, output_file);
                        }
                        fprintf(output_file, "\n");
                        fclose(read_file);
                }
		if(pkt_log){
		   char pkt_stop[FILE_PATH_LEN];
        	   char pkt_copy[FILE_PATH_LEN];
		   FILE *stop_file = NULL;
                   FILE *copy_file = NULL;
		   snprintf(pkt_stop, FILE_PATH_LEN, "echo 0 > /sys/kernel/debug/ath12k/%s/mac0/pktlog/start", radio_name);
		   snprintf(pkt_copy, FILE_PATH_LEN, "cp /sys/kernel/debug/ath12k/%s/mac0/pktlog/dump %s/pktlog.dat", radio_name, log_folder);
		   log_message(LOG_LEVEL_AD_LIB_DEBUG, "pkt_stop: %s\npkt_copy: %s\n", pkt_stop, pkt_copy);
		   stop_file = popen(pkt_stop, "w");
		   if (stop_file == NULL) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not run command: %s\n", pkt_stop);
                   	return -1;
                   }
		   pclose(stop_file);
		   copy_file = popen(pkt_copy, "w");
		   if (copy_file == NULL) {
                        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Could not run command: %s\n", pkt_copy);
                        return -1;
                   }
		   pclose(copy_file);
		   start_pkt_log();
	       }
               if (radio_name) {
               	   free(radio_name);
                   radio_name = NULL;
               }
        } else {
                /***For Prop***/
                init_aps_and_radios();

                for(int i = 0; i < ANOMALY_STAT_CNT; i++) {
                        char stat_str[INT_STR];
                        char temp_file[CMD_LEN];
                        memset(cmd, '\0', CMD_LEN);
                        snprintf(stat_str, INT_STR, "%d", anomaly_stat[i]);
                        snprintf(temp_file, CMD_LEN, "%swifistat_temp_%d.txt", log_dir, anomaly_stat[i]);

                        strlcpy(cmd, WIFI_STR, CMD_LEN);
                        strlcat(cmd, SPACE, CMD_LEN);
                        strlcat(cmd, radios[rad_id], CMD_LEN);
                        strlcat(cmd, SPACE, CMD_LEN);
                        strlcat(cmd, stat_str, CMD_LEN);
                        strlcat(cmd, SPACE, CMD_LEN);
                        if(anomaly_stat[i] == 21)
                                strlcat(cmd, WMI_STR, CMD_LEN);
                        strlcat(cmd, REDIR, CMD_LEN);
                        strlcat(cmd, temp_file, CMD_LEN);

                        host_cmd = popen(cmd, "r");
                        if(host_cmd == NULL){
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"Could not run wifistats command\n");
                                continue;
                        }
                        pclose(host_cmd);

                        // Read temp file and append to output
                        FILE *temp_fp = fopen(temp_file, "r");
                        if (temp_fp) {
                                fprintf(output_file, "=== WIFISTAT %d on %dG ===\n", anomaly_stat[i], band);
                                char line[1024];
                                while (fgets(line, sizeof(line), temp_fp) != NULL) {
                                        fputs(line, output_file);
                                }
                                fprintf(output_file, "\n");
                                fclose(temp_fp);
                                remove(temp_file);
                        }
                }
                
                // Handle packet log operations for Prop builds (after capturing wifistats)
                if (pkt_log) {
                        // Stop packet log
                        strlcpy(cmd, PKT_STP, CMD_LEN);
                        strlcat(cmd, radios[rad_id], CMD_LEN);
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"CMD: %s\n", cmd);
                        host_cmd = popen(cmd, "r");
                        if(host_cmd == NULL){
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"could Not run pkt log stop command\n");
                                fclose(output_file);
                                return -1;
                        }
                        pclose(host_cmd);
                        
                        // Copy packet log
                        memset(cmd, '\0', CMD_LEN);
                        strlcpy(cmd, PKT_CPY, CMD_LEN);
                        strlcat(cmd, radios[rad_id], CMD_LEN);
                        strlcat(cmd, SPACE, CMD_LEN);
                        strlcat(cmd, log_folder, CMD_LEN);
                        strlcat(cmd, FWD_SLSH, CMD_LEN);
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"CMD: %s\n", cmd);
                        host_cmd = popen(cmd, "r");
                        if(host_cmd == NULL){
                                log_message(LOG_LEVEL_AD_LIB_DEBUG,"could Not run copy command\n");
                                fclose(output_file);
                                return -1;
                        }
                        pclose(host_cmd);
                        
                        // Restart packet log
                        start_pkt_log();
                }
        }

        fclose(output_file);
        log_message(LOG_LEVEL_AD_LIB_DEBUG, "Wifistats captured to: %s\n", output_path);
        return 0;
}

int save_syslog(const char *notif_path)
{
        // regular
        if (save_logs_to_usb == 0) {
                char cmd[CMD_LEN];
                FILE *host_cmd;

                if(!sys_log_avail) {
                        int ret = snprintf(cur_sys_path, PATH_MAX, "%s/%s", log_folder, SYS_LOG_NAME);
                        if (ret >= PATH_MAX) {
                                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Path truncated: %s/%s exceeds PATH_MAX\n", log_folder, SYS_LOG_NAME);
                                return 0;
                        }
                        snprintf(cmd, CMD_LEN, "logread > %s", cur_sys_path);
                        sys_log_avail = 1;
                } else {
                        snprintf(cmd, CMD_LEN, "cp %s %s/%s", cur_sys_path, log_folder, SYS_LOG_NAME);
                }
                log_message(LOG_LEVEL_AD_LIB_DEBUG,"SYSLOG CMD: %s\n", cmd);
                host_cmd = popen(cmd, "r");
                if(host_cmd == NULL){
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"could Not run syslog save command\n");
                        return 0;
                }
                pclose(host_cmd);
                reset_syslog();
                return 0;

        // usb
        } else {
                return save_syslog_usb(notif_path);
        }
}

int save_syslog_usb(const char *notif_path)
{
    char cmd[CMD_LEN];
    FILE *host_cmd;

    if(!sys_log_avail) {
        int ret = snprintf(cur_sys_path, PATH_MAX, "%s/%s", log_folder, SYS_LOG_NAME);
        if (ret >= PATH_MAX) {
                log_message(LOG_LEVEL_AD_LIB_DEBUG, "Path truncated: %s/%s exceeds PATH_MAX\n", log_folder, SYS_LOG_NAME);
                return 0;
        }
        snprintf(cmd, CMD_LEN, "cp /mnt/usb/hostapd.log %s", cur_sys_path);
        // snprintf(cmd, CMD_LEN, "cp /mnt/usb/hostapd.log %s/%s", log_folder, SYS_LOG_NAME);
        sys_log_avail = 1;
    } else {
	snprintf(cmd, CMD_LEN, "cp %s %s/%s", cur_sys_path, log_folder, SYS_LOG_NAME);
    }

    log_message(LOG_LEVEL_AD_LIB_DEBUG,"Inside of save_syslog");
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"SYSLOG CMD: %s\n", cmd);
    host_cmd = popen(cmd, "r");
    if(host_cmd == NULL){
     	log_message(LOG_LEVEL_AD_LIB_DEBUG,"could Not run syslog save command\n");
    	return 0;
    }
    pclose(host_cmd);
    reset_syslog();
    return 0;
}

void reset_syslog()
{
        // regular
        if (save_logs_to_usb == 0) {

                char cmd[CMD_LEN];
                FILE *host_cmd;
                strlcpy(cmd, SYS_END, CMD_LEN);
                strlcat(cmd, COL_STR, CMD_LEN);
                strlcat(cmd, SYS_START, CMD_LEN);
                host_cmd = popen(cmd, "r");
                if(host_cmd == NULL){
                        log_message(LOG_LEVEL_AD_LIB_DEBUG,"could Not run restart syslog command\n");
                        return;
                }
                if(host_cmd) pclose(host_cmd);
        // usb
        } else {
                reset_syslog_usb();
        }
}

void reset_syslog_usb(void)
{
    char cmd[CMD_LEN];
    FILE *host_cmd;

    // NOTE: Use the real '>' character, not '&gt;'
    strlcpy(cmd, "> /mnt/usb/hostapd.log", CMD_LEN);

    host_cmd = popen(cmd, "r");
    if (host_cmd == NULL) {
        log_message(LOG_LEVEL_AD_LIB_DEBUG,
                    "could Not run truncate command: %s\n", cmd);
        return;
    }
    log_message(LOG_LEVEL_AD_LIB_DEBUG,"RESET SYSLOG CMD: %s\n", cmd);
    pclose(host_cmd);
}

void check_and_reset_syslog_if_needed(void)
{
	// Check if 20 minutes have passed since last send_note() call
	time_t now = time(NULL);
	if (g_last_send_note_time > 0) {
		double elapsed = difftime(now, g_last_send_note_time);
		if (elapsed >= SYSLOG_RESET_INTERVAL_SECONDS) {
			// Check if USB is mounted
			if (access("/mnt/usb/hostapd.log", F_OK) == 0) {
				log_message(LOG_LEVEL_AD_LIB_DEBUG, 
					"20 minutes elapsed since last anomaly, resetting syslog (elapsed: %.0f seconds)\n", 
					elapsed);
				reset_syslog();
				g_last_send_note_time = now; // Reset the timer
			}
		}
	} else {
		// Initialize the timer on first call
		g_last_send_note_time = now;
	}
}
