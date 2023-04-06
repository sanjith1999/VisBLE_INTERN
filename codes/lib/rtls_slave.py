import os
import time
import json
import queue
import threading
import datetime
import numpy as np
from pyod.models.knn import KNN
from pyod.models.lof import LOF
import csv
import matplotlib.pyplot as plt
from scipy.ndimage import gaussian_filter
import pandas as pd
from scipy.interpolate import CubicSpline

from rtls_util import RtlsUtil, RtlsUtilLoggingLevel, RtlsUtilException, RtlsUtilTimeoutException, \
    RtlsUtilNodesNotIdentifiedException, RtlsUtilScanNoResultsException

all_conn_handles = {}
yy = {}


# User function to proces
def results_parsing(q):
    while True:
        try:
            data = q.get(block=True, timeout=0.5)
            if isinstance(data, dict):
                # data_time = datetime.datetime.now().strftime("[%m:%d:%Y %H:%M:%S:%f] :")
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


# Main Function
def aoa_main():
    # PARAMETERS
    devices = [{"com_port": "COM3", "baud_rate": 460800, "name": "CC26x2 Master"}]
    slave_bd_addr_list = []
    scan_time_sec = 5
    connect_interval_mSec = 180
    sleep_time = 10
    cci = False
    aoa = True
    time_out_sec = 10

    # Update connection interval on the fly Demo Enable / Disable
    update_conn_interval = False
    new_connect_interval_mSec = 80

    # NAMES OF LOG FILES
    data_time = datetime.datetime.now().strftime("%m_%d_%Y_%H_%M_%S")
    logging_file_path = './logs/rtls_util_logs'
    if not os.path.isdir(logging_file_path):
        os.makedirs(logging_file_path)
    logging_file = os.path.join(logging_file_path, f"{data_time}_rtls_utils_logs")

    # Initialize RTLS Util instance
    rtlsUtil = RtlsUtil(logging_file, RtlsUtilLoggingLevel.INFO)
    # Update general time out for all action at RTLS Util [Default timeout : 30 sec]
    rtlsUtil.timeout = time_out_sec

    all_nodes = []
    all_conn_handles.clear()
    try:
        # Setup devices
        master_node, passive_nodes, all_nodes = rtlsUtil.set_devices(devices)
        print(f"Master : {master_node} \nPassives : {passive_nodes} \nAll : {all_nodes}")

        # Reset devices for initial state of devices
        rtlsUtil.reset_devices()
        print("Devices Reset")

        # Code below demonstrates two option of scan and connect
        # 1. Then user know which slave to connect
        # 2. Then user doesn't mind witch slave to use
        if slave_bd_addr_list:
            for slave in slave_bd_addr_list:
                print(f"Start scan of {slave} for {scan_time_sec} sec")
                scan_result = rtlsUtil.scan(scan_time_sec, slave)
                print(f"Scan Results: {scan_result}")
                try:
                    print(f"Try to connect to : {scan_result}")
                    conn_handle = rtlsUtil.ble_connect(slave, connect_interval_mSec)
                    print(f"Connected to : {slave} with connection handle {conn_handle}")
                    if conn_handle is not None:
                        all_conn_handles[conn_handle] = slave
                    else:
                        sleep_time = 1  # REDUCING THE UNWANTED TEST TIME
                except:
                    print(f'Failed to connect to {slave}')
                    continue
        else:
            print(f"Start scan for {scan_time_sec} sec")
            scan_results = rtlsUtil.scan(scan_time_sec)
            print(f"Scan Results: {scan_results}")

            for scan_result in scan_results:
                if scan_result['periodicAdvInt'] != 240:
                    continue
                slave = scan_result['addr']
                try:
                    print(f"Try to connect to : {slave}")
                    conn_handle = rtlsUtil.ble_connect(slave, connect_interval_mSec)
                    print(f"Connected to : {slave} with connection handle {conn_handle}")
                    if conn_handle is not None:
                        all_conn_handles[conn_handle] = slave
                    else:
                        sleep_time = 1
                except:
                    print(f'Failed to connect to {slave}')
                    continue

        # REDUCING THE UNWANTED TEST TIME
        if len(all_conn_handles) == 0:
            sleep_time = 1

        # Start continues connection info feature
        if cci:
            # Setup thread to pull out received data from devices on screen
            th_cci_parsing = threading.Thread(target=results_parsing, args=(rtlsUtil.conn_info_queue,))
            th_cci_parsing.setDaemon(True)
            th_cci_parsing.start()
            print("CCI Callback Set for All Connection Handlers")

            for conn_handle in all_conn_handles.keys():
                rtlsUtil.cci_start(conn_handle=conn_handle)
                print(f"CCI Started with Connection Handle : {conn_handle}")

        # Start angle of arrival feature
        if aoa:
            if rtlsUtil.is_aoa_supported(all_nodes):
                aoa_params = {
                    "aoa_run_mode": "AOA_MODE_ANGLE",  # AOA_MODE_ANGLE, AOA_MODE_PAIR_ANGLES, AOA_MODE_RAW
                    "aoa_cc26x2": {
                        "aoa_slot_durations": 1,
                        "aoa_sample_rate": 1,
                        "aoa_sample_size": 1,
                        "aoa_sampling_control": int('0x10', 16),
                        # bit 0   - 0x00 - default filtering, 0x01 - RAW_RF no filtering,
                        # bit 4,5 - default: 0x10 - ONLY_ANT_1, optional: 0x20 - ONLY_ANT_2
                        "aoa_sampling_enable": 1,
                        "aoa_pattern_len": 3,
                        "aoa_ant_pattern": [0, 1, 2]
                    }
                }
                aoa_conn_handles = []
                for conn_handle in all_conn_handles.keys():
                    try:
                        rtlsUtil.aoa_set_params(aoa_params, conn_handle=conn_handle)
                        print(f"AOA Params Set for Connection Handle: {conn_handle}")
                        aoa_conn_handles.append(conn_handle)
                    except:
                        print(f'Failed to Set AoA Parameters to : {conn_handle}')

                # Setup thread to pull out received data from devices on screen
                th_aoa_results_parsing = threading.Thread(target=results_parsing, args=(rtlsUtil.aoa_results_queue,))
                th_aoa_results_parsing.setDaemon(True)
                th_aoa_results_parsing.start()
                print("AOA Callback Set for All Connection Handlers")

                for conn_handle in aoa_conn_handles:
                    rtlsUtil.aoa_start(cte_length=20, cte_interval=1, conn_handle=conn_handle)
                    print(f"AOA Started with Connection Handle: {conn_handle}")
            else:
                print("=== Warning ! One of the devices does not support AoA functionality ===")

        # Update connection interval after connection is set
        if update_conn_interval:
            time.sleep(2)
            print("Sleep for 2 sec before update connection interval")

            rtlsUtil.set_connection_interval(new_connect_interval_mSec)
            print(f"Update Connection Interval into : {new_connect_interval_mSec} mSec")

        # Sleep code to see in the screen receives data from devices
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
        if cci:
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

    # PREPARING FOR NEXT DATA ACQUISITION
    aoa_data = yy.copy()
    yy.clear()

    print(aoa_data)
    return aoa_data


