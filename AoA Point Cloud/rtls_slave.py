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

yy = {}
all_conn_handles = {}
## User function to proces
def results_parsing(q):
    while True:
        try:
            data = q.get(block=True, timeout=0.5)
            if isinstance(data, dict):
                #data_time = datetime.datetime.now().strftime("[%m:%d:%Y %H:%M:%S:%f] :")
                if data["name"] == "CC26x2 Master":
                    addr = all_conn_handles[data['payload']['connHandle']]
                    angle = data['payload']['angle']
                    if addr not in yy:
                        yy[addr] = [angle]
                    else: 
                        yy[addr].append(angle)
            elif isinstance(data, str) and data == "STOP":
                print("STOP Command Received")
                break
            else:
                pass
        except queue.Empty:
            continue



## Main Function
def aoa_main(devices=[{"com_port": "COM3", "baud_rate": 460800, "name": "CC26x2 Master"}],slave_bd_addr_list=[],scan_time_sec=5,connect_interval_mSec=180,sleep_time = 10 ,cci=False,aoa=True, time_out_sec = 30):

    tof_use_calibrate_from_nv = False
    ## Switch TOF Role Demo Enable / Disable
    tof_switch_role = False
    ## Update connection interval on the fly Demo Enable / Disable
    update_conn_interval = False
    new_connect_interval_mSec = 80

    # NAMES OF LOG FILES
    data_time = datetime.datetime.now().strftime("%m_%d_%Y_%H_%M_%S")
    logging_file_path = os.path.join(os.path.curdir, 'rtls_util_logs')
    if not os.path.isdir(logging_file_path):
        os.makedirs(logging_file_path)
    logging_file = os.path.join(logging_file_path, f"{data_time}_rtls_utils_logs")

    ## Initialize RTLS Util instance
    rtlsUtil = RtlsUtil(logging_file, RtlsUtilLoggingLevel.INFO)
    ## Update general time out for all action at RTLS Util [Default timeout : 30 sec]
    rtlsUtil.timeout = time_out_sec

    all_nodes = []
    all_conn_handles.clear()
    try:
        ## Setup devices
        master_node, passive_nodes, all_nodes = rtlsUtil.set_devices(devices)
        print(f"Master : {master_node} \nPassives : {passive_nodes} \nAll : {all_nodes}")

        ## Reset devices for initial state of devices
        rtlsUtil.reset_devices()
        print("Devices Reset")

        ## Code below demonstrates two option of scan and connect
        ## 1. Then user know which slave to connect
        ## 2. Then user doesn't mind witch slave to use
        if slave_bd_addr_list:
            for slave in slave_bd_addr_list:
                print(f"Start scan of {slave} for {scan_time_sec} sec")
                scan_results = rtlsUtil.scan(scan_time_sec, slave)
                print(f"Scan Results: {scan_results}")
                try:
                    print(f"Try to connect to : {slave}")
                    conn_handle = rtlsUtil.ble_connect(scan_result, connect_interval_mSec)
                    print(f"Connected to : {slave} with connection handle {conn_handle}")
                    if conn_handle != None:
                        all_conn_handles.append({conn_handle:slave})
                    else:
                        sleep_time = 1 # REDUCING THE UNWANTED TEST TIME
                except:
                    print(f'Failed to connect to {slave}')
                    continue
        else:
            print(f"Start scan for {scan_time_sec} sec")
            scan_results = rtlsUtil.scan(scan_time_sec)
            print(f"Scan Results: {scan_results}")

            for scan_result in scan_results:
                if scan_result['periodicAdvInt']!=240:
                    continue
                slave = scan_result['addr']
                try:
                    print(f"Try to connect to : {slave}")
                    conn_handle = rtlsUtil.ble_connect(slave, connect_interval_mSec)
                    print(f"Connected to : {slave} with connection handle {conn_handle}")
                    if conn_handle != None:
                        all_conn_handles[conn_handle] = slave
                    else:
                        sleep_time = 1
                except:
                    print(f'Failed to connect to {slave}')
                    continue
        
        # REDUCING THE UNWANTED TEST TIME
        if len(all_conn_handles)==0:
            sleep_time = 1

        ## Start continues connection info feature
        if cci:
            ## Setup thread to pull out received data from devices on screen
            th_cci_parsing = threading.Thread(target=results_parsing, args=(rtlsUtil.conn_info_queue,))
            th_cci_parsing.setDaemon(True)
            th_cci_parsing.start()
            print("CCI Callback Set for All Connection Handlers")

            for conn_handle in all_conn_handles.keys():
                rtlsUtil.cci_start(conn_handle=conn_handle)
                print(f"CCI Started with Connection Handle : {conn_handle}")

        ## Start angle of arrival feature
        if aoa:
            if rtlsUtil.is_aoa_supported(all_nodes):
                aoa_params = {
                    "aoa_run_mode": "AOA_MODE_ANGLE",  ## AOA_MODE_ANGLE, AOA_MODE_PAIR_ANGLES, AOA_MODE_RAW
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
                aoa_conn_handles=[]
                for conn_handle in all_conn_handles.keys():
                    try:
                        rtlsUtil.aoa_set_params(aoa_params,conn_handle=conn_handle)
                        print(f"AOA Params Set for Connection Handle: {conn_handle}")
                        aoa_conn_handles.append(conn_handle)
                    except:
                        print(f'Failed to Set AoA Parameters to : {conn_handle}')

                ## Setup thread to pull out received data from devices on screen
                th_aoa_results_parsing = threading.Thread(target=results_parsing, args=(rtlsUtil.aoa_results_queue,))
                th_aoa_results_parsing.setDaemon(True)
                th_aoa_results_parsing.start()
                print("AOA Callback Set for All Connection Handlers")
                
                for conn_handle in aoa_conn_handles:
                    rtlsUtil.aoa_start(cte_length=20, cte_interval=1,conn_handle=conn_handle)
                    print(f"AOA Started with Connection Handle: {conn_handle}")
            else:
                print("=== Warning ! One of the devices does not support AoA functionality ===")

        ## Update connection interval after connection is set
        if update_conn_interval:
            time.sleep(2)
            print("Sleep for 2 sec before update connection interval")

            rtlsUtil.set_connection_interval(new_connect_interval_mSec)
            print(f"Update Connection Interval into : {new_connect_interval_mSec} mSec")

        ## Sleep code to see in the screen receives data from devices
        print("Going to sleep for {} sec".format(sleep_time))
        timeout = time.time() + sleep_time
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

        if rtlsUtil.ble_connected:
            rtlsUtil.ble_disconnect()
            print("Master Disconnected")

        rtlsUtil.done()
        print("Done")

        rtlsUtil = None


    return main1()

def main1():
    # Clearing out yy for next data acquistation
    aoa_data = yy.copy()
    yy.clear()

    aoa_sorted = {}
    for slave in aoa_data:
        try:
            y = aoa_data[slave]
            result = []
            # Train a kNN detector
            clf_name = 'kNN'
            clf = KNN()  # Initialize Detector clf
            clf.fit(np.array(y).reshape(-1, 1))  # Use X_train to train the detector clf
            # Returns the abnormal labels and abnormal scores on the traning data X_train
            y_train_pred = clf.labels_  #  Returs the Classification Labels on the Training Data(0: Normal Value, 1: Outlier)
            # y_train_scores = clf.decision_scores_  # Return the abnormal Value on the Training Data(The larger the Score, the More Abnormal)
            for i, k in enumerate(y):
                if y_train_pred[i] == 0:
                    result.append(k)
            Percentile = np.percentile(result, [50], axis=0)
            aoa_sorted[slave] = result
        except:
            print(f"AoA Data Missing for {slave}.")
    return aoa_sorted


#Functions to Calculate Azimuth and Elevation
def pixel_calculate(LEVELangle,AOAangle1,AOAangle2,beta = 1,aoa_bias = 0):

    aoaangle1 = np.radians(AOAangle1+aoa_bias)
    aoaangle2 = np.radians(AOAangle2+aoa_bias)
    levelangle = np.radians(LEVELangle)


    elevation_angle = np.arccos((np.cos(aoaangle2)-np.cos(aoaangle1)*np.cos(levelangle))/np.sin(levelangle))
    azimuth_angle = np.arccos(np.cos(aoaangle1)/np.sin(elevation_angle))



    bool1 = pd.isnull(np.degrees(azimuth_angle))
    bool2 = pd.isnull(np.degrees(elevation_angle))

    if (bool1 | bool2):
        # print("The Azimuth and Elevation Angles are Incorrect")
        return (1,1)
    else:
        focal_length = 6.7 # Focal Length/mm
        pixel_size = 1/0.8  # Individual Pixel size/ micro meter
        f = beta * focal_length * 1000 / pixel_size  # Pixel Focal Length

        camera_positon_u = f * (np.sin(azimuth_angle) / np.cos(azimuth_angle))  # Camera Co-ordinates -> Co-ordinate System Established by the Center of the Camera
        camera_position_v = f * (np.cos(elevation_angle) / (np.cos(azimuth_angle) * np.sin(elevation_angle)))


        # Co-ordinate System Conversion: Camera co-ordinate -> GUI Co-ordinate
        u = (2000 - camera_positon_u)
        v = (1500 - camera_position_v)

        return (u, v)
    

def angle_calculate(LEVELangle, AOAangle1, AOAangle2):
    """ 
    LEVELangle: Change in level angle
    AOAangle1: First AoA measurement
    AOAangle2: Second AoA measurement
    return: azimuth_angle, elevation_angle 
    """
    aoaangle1 = np.radians(AOAangle1)
    aoaangle2 = np.radians(AOAangle2)
    levelangle = np.radians(LEVELangle)

    
    elevation_angle = np.arccos(clamp((np.cos(aoaangle2)-np.cos(aoaangle1)*np.cos(levelangle))/np.sin(levelangle)))
    azimuth_angle = np.arccos(clamp(np.cos(aoaangle1)/np.sin(elevation_angle)))

    return(round(np.rad2deg(azimuth_angle),2), round(np.rad2deg(elevation_angle),2))

def clamp(value):
    if value< -1:
        return -1
    elif value > 1:
        return 1
    return value