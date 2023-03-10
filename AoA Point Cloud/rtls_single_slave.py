import os
import time
import json
import queue
import threading
import datetime
import numpy as np
from pyod.models.knn import KNN

import pandas as pd

from rtls_util import RtlsUtil, RtlsUtilLoggingLevel, RtlsUtilException, RtlsUtilTimeoutException, \
    RtlsUtilNodesNotIdentifiedException, RtlsUtilScanNoResultsException

yy = []
## User function to proces
def results_parsing(q):
    while True:
        try:
            data = q.get(block=True, timeout=0.5)
            if isinstance(data, dict):
                #data_time = datetime.datetime.now().strftime("[%m:%d:%Y %H:%M:%S:%f] :")
                if data["name"] == "CC26x2 Master":

                    with open("./aoa_results/aoa_data.txt", "a") as file1:
                        # Writing data to a file
                        file1.write(str(data["payload"]["angle"]) + "\n")
                    yy.append(data["payload"]["angle"])
            elif isinstance(data, str) and data == "STOP":
                print("STOP Command Received")
                break
            else:
                pass
        except queue.Empty:
            continue



## Main Function
def aoa_single_main():
    ## Predefined parameters
    slave_bd_addr = None  # "80:6F:B0:1E:38:C3" # "54:6C:0E:83:45:D8"
    scan_time_sec = 5
    connect_interval_mSec = 180#100

    ## Continuous Connection Info Demo Enable / Disable
    cci = False
    ## Angle of Arival Demo Enable / Disable
    aoa = True
    ## Time of Flight Demo Enable / Disable
    tof = False
    tof_use_calibrate_from_nv = False
    ## Switch TOF Role Demo Enable / Disable
    tof_switch_role = False
    ## Update connection interval on the fly Demo Enable / Disable
    update_conn_interval = False
    new_connect_interval_mSec = 80

    ## Taking python file and replacing extension from py into log for output logs + adding data time stamp to file
    data_time = datetime.datetime.now().strftime("%m_%d_%Y_%H_%M_%S")
    logging_file_path = os.path.join(os.path.curdir, 'rtls_util_logs')
    if not os.path.isdir(logging_file_path):
        os.makedirs(logging_file_path)
    logging_file = os.path.join(logging_file_path, f"{data_time}_rtls_utils_logs")

    ## Initialize RTLS Util instance
    rtlsUtil = RtlsUtil(logging_file, RtlsUtilLoggingLevel.INFO)
    ## Update general time out for all action at RTLS Util [Default timeout : 30 sec]
    rtlsUtil.timeout = 30

    all_nodes = []
    try:
        devices = [
            # {"com_port": "COM7", "baud_rate": 460800, "name": "CC26x2 Master"},
            # {"com_port": "COM6", "baud_rate": 460800, "name": "CC26x2 Passive"},
            {"com_port": "COM3", "baud_rate": 460800, "name": "CC26x2 Master"},
            # {"com_port": "COM23", "baud_rate": 460800, "name": "CC2640r2 TOF Master"},
            # {"com_port": "COM21", "baud_rate": 460800, "name": "CC2640r2 TOF Passive"}
        ]
        ## Setup devices
        master_node, passive_nodes, all_nodes = rtlsUtil.set_devices(devices)
        print(f"Master : {master_node} \nPassives : {passive_nodes} \nAll : {all_nodes}")

        ## Reset devices for initial state of devices
        rtlsUtil.reset_devices()
        print("Devices Reset")

        ## Code below demonstrates two option of scan and connect
        ## 1. Then user know which slave to connect
        ## 2. Then user doesn't mind witch slave to use
        if slave_bd_addr is not None:
            print(f"Start scan of {slave_bd_addr} for {scan_time_sec} sec")
            scan_results = rtlsUtil.scan(scan_time_sec, slave_bd_addr)
            print(f"Scan Results: {scan_results}")

            rtlsUtil.ble_connect(slave_bd_addr, connect_interval_mSec)
            print("Connection Success")
        else:
            print(f"Start scan for {scan_time_sec} sec")
            scan_results = rtlsUtil.scan(scan_time_sec)
            print(f"Scan Results: {scan_results}")

            rtlsUtil.ble_connect(scan_results[0], connect_interval_mSec)
            print("Connection Success")

        ## Start continues connection info feature
        if cci:
            if rtlsUtil.is_tof_supported(all_nodes):
                ## Setup thread to pull out received data from devices on screen
                th_cci_parsing = threading.Thread(target=results_parsing, args=(rtlsUtil.conn_info_queue,))
                th_cci_parsing.setDaemon(True)
                th_cci_parsing.start()
                print("CCI Callback Set")

                rtlsUtil.cci_start()
                print("CCI Started")
            else:
                print("=== Warning ! One of the devices does not support CCI functionality ===")

        ## Start angle of arrival feature
        if aoa:
            if rtlsUtil.is_aoa_supported(all_nodes):
                aoa_params = {
                    "aoa_run_mode": "AOA_MODE_ANGLE",  ## AOA_MODE_ANGLE, AOA_MODE_PAIR_ANGLES, AOA_MODE_RAW
                    "aoa_cc2640r2": {
                        "aoa_cte_scan_ovs": 4,
                        "aoa_cte_offset": 4,
                        "aoa_cte_length": 20,
                        "aoa_sampling_control": int('0x00', 16),
                        ## bit 0   - 0x00 - default filtering, 0x01 - RAW_RF no filtering - not supported,
                        ## bit 4,5 - 0x00 - default both antennas, 0x10 - ONLY_ANT_1, 0x20 - ONLY_ANT_2
                    },
                    "aoa_cc26x2": {
                        "aoa_slot_durations": 1,
                        "aoa_sample_rate": 1,
                        "aoa_sample_size": 1,
                        "aoa_sampling_control": int('0x10', 16),
                        ## bit 0   - 0x00 - default filtering, 0x01 - RAW_RF no filtering,
                        ## bit 4,5 - default: 0x10 - ONLY_ANT_1, optional: 0x20 - ONLY_ANT_2
                        "aoa_sampling_enable": 1,
                        "aoa_pattern_len": 3,
                        "aoa_ant_pattern": [0, 1, 2]
                    }
                }
                rtlsUtil.aoa_set_params(aoa_params)
                print("AOA Params Set")

                ## Setup thread to pull out received data from devices on screen
                th_aoa_results_parsing = threading.Thread(target=results_parsing, args=(rtlsUtil.aoa_results_queue,))
                th_aoa_results_parsing.setDaemon(True)
                th_aoa_results_parsing.start()
                print("AOA Callback Set")

                rtlsUtil.aoa_start(cte_length=20, cte_interval=1)
                print("AOA Started")
            else:
                print("=== Warning ! One of the devices does not support AoA functionality ===")

        ## Start time of flight feature
        if tof:
            if rtlsUtil.is_tof_supported(all_nodes):
                tof_params = {
                "tof_sample_mode": "TOF_MODE_DIST",  ## TOF_MODE_DIST, TOF_MODE_STAT, TOF_MODE_RAW
                "tof_run_mode": "TOF_MODE_CONT",
                "tof_slave_lqi_filter": 25,
                "tof_post_process_lqi_thresh": 20,
                "tof_post_process_magn_ratio": 111,
                "tof_samples_per_burst": 256,
                "tof_freq_list": [2416, 2418, 2420, 2424, 2430, 2432, 2436, 2438],
                "tof_auto_rssi": -55,
                }
                rtlsUtil.tof_set_params(tof_params)
                print("TOF Paramas + Seed Set")

                ## Code below demonstrate option where the user doesn't want to use internal calibration
                if tof_params['tof_sample_mode'] == "TOF_MODE_DIST":
                    rtlsUtil.tof_calibrate(samples_per_freq=1024, distance=1, use_nv_calib=tof_use_calibrate_from_nv)
                    print("Calibration Done")

                    # print(json.dumps(rtlsUtil.tof_get_calib_info(), indent=4))
                    # print("Calibration Info Done")

                ## Setup thread to pull out received data from devices on screen
                th_tof_results_parsing = threading.Thread(target=results_parsing, args=(rtlsUtil.tof_results_queue,))
                th_tof_results_parsing.setDaemon(True)
                th_tof_results_parsing.start()
                print("TOF Callback Set")

                rtlsUtil.tof_start()
                print("TOF Started")

                ## Start switch role feature while TOF is running
                if tof_switch_role and len(passive_nodes) > 0:
                    time.sleep(2)
                    print("Slept for 2 sec before switching roles")

                    rtlsUtil.tof_stop()
                    print("TOF Stopped")

                    master_capab = rtlsUtil.get_devices_capability(nodes=[master_node])[0]
                    print(f"RTLS MASTER capability before role switch: {json.dumps(master_capab, indent=4)}")

                    rtlsUtil.tof_role_switch(tof_master_node=master_node, tof_passive_node=passive_nodes[0])
                    print("TOF Role Switch Done")

                    master_capab = rtlsUtil.get_devices_capability(nodes=[master_node])[0]
                    print(f"RTLS MASTER capability after role switch: {json.dumps(master_capab, indent=4)}")

                    rtlsUtil.tof_calibrate(samples_per_freq=1000, distance=1)
                    print("Calibration Done")

                    rtlsUtil.tof_start()
                    print("TOF Re-Started")
            else:
                print("=== Warring ! One of the devices does not support ToF functionality ===")

        ## Update connection interval after connection is set
        if update_conn_interval:
            time.sleep(2)
            print("Sleep for 2 sec before update connection interval")

            rtlsUtil.set_connection_interval(new_connect_interval_mSec)
            print(f"Update Connection Interval into : {new_connect_interval_mSec} mSec")

        ## Sleep code to see in the screen receives data from devices
        timeout_sec = 10
        print("Going to sleep for {} sec".format(timeout_sec))
        timeout = time.time() + timeout_sec
        while timeout >= time.time():
            time.sleep(0.01)

    except RtlsUtilNodesNotIdentifiedException as ex:
        print(f"=== ERROR: {ex} ===")
        print(ex.not_indentified_nodes)
    except RtlsUtilTimeoutException as ex:
        print(f"=== ERROR: {ex} ===")
    except RtlsUtilException as ex:
        print(f"=== ERROR: {ex} ===")
    finally:
        if cci and rtlsUtil.is_tof_supported(all_nodes):
            rtlsUtil.conn_info_queue.put("STOP")
            print("Try to stop CCI result parsing thread")

            rtlsUtil.cci_stop()
            print("CCI Stopped")

        if aoa and rtlsUtil.is_aoa_supported(all_nodes):
            rtlsUtil.aoa_results_queue.put("STOP")
            print("Try to stop AOA result parsing thread")

            rtlsUtil.aoa_stop()
            print("AOA Stopped")

        if tof and rtlsUtil.is_tof_supported(all_nodes):
            rtlsUtil.tof_results_queue.put("STOP")
            print("Try to stop TOF result parsing thread")

            rtlsUtil.tof_stop()
            print("TOF Stopped")

        if rtlsUtil.ble_connected:
            rtlsUtil.ble_disconnect()
            print("Master Disconnected")

        rtlsUtil.done()
        print("Done")

        rtlsUtil = None


    return main1()