# REMOVAL OF ANOMALIES
def remove_anomalies(data, model='KNN'):
    y = np.array(data)

    if model == 'KNN':
        clf = KNN()
    elif model == 'LOF':
        clf = LOF()
    else:
        print("NO OTHER SUPPORT --> CHOOSING KNN BY DEFAULT")
        clf = KNN()
    try:
        clf.fit(np.array(y).reshape(-1, 1))
    except:
        print(f"Angular Data Missing.")
        return np.array([])

    y_train_pre = clf.labels_
    filtered = y[y_train_pre == 0]
    return filtered


# Function to Sort Data Using K-Nearest Neighbour Algorithm
def sort_data(aoa_data, aoa_bias=None):
    # PARAMETER DEFINITION
    num_bins = 100++-+
    
    if aoa_bias is None:
        aoa_bias = 0
    scale_factor = 0.5
    threshold = 10

    for slave in aoa_data:
        # GETTING RID OF OUTLIER DATA
        result = remove_anomalies(aoa_data[slave], model='LOF') + aoa_bias

        # RESHAPING THE DISTRIBUTION
        hist, bin_edges = np.histogram(result, bins=num_bins)
        cs = CubicSpline(bin_edges[:-1], hist, bc_type='natural')
        aoa_spread = np.linspace(bin_edges[0], bin_edges[-1], num_bins)
        counts = cs(aoa_spread).astype(int)

        # Percentile = np.percentile(result, [50], axis=0)
        # result = gaussian_filter(result, sigma=2)
        # MODE = np.mode(result)
        # filtered_result = (result - Percentile) * (1 - scale_factor) + Percentile
        # filtered_result = result[abs(result - Percentile) < threshold]

        aoa_data[slave] = np.repeat(aoa_spread, counts)

    return aoa_data


# Functions to Calculate Azimuth and Elevation
def pixel_calculate(level_angle_deg, AoA_angle1, AOA_angle2):
    angle1 = np.radians(AoA_angle1)
    angle2 = np.radians(AOA_angle2)
    level_angle = np.radians(level_angle_deg)

    elevation_angle = np.arccos((np.cos(angle2) - np.cos(angle1) * np.cos(level_angle)) / np.sin(level_angle))
    azimuth_angle = np.arccos(np.cos(angle1) / np.sin(elevation_angle))

    if AoA_angle1 > 0 and AOA_angle2 > 0:
        azimuth_angle = -azimuth_angle

    bool1 = pd.isnull(np.degrees(azimuth_angle))
    bool2 = pd.isnull(np.degrees(elevation_angle))

    if bool1 | bool2:
        # print("The Azimuth and Elevation Angles are Incorrect")
        return 1, 1
    else:
        focal_length = 6.7  # Focal Length/mm
        pixel_size = 1 / 0.8  # Individual Pixel size/ micro meter
        f = focal_length * 1000 / pixel_size  # Pixel Focal Length

        # Camera Co-ordinates -> Co-ordinate System Established by the Center of the Camera
        camera_position_u = f * (np.sin(azimuth_angle) / np.cos(azimuth_angle))
        camera_position_v = f * (np.cos(elevation_angle) / (np.cos(azimuth_angle) * np.sin(elevation_angle)))

        # Co-ordinate System Conversion: Camera co-ordinate -> GUI Co-ordinate
        u = (2000 + camera_position_u)
        v = (1500 + camera_position_v)

        return u, v


def post_calculation(CASE, level1, level2, aoa_bias=0):
    #  AoA BEFORE
    with open(f'./data/aoa_data/{CASE}_{level1}.json', 'r') as f:
        aoa_before = sort_data(json.load(f), aoa_bias)

    # AoA
    with open(f'./data/aoa_data/{CASE}_{level2}.json', 'r') as f:
        aoa = sort_data(json.load(f), aoa_bias)

    lev = [level1, level2]

    print(
        "Before Turning：" + str(aoa_before) + '\n' + "After Turning： " + str(aoa) + '\n' + "Rotation Angle： " + str(lev))
    # aoa_image()
    u = []
    v = []

    set_aoa = set(aoa)
    set_aoa_before = set(aoa_before)

    for slave in set_aoa.intersection(set_aoa_before):
        f = open(f"./results/pixels/{slave.replace(':', '_')}.csv", 'w', newline="")
        writer = csv.writer(f)

        for i in range(2, len(aoa_before[slave]) - 2):
            for j in range(2, len(aoa[slave]) - 2):
                (temp1, temp2) = pixel_calculate(lev[-2] - lev[-1], aoa_before[slave][i], aoa[slave][j])

                if temp1 != 1:
                    u.append(temp1)
                    v.append(temp2)
                    tux = (temp1, temp2)
                    writer.writerow(tux)

        f.close()


def visualize_aoa_spread(CASE, level, num_bins=40):
    with open(f'./data/aoa_data/{CASE}_{level}.json', 'r') as f:
        aoa_data = sort_data(json.load(f))

    # Create a figure and axis object
    fig, ax = plt.subplots()

    # Set the x and y labels and title
    ax.set_xlabel("Angle of Arrival")
    ax.set_ylabel("Frequency")
    ax.set_title("Histogram of Angle of Arrival")

    # Set the number of bins in the histogram

    # Loop over each slave and plot its angle of arrival data as a histogram
    for slave, data in aoa_data.items():
        ax.hist(data, bins=num_bins, alpha=0.5, label=slave)

    # Add a legend to the plot
    ax.legend()
    ax.grid()
    # Show the plot
    plt.show()

    if len(aoa_data.keys()) > 1:
        # Set up the figure with subplots
        fig, axs = plt.subplots(nrows=1, ncols=len(aoa_data.keys()), figsize=(10, 5))

        # Iterate over each slave and plot a histogram of its angle of arrival data
        for i, slave in enumerate(aoa_data.keys()):
            axs[i].hist(aoa_data[slave], bins=num_bins, alpha=0.5)  # adjust bins as needed
            axs[i].set_title(slave)
            axs[i].set_xlabel("Angle of Arrival")
            axs[i].set_ylabel("Frequency")
            axs[i].grid()

        # Adjust the spacing between subplots and display the figure
        plt.tight_layout()

        plt.show()

        return "SUCCESS"


def visualize_aoa_turn_spread(CASE, level1, level2, vis_bias=0, num_bins=50):
    with open(f'./data/aoa_data/{CASE}_{level1}.json', 'r') as f:
        aoa_data1 = json.load(f)
    with open(f'./data/aoa_data/{CASE}_{level2}.json', 'r') as f:
        aoa_data2 = json.load(f)

    # Set up the figure with subplots
    fig, axs = plt.subplots(nrows=1, ncols=len(aoa_data1.keys()), figsize=(10, 5))

    # Iterate over each slave and plot a histogram of its angle of arrival data
    for i, slave in enumerate(aoa_data1.keys()):
        if len(aoa_data1.keys()) == 1:
            axs.hist(np.array(aoa_data1[slave]) - vis_bias, bins=num_bins, color='lightblue',
                     label=f'CASE-I: {level1}')  # adjust bins as needed
            axs.hist(aoa_data2[slave], bins=40, color='orange', label=f'CASE-II: {level2}')  # adjust bins as needed
            axs.set_title(slave)
            axs.set_xlabel("Angle of Arrival")
            axs.set_ylabel("Frequency")
            axs.legend()
            continue

        axs[i].hist(np.array(aoa_data1[slave]) - vis_bias, bins=num_bins, color='lightblue',
                    label=f'CASE-I: {level1}')  # adjust bins as needed
        axs[i].hist(aoa_data2[slave], bins=40, color='orange', label=f'CASE-II: {level2}')  # adjust bins as needed
        axs[i].set_title(slave)
        axs[i].set_xlabel("Angle of Arrival")
        axs[i].set_ylabel("Frequency")
        axs[i].legend()

    # Adjust the spacing between subplots and display the figure
    plt.tight_layout()

    plt.show()