empty = []


def main1():
    y = yy.copy()

    yy.clear()
    # Train a kNN detector
    clf_name = 'kNN'
    clf = KNN()  # Initialize Detector clf
    clf.fit(np.array(y).reshape(-1, 1))  # Use X_train to train the detector clf
    # Returns the abnormal labels and abnormal scores on the traning data X_train
    y_train_pred = clf.labels_  #  Returs the Classification Labels on the Training Data(0: Normal Value, 1: Outlier)
    # y_train_scores = clf.decision_scores_  # Return the abnormal Value on the Training Data(The larger the Score, the More Abnormal)
    result = []
    for i, k in enumerate(y):
        if y_train_pred[i] == 0:
            result.append(k)
    Percentile = np.percentile(result, [50], axis=0)
    return result


#Functions to Calculate Azimuth and Elevation
def pixel_calculate(LEVELangel,AOAangel1,AOAangel2):
    #temp1 = np.pi/36
    #temp2 = np.pi/30
    #print("The Correction Value is??? " + str(temp1))
    #Calculate Azimuth and Elevation Angle to Radian
    aoangel1 = AOAangel1 * np.pi/180
    aoangle2 = AOAangel2 * np.pi/180
    levelangel = LEVELangel * np.pi/180

    cosAOAangel1 = np.cos(aoangel1)
    cosAOAangel2 = np.cos(aoangle2)
    coslevelangel = np.cos(levelangel)
    sinlevelangel = np.sin(levelangel)

    elvation1 = np.arccos((cosAOAangel2-coslevelangel*cosAOAangel1)/sinlevelangel)
    sinelvation1 = np.sin(elvation1)
    coselvation1 = np.cos(elvation1)
    azimuth1 = np.arccos(cosAOAangel1/sinelvation1)
    sinazimuth1 = np.sin(azimuth1)



    bool1 = pd.isnull(np.degrees(azimuth1))
    bool2 = pd.isnull(np.degrees(elvation1))

    if (bool1 | bool2):
        # print("The Azimuth and Elevation Angles are Incorrect")
        return (1,1)
    else:
        focal_length = 4.69  # Focal Length/mm
        pixel_size = 1.55  # Individual Pixel size/ micron
        f = focal_length * 1000 / pixel_size  # Pixel Focal Length

        camera_positon_u = f * (np.sin(azimuth1) / np.cos(azimuth1))  # Camera Co-ordinates -> Co-ordinate System Established by the Center of the Camera
        camera_position_v = f * (np.cos(elvation1) / (np.cos(azimuth1) * np.sin(elvation1)))


        # Co-ordinate System Conversion: Camera co-ordinate -> GUI Co-ordinate
        u = (2016 - camera_positon_u)
        v = (1512 - camera_position_v)

        return (u, v)