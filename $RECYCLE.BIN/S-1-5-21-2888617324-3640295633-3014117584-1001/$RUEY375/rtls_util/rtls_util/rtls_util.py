import weakref
import sys
import queue
import time
import threading
import json
import logging
from logging.handlers import RotatingFileHandler
import random

from .rtls_util_exception import *

from rtls import RTLSManager, RTLSNode

from dataclasses import dataclass


@dataclass
class RtlsUtilLoggingLevel():
    CRITICAL = 50
    ERROR = 40
    WARNING = 30
    INFO = 20
    DEBUG = 10
    ALL = 0


class ConnectionlessAOASync():
    def __init__(self, sync_created, sync_established, sync_report_enable, cl_aoa_enable, in_padv_list, sync_handle):
        self.sync_created = sync_created
        self.sync_established = sync_established
        self.sync_report_enable = sync_report_enable
        self.cl_aoa_enable = cl_aoa_enable
        self.sync_handle = sync_handle
        self.in_padv_list = in_padv_list

    def __repr__(self):
        return "%s(%r)" % (self.__class__, self.__dict__)


class RtlsUtil():
    def __init__(self, logging_file, logging_level, websocket_port=None, max_log_file_size=100):
        self.logger = logging.getLogger()
        self.logger.setLevel(logging_level)

        self.logger_fh = RotatingFileHandler(logging_file, maxBytes=max_log_file_size * 1024 * 1024, backupCount=100)
        self.logger_fh.setLevel(logging_level)

        # formatter = logging.Formatter('[%(asctime)s] %(filename)-18sln %(lineno)3d %(threadName)-10s %(name)s - %(levelname)8s - %(message)s')
        formatter = logging.Formatter(
            '[%(asctime)s] %(name)9s - %(levelname)8s - %(message)s')
        self.logger_fh.setFormatter(formatter)

        # Messages can be filter by logger name
        # blank means all all messages
        # filter = logging.Filter()
        # self.logger_fh.addFilter(filter)

        self.logger.addHandler(self.logger_fh)

        self._master_node = None
        self._passive_nodes = []
        self._all_nodes = []

        self._rtls_manager = None
        self._rtls_manager_subscriber = None

        self._message_receiver_th = None
        self._message_receiver_stop = False

        self._scan_results = []
        self._scan_stopped = threading.Event()
        self._scan_stopped.clear()

        self._ble_connected = False
        self._connected_slave = []

        self._master_disconnected = threading.Event()
        self._master_disconnected.clear()

        self._master_seed = None

        self._timeout = 30
        self._conn_handle = None
        self._slave_attempt_to_connect = None

        self._is_cci_started = False
        self._is_aoa_started = False

        self.padv_list_size = None
        self.sync_failed_to_be_est = False
        # TODO: Change this flags to be threading.event and use clear, is_set, set to toggle
        self._padv_read_list_size_complete = threading.Event()
        self._padv_read_list_size_complete.clear()
        self._padv_clear_adv_list_complete = threading.Event()
        self._padv_clear_adv_list_complete.clear()

        self._read_heap_size_complete = threading.Event()
        self._read_heap_size_complete.clear()

        self._padv_current_slave = None
        self._padv_sync_dict = {}

        self.aoa_results_queue = queue.Queue()
        self.conn_info_queue = queue.Queue()
        self.padv_event_queue = queue.Queue()
        self.cl_aoa_results_queue = queue.Queue()
        self.custom_message_queue = queue.Queue()

        self.custom_message_filter = None

        self.evt_assert = False
        self.total_heap = None
        self.free_heap = None

        self.websocket_port = websocket_port

        self.on_ble_disconnected_queue = queue.Queue()

    def __del__(self):
        self.done()

    @property
    def timeout(self):
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        self._timeout = value

    def _rtls_wait(self, true_cond_func, nodes, timeout_message):
        timeout = time.time() + self._timeout
        timeout_reached = time.time() > timeout

        while not true_cond_func(nodes) and not timeout_reached:
            time.sleep(0.1)
            timeout_reached = time.time() > timeout

        if timeout_reached:
            raise RtlsUtilTimeoutException(
                f"Timeout reached while waiting for : {timeout_message}")

    def done(self):
        if self._message_receiver_th is not None:
            self._message_receiver_stop = True
            self._message_receiver_th.join()
            self._message_receiver_th = None

        if self._rtls_manager:
            self._rtls_manager.stop()

            self._rtls_manager_subscriber = None
            self._rtls_manager = None

        self.logger_fh.close()
        self.logger.removeHandler(self.logger_fh)

    def _log_incoming_msg(self, item, identifier):
        json_item = json.loads(item.as_json())

        json_item["type"] = "Response" if json_item["type"] == "SyncRsp" else "Event"

        # Filtering out "originator" and "subsystem" fields
        new_dict = {k: v for (k, v) in json_item.items()
                    if k != "originator" if k != "subsystem"}

        # Get reference to RTLSNode based on identifier in message
        sending_node = self._rtls_manager[identifier]

        if sending_node in self._passive_nodes:
            self.logger.info(f"PASSIVE : {identifier} --> {new_dict}")
        else:
            self.logger.info(f"MASTER  : {identifier} --> {new_dict}")

    def _message_receiver(self):
        while not self._message_receiver_stop:
            # Get messages from manager
            try:
                identifier, msg_pri, msg = self._rtls_manager_subscriber.pend(
                    block=True, timeout=0.05).as_tuple()

                self._log_incoming_msg(msg, identifier)

                sending_node = self._rtls_manager[identifier]

                if self.custom_message_filter and msg.command in self.custom_message_filter:
                    self.custom_message_queue.put({
                        "name": sending_node.name,
                        "identifier": identifier,
                        "msg": msg
                    })

                if msg.command == "RTLS_EVT_DEBUG" and msg.type == "AsyncReq":
                    self.logger.debug(msg.payload)

                if msg.command == "RTLS_CMD_SCAN" and msg.type == "AsyncReq":
                    self._add_scan_result({
                        'addr': msg.payload.addr,
                        'addrType': msg.payload.addrType,
                        'rssi': msg.payload.rssi,
                        'advSID': msg.payload.advSID,
                        'periodicAdvInt': msg.payload.periodicAdvInt
                    })

                if msg.command == "RTLS_CMD_SCAN_STOP" and msg.type == "AsyncReq":
                    self._scan_stopped.set()

                if msg.command == "RTLS_CMD_CONNECT" and msg.type == "AsyncReq" and msg.payload.status == "RTLS_SUCCESS":
                    sending_node.connection_in_progress = False
                    sending_node.connected = True

                    if sending_node.identifier == self._master_node.identifier:
                        self._conn_handle = msg.payload.connHandle if 'connHandle' in msg.payload else -1
                        self._master_disconnected.clear()

                if msg.command == "RTLS_CMD_CONN_PARAMS" and msg.type == "AsyncReq":
                    pass

                if msg.command == "RTLS_CMD_CONNECT" and msg.type == "AsyncReq" and msg.payload.status == "RTLS_LINK_TERMINATED":
                    sending_node.connection_in_progress = False
                    sending_node.connected = False

                    if sending_node.identifier == self._master_node.identifier:
                        self._master_disconnected.set()

                        if 'connHandle' in msg.payload:
                            for _slave in self._connected_slave[:]:
                                if _slave['conn_handle'] == msg.payload.connHandle:
                                    self._connected_slave.remove(_slave)
                                    break

                        # TODO:
                        #     Make disocnnect wait for all required slave to disconnect
                        #     if len(self._connected_slave) == 0:
                        #         self._master_disconnected.set()
                        #     else:
                        #         self._master_disconnected.set()

                    elif 'connHandle' in msg.payload and sending_node in self._passive_nodes:
                        slave = self._get_slave_by_conn_handle(
                            msg.payload.connHandle)
                        # In this point if slave is none it means connection fail while we in connection process
                        if slave is not None:
                            self.on_ble_disconnected_queue.put({
                                'node_identifier': sending_node.identifier,
                                'slave_addr': slave['addr'],
                                'isCciStarted': self._is_cci_started,
                                'isAoaStarted': self._is_aoa_started
                            })

                    else:
                        pass

                if msg.command == 'RTLS_CMD_AOA_SET_PARAMS' and msg.payload.status == 'RTLS_SUCCESS':
                    sending_node.aoa_initialized = True

                if msg.command in ["RTLS_CMD_AOA_RESULT_ANGLE",
                                   "RTLS_CMD_AOA_RESULT_RAW",
                                   "RTLS_CMD_AOA_RESULT_PAIR_ANGLES"] and msg.type == "AsyncReq":
                    self.aoa_results_queue.put({
                        "name": sending_node.name,
                        "type": str(msg.command),
                        "identifier": identifier,
                        "payload": msg.payload
                    })

                if msg.command == 'RTLS_CMD_RESET_DEVICE' and msg.type == 'AsyncReq':
                    sending_node.device_resets = True

                if msg.command == 'RTLS_CMD_CONN_INFO' and msg.type == 'SyncRsp':
                    sending_node.cci_started = True

                if msg.command == 'RTLS_EVT_CONN_INFO' and msg.type == 'AsyncReq':
                    self.conn_info_queue.put({
                        "name": sending_node.name,
                        "type": "conn_info",
                        "identifier": identifier,
                        "payload": msg.payload
                    })

                # print(msg.payload)
                if msg.command == 'RTLS_CMD_SET_RTLS_PARAM' and msg.payload.rtlsParamType == "RTLS_PARAM_CONNECTION_INTERVAL" and msg.payload.status == "RTLS_SUCCESS":
                    sending_node.conn_interval_updated = True

                if msg.command == 'RTLS_CMD_IDENTIFY' and msg.type == 'SyncRsp':
                    sending_node.identified = True
                    sending_node.identifier = msg.payload.identifier
                    sending_node.capabilities = msg.payload.capabilities
                    sending_node.devId = msg.payload.devId
                    sending_node.revNum = msg.payload.revNum

                if msg.command == 'RTLS_CMD_CREATE_SYNC' and msg.type == 'SyncRsp' and msg.payload.status == 'RTLS_SUCCESS':
                    self._padv_sync_dict[self._padv_current_slave].sync_created = True

                if msg.command == 'RTLS_EVT_TERMINATE_SYNC' and msg.type == 'AsyncReq' and msg.payload.status == 'RTLS_SUCCESS':
                    if self._padv_current_slave is not None and self._padv_current_slave in self._padv_sync_dict.keys():
                        self._padv_sync_dict[self._padv_current_slave].sync_created = False

                if msg.command == 'RTLS_EVT_SYNC_LOST' and msg.type == 'AsyncReq':
                    slave = self._padv_find_address_by_handle(msg.payload.syncHandle)
                    if slave:
                        padv_current_slave = (slave[0], slave[1])
                        self._padv_sync_dict[padv_current_slave].sync_created = False
                        self._padv_sync_dict[padv_current_slave].sync_established = False
                        self._padv_sync_dict[padv_current_slave].sync_report_enable = False
                        self._padv_sync_dict[padv_current_slave].cl_aoa_enable = False
                        self._padv_sync_dict[padv_current_slave].sync_handle = -1

                if msg.command == 'RTLS_CMD_ADD_DEVICE_ADV_LIST' and msg.type == 'SyncRsp' and msg.payload.status == 'RTLS_SUCCESS':
                    self._padv_sync_dict[self._padv_current_slave].in_padv_list = True

                if msg.command == 'RTLS_CMD_REMOVE_DEVICE_ADV_LIST' and msg.type == 'SyncRsp' and msg.payload.status == 'RTLS_SUCCESS':
                    self._padv_sync_dict[self._padv_current_slave].in_padv_list = False

                if msg.command == 'RTLS_CMD_CLEAR_ADV_LIST' and msg.type == 'SyncRsp' and msg.payload.status == 'RTLS_SUCCESS':
                    self._padv_clear_adv_list_complete.set()

                if msg.command == 'RTLS_CMD_CL_AOA_ENABLE' and msg.type == 'SyncRsp' and msg.payload.status == 'RTLS_SUCCESS':
                    self._padv_sync_dict[self._padv_current_slave].cl_aoa_enable = not self._padv_sync_dict[
                        self._padv_current_slave].cl_aoa_enable

                if msg.command == 'RTLS_EVT_SYNC_EST' and msg.type == 'AsyncReq' and msg.payload.status == 'RTLS_SUCCESS':
                    current_slave = (msg.payload.advAddress, msg.payload.advSid)
                    if current_slave in self._padv_sync_dict.keys():
                        self._padv_sync_dict[current_slave].sync_established = True
                        self._padv_sync_dict[current_slave].sync_handle = msg.payload.syncHandle

                if msg.command == 'RTLS_EVT_SYNC_EST' and msg.type == 'AsyncReq' and msg.payload.status == 'RTLS_SYNC_CANCELED_BY_HOST':
                    self._padv_sync_dict[self._padv_current_slave].sync_created = False

                if msg.command == 'RTLS_EVT_SYNC_EST' and msg.type == 'AsyncReq' and msg.payload.status == 'RTLS_SYNC_FAILED_TO_BE_EST':
                    self.sync_failed_to_be_est = True

                if msg.command == 'RTLS_CMD_PERIODIC_RECEIVE_ENABLE' and msg.type == 'SyncRsp' and msg.payload.status == 'RTLS_SUCCESS':
                    self._padv_sync_dict[self._padv_current_slave].sync_report_enable = not self._padv_sync_dict[
                        self._padv_current_slave].sync_report_enable

                if msg.command == 'RTLS_CMD_READ_ADV_LIST_SIZE' and msg.type == 'AsyncReq' and msg.payload.status == 'RTLS_SUCCESS':
                    self.padv_list_size = msg.payload.listSize
                    self._padv_read_list_size_complete.set()

                if msg.command == 'RTLS_CMD_HEAP_SIZE' and msg.type == 'SyncRsp':
                    self.total_heap = msg.payload.totalHeap
                    self.free_heap = msg.payload.freeHeap
                    self._read_heap_size_complete.set()

                if msg.command == 'RTLS_EVT_PERIODIC_ADV_RPT' and msg.type == 'AsyncReq':
                    self.padv_event_queue.put({
                        "name": sending_node.name,
                        "type": "padv_event",
                        "identifier": identifier,
                        "payload": msg.payload
                    })

                if msg.command in ['RTLS_CMD_CL_AOA_RESULT_RAW',
                                   'RTLS_CMD_CL_AOA_RESULT_ANGLE',
                                   'RTLS_CMD_CL_AOA_RESULT_PAIR_ANGLES'] and msg.type == 'AsyncReq':
                    self.cl_aoa_results_queue.put({
                        "name": sending_node.name,
                        "type": str(msg.command),
                        "identifier": identifier,
                        "payload": msg.payload
                    })

                if msg.command == 'RTLS_EVT_ASSERT' and msg.type == 'AsyncReq':
                    self.evt_assert = True

            except queue.Empty:
                pass

    def _start_message_receiver(self):
        self._message_receiver_stop = False
        self._message_receiver_th = threading.Thread(
            target=self._message_receiver)
        self._message_receiver_th.setDaemon(True)
        self._message_receiver_th.start()

    def _empty_queue(self, q):
        while True:
            try:
                q.get(timeout=0.5)
            except queue.Empty:
                break

    def _is_passive_in_nodes(self, nodes):
        for node in nodes:
            if not node.capabilities.get('RTLS_MASTER', False):
                return True

        return False

    # User Function

    def add_user_log(self, msg):
        print(msg)
        self.logger.info(msg)

    def set_custom_message_filter(self, list_of_cmd):
        if not isinstance(list_of_cmd, (list, tuple)):
            raise Exception(" list_of_cmd must be type of list or tuple")

        self.custom_message_filter = list_of_cmd

    def get_custom_message_filter(self):
        return self.custom_message_filter

    def clear_custom_message_filter(self):
        self.custom_message_filter = None

    # Devices API

    def indentify_devices(self, devices_setting):
        self.logger.info("Setting nodes : ".format(
            json.dumps(devices_setting)))
        nodes = [RTLSNode(node["com_port"], node["baud_rate"],
                          node["name"]) for node in devices_setting]

        _rtls_manager = RTLSManager(nodes, websocket_port=None)
        _rtls_manager_subscriber = _rtls_manager.create_subscriber()
        _rtls_manager.auto_params = False

        _rtls_manager.start()
        self.logger.info("RTLS Manager started")
        time.sleep(2)

        _all_nodes = _rtls_manager.nodes

        _rtls_manager.stop()
        while not _rtls_manager.stopped:
            time.sleep(0.1)

        _rtls_manager_subscriber = None
        _rtls_manager = None

        return _all_nodes

    def set_devices(self, devices_setting):
        self.logger.info("Setting nodes : ".format(
            json.dumps(devices_setting)))
        nodes = [RTLSNode(node["com_port"], node["baud_rate"],
                          node["name"]) for node in devices_setting]

        self._rtls_manager = RTLSManager(
            nodes, websocket_port=self.websocket_port)
        self._rtls_manager_subscriber = self._rtls_manager.create_subscriber()
        self._rtls_manager.auto_params = True

        self._start_message_receiver()
        self.logger.info("Message receiver started")

        self._rtls_manager.start()
        self.logger.info("RTLS Manager started")
        time.sleep(2)
        self._master_node, self._passive_nodes, failed = self._rtls_manager.wait_identified()

        if self._master_node is None:
            raise RtlsUtilMasterNotFoundException(
                "No one of the nodes identified as RTLS MASTER")
        # elif len(self._passive_nodes) == 0:
        #     raise RtlsUtilPassiveNotFoundException("No one of the nodes identified as RTLS PASSIVE")
        elif len(failed) > 0:
            raise RtlsUtilNodesNotIdentifiedException(
                "{} nodes not identified at all".format(len(failed)), failed)
        else:
            pass

        self._all_nodes = [pn for pn in self._passive_nodes]  # deep copy
        self._all_nodes.extend([self._master_node])

        for node in self._all_nodes:
            node.cci_started = False
            node.aoa_initialized = False

            node.ble_connected = False
            node.device_resets = False

        self.logger.info("Done setting node")
        return self._master_node, self._passive_nodes, self._all_nodes

    def get_devices_capability(self, nodes=None):
        nodes_to_set = self._all_nodes
        if nodes is not None:
            if isinstance(nodes, list):
                nodes_to_set = nodes
            else:
                raise RtlsUtilException("nodes input must be from list type")

        for node in nodes_to_set:
            node.identified = False
            node.rtls.identify()

        def true_cond_func(nodes):
            return all([n.identified for n in nodes])

        self._rtls_wait(true_cond_func, nodes_to_set,
                        "All device to identified")

        ret = []
        for node in nodes_to_set:
            dev_info = {
                "node_mac_address": node.identifier,
                "capabilities": node.capabilities
            }

            ret.append(dev_info)

        return ret

    ######

    # Common BLE API

    def _get_slave_by_addr(self, addr, advSID=None):
        for _scan_result in self._scan_results:
            if advSID is None:
                if _scan_result['addr'].lower() == addr.lower():
                    return _scan_result
            else:
                if _scan_result['addr'].lower() == addr.lower() and _scan_result['advSID'] == advSID:
                    return _scan_result

        return None

    def _get_slave_by_conn_handle(self, conn_handle):
        for _slave in self._connected_slave:
            if _slave['conn_handle'] == conn_handle:
                return _slave

        return None

    def _add_scan_result(self, scan_result):
        if self._get_slave_by_addr(scan_result['addr'], scan_result['advSID']) is None:
            self._scan_results.append(scan_result)

    def scan(self, scan_time_sec, expected_slave_bd_addr=None, advSID=None):
        self._scan_results = []

        timeout = time.time() + scan_time_sec
        timeout_reached = time.time() > timeout

        while not timeout_reached:
            self._scan_stopped.clear()

            self._master_node.rtls.scan()
            scan_start_time = time.time()

            scan_timeout_reached = time.time() > (scan_start_time + 10)
            while not self._scan_stopped.isSet() and not scan_timeout_reached:
                time.sleep(0.1)
                scan_timeout_reached = time.time() > (scan_start_time + 10)

                if scan_timeout_reached:
                    raise RtlsUtilEmbeddedFailToStopScanException(
                        "Embedded side didn't finished due to timeout")

            if len(self._scan_results) > 0:
                if expected_slave_bd_addr is not None and self._get_slave_by_addr(expected_slave_bd_addr,
                                                                                  advSID) is not None:
                    break

            timeout_reached = time.time() > timeout
        else:
            if len(self._scan_results) > 0:
                if expected_slave_bd_addr is not None and self._get_slave_by_addr(expected_slave_bd_addr,
                                                                                  advSID) is not None:
                    raise RtlsUtilScanSlaveNotFoundException(
                        "Expected slave not found in scan list")
            else:
                raise RtlsUtilScanNoResultsException(
                    "No device with slave capability found")

        return self._scan_results

    @property
    def ble_connected(self):
        return len(self._connected_slave) > 0

    def ble_connected_to(self, slave):
        if isinstance(slave, str):
            slave = self._get_slave_by_addr(slave)
            if slave is None:
                raise RtlsUtilScanSlaveNotFoundException(
                    "Expected slave not found in scan list")
        else:
            if 'addr' not in slave.keys() or 'addrType' not in slave.keys():
                raise RtlsUtilException(
                    "Input slave not a string and not contains required keys")

        for s in self._connected_slave:
            if s['addr'] == slave['addr'] and s['conn_handle'] == slave['conn_handle']:
                return True

        return False

    def ble_connect(self, slave, connect_interval_mSec):
        if isinstance(slave, str):
            slave = self._get_slave_by_addr(slave)
            if slave is None:
                raise RtlsUtilScanSlaveNotFoundException(
                    "Expected slave not found in scan list")
        else:
            if 'addr' not in slave.keys() or 'addrType' not in slave.keys():
                raise RtlsUtilException(
                    "Input slave not a string and not contains required keys")

        interval = int(connect_interval_mSec / 1.25)

        self._conn_handle = None
        self._slave_attempt_to_connect = slave
        self._master_node.connection_in_progress = True
        self._master_node.connected = False

        self._master_node.rtls.connect(
            slave['addrType'], slave['addr'], interval)

        def true_cond_func(master_node):
            return master_node.connection_in_progress == False

        self._rtls_wait(true_cond_func, self._master_node,
                        "All node to connect")

        if self._master_node.connected:
            slave['conn_handle'] = self._conn_handle

            self._connected_slave.append(slave)
            self._slave_attempt_to_connect = None

            self._ble_connected = True
            self.logger.info("Connection process done")

            return self._conn_handle

        return None

    def ble_disconnect(self, conn_handle=None, nodes=None):
        nodes_to_set = self._all_nodes
        if nodes is not None:
            if isinstance(nodes, list):
                nodes_to_set = nodes
            else:
                raise RtlsUtilException("Nodes input must be from list type")

        for node in nodes_to_set:
            if str(node.devId) == "DeviceFamily_ID_CC26X0R2":
                node.rtls.terminate_link()
            else:
                if conn_handle is None:
                    for slave in self._connected_slave:
                        node.rtls.terminate_link(slave['conn_handle'])
                else:
                    node.rtls.terminate_link(conn_handle)

        def true_cond_func(event):
            return event.isSet()

        self._rtls_wait(
            true_cond_func, self._master_disconnected, "Master disconnect")

        self._ble_connected = False
        self.logger.info("Disconnect process done")

    def set_connection_interval(self, connect_interval_mSec, conn_handle=None):
        conn_interval = int(connect_interval_mSec / 1.25)
        data_len = 2
        data_bytes = conn_interval.to_bytes(data_len, byteorder='little')

        self._master_node.conn_interval_updated = False
        if str(self._master_node.devId) == "DeviceFamily_ID_CC26X0R2":
            self._master_node.rtls.set_rtls_param(
                'RTLS_PARAM_CONNECTION_INTERVAL', data_len, data_bytes)
        else:
            if conn_handle is None:
                for s in self._connected_slave:
                    self._master_node.rtls.set_rtls_param(s['conn_handle'],
                                                          'RTLS_PARAM_CONNECTION_INTERVAL',
                                                          data_len,
                                                          data_bytes)

            else:
                self._master_node.rtls.set_rtls_param(conn_handle,
                                                      'RTLS_PARAM_CONNECTION_INTERVAL',
                                                      data_len,
                                                      data_bytes)

        def true_cond_func(nodes):
            return all([n.conn_interval_updated for n in nodes])

        self._rtls_wait(true_cond_func, [self._master_node], "Master node set connection interval")

        self.logger.info("Connection Interval Updated")

    def reset_devices(self, nodes=None):
        nodes_to_set = self._all_nodes
        if nodes is not None:
            if isinstance(nodes, list):
                nodes_to_set = nodes
            else:
                raise RtlsUtilException("nodes input must be from list type")

        for node in nodes_to_set:
            node.device_resets = False
            node.rtls.reset_device()

        def true_cond_func(nodes):
            return all([n.device_resets for n in nodes])

        self._rtls_wait(true_cond_func, nodes_to_set, "All node to reset")

    def is_multi_connection_supported(self, nodes):
        for node in nodes:
            if str(node.devId) == "DeviceFamily_ID_CC26X0R2":
                return False

        return True

    ######

    # CCI - Continuous Connection Info

    def cci_start(self, nodes=None, conn_handle=None):
        nodes_to_set = self._all_nodes
        if nodes is not None:
            if isinstance(nodes, list):
                nodes_to_set = nodes
            else:
                raise RtlsUtilException("Nodes input must be from list type")

        for node in nodes_to_set:
            node.cci_started = False
            if str(node.devId) == "DeviceFamily_ID_CC26X0R2":
                node.rtls.get_conn_info(True)
            else:
                if conn_handle is None:
                    for s in self._connected_slave:
                        node.rtls.get_conn_info(s['conn_handle'], True)
                else:
                    node.rtls.get_conn_info(conn_handle, True)

        def true_cond_func(nodes):
            return all([n.cci_started for n in nodes])

        self._rtls_wait(true_cond_func, nodes_to_set,
                        "All node start continues connect info (CCI)")

        self._is_cci_started = True

    def cci_stop(self, nodes=None, conn_handle=None):
        nodes_to_set = self._all_nodes
        if nodes is not None:
            if isinstance(nodes, list):
                nodes_to_set = nodes
            else:
                raise RtlsUtilException("Nodes input must be from list type")

        for node in nodes_to_set:
            if str(node.devId) == "DeviceFamily_ID_CC26X0R2":
                node.rtls.get_conn_info(False)
            else:
                if conn_handle is None:
                    for slave in self._connected_slave:
                        node.rtls.get_conn_info(slave['conn_handle'], False)
                else:
                    node.rtls.get_conn_info(conn_handle, False)

        self._is_cci_started = False

    ######

    # AOA - Angle of Arrival

    def is_aoa_supported(self, nodes):
        devices_capab = self.get_devices_capability(nodes)
        for device_capab in devices_capab:
            if not (device_capab['capabilities'].AOA_TX == True or device_capab['capabilities'].AOA_RX == True):
                return False

        return True

    def _aoa_set_params(self, node, aoa_params, conn_handle):
        try:
            node.aoa_initialized = False
            node_role = 'AOA_MASTER' if node.capabilities.get(
                'RTLS_MASTER', False) else 'AOA_PASSIVE'
            if str(node.devId) == "DeviceFamily_ID_CC26X0R2":
                node.rtls.aoa_set_params(
                    node_role,
                    aoa_params['aoa_run_mode'],
                    aoa_params['aoa_cc2640r2']['aoa_cte_scan_ovs'],
                    aoa_params['aoa_cc2640r2']['aoa_cte_offset'],
                    aoa_params['aoa_cc2640r2']['aoa_cte_length'],
                    aoa_params['aoa_cc2640r2']['aoa_sampling_control']
                )
            else:
                node.rtls.aoa_set_params(
                    node_role,
                    aoa_params['aoa_run_mode'],
                    conn_handle,
                    aoa_params['aoa_cc26x2']['aoa_slot_durations'],
                    aoa_params['aoa_cc26x2']['aoa_sample_rate'],
                    aoa_params['aoa_cc26x2']['aoa_sample_size'],
                    aoa_params['aoa_cc26x2']['aoa_sampling_control'],
                    aoa_params['aoa_cc26x2']['aoa_sampling_enable'],
                    aoa_params['aoa_cc26x2']['aoa_pattern_len'],
                    aoa_params['aoa_cc26x2']['aoa_ant_pattern']
                )
        except KeyError as ke:
            raise RtlsUtilException("Invalid key : {}".format(str(ke)))

    def aoa_set_params(self, aoa_params, nodes=None, conn_handle=None):
        nodes_to_set = self._all_nodes
        if nodes is not None:
            if isinstance(nodes, list):
                nodes_to_set = nodes
            else:
                raise RtlsUtilException("Nodes input must be from list type")

        for node in nodes_to_set:
            node.aoa_initialized = False
            if conn_handle is None:
                for slave in self._connected_slave:
                    self._aoa_set_params(
                        node, aoa_params, slave['conn_handle'])
            else:
                self._aoa_set_params(node, aoa_params, conn_handle)

        def true_cond_func(nodes):
            return all([n.aoa_initialized for n in nodes])

        self._rtls_wait(true_cond_func, nodes_to_set,
                        "All node to set AOA params")

    def _aoa_set_state(self, start, cte_interval=1, cte_length=20, nodes=None, conn_handle=None):
        nodes_to_set = self._all_nodes
        if nodes is not None:
            if isinstance(nodes, list):
                nodes_to_set = nodes
            else:
                raise RtlsUtilException("Nodes input must be from list type")

        for node in nodes_to_set:
            node_role = 'AOA_MASTER' if node.capabilities.get(
                'RTLS_MASTER', False) else 'AOA_PASSIVE'
            if str(node.devId) == "DeviceFamily_ID_CC26X0R2":
                node.rtls.aoa_start(start)
            else:
                if conn_handle is None:
                    for slave in self._connected_slave:
                        node.rtls.aoa_start(
                            slave['conn_handle'], start, cte_interval, cte_length)
                else:
                    node.rtls.aoa_start(conn_handle, start,
                                        cte_interval, cte_length)

        self._is_aoa_started = start

    def aoa_start(self, cte_length, cte_interval, nodes=None, conn_handle=None):
        self._aoa_set_state(start=True, cte_length=cte_length, cte_interval=cte_interval, nodes=nodes,
                            conn_handle=conn_handle)
        self.logger.info("AOA Started")

    def aoa_stop(self, nodes=None, conn_handle=None):
        self._aoa_set_state(start=False, nodes=nodes, conn_handle=conn_handle)
        self.logger.info("AOA Stopped")

    ######

    # Periodic adv/Connectionless AOA

    def cl_aoa_start(self, cl_aoa_params, slave):
        if not self._padv_sync_dict[(slave['addr'], slave['advSID'])].cl_aoa_enable:
            self._cl_aoa_set_state(cl_aoa_params, slave, True)
            self.logger.info("Connectionless AOA Started")
        else:
            raise RtlsUtilException("Connectionless AOA has already enabled.")

    def cl_aoa_stop(self, cl_aoa_params, slave):
        if self._padv_sync_dict[(slave['addr'], slave['advSID'])].cl_aoa_enable:
            self._cl_aoa_set_state(cl_aoa_params, slave, False)
            self.logger.info("Connectionless AOA Stopped")
        else:
            self.logger.info("Connectionless AOA has already disabled.")

    def _cl_aoa_set_state(self, cl_aoa_params, slave, enable):

        # Check slave type(str or dict)
        if isinstance(slave, str):
            slave = self._get_slave_by_addr(slave)
            if slave is None:
                raise RtlsUtilScanSlaveNotFoundException(
                    "Expected slave not found in scan list")
        elif isinstance(slave, dict):
            if 'addr' not in slave.keys() or 'addrType' not in slave.keys() or 'advSID' not in slave.keys() or 'periodicAdvInt' not in slave.keys():
                raise RtlsUtilException(
                    "Input slave not a string and not contains required keys")
        else:
            raise RtlsUtilException(
                "Input slave is nor string neither dict - invalid input")

        self._padv_current_slave = (slave['addr'], slave['advSID'])
        # Get sync handle
        sync_handle = self.padv_get_sync_handle_by_slave(slave)

        if sync_handle > -1:
            self._master_node.rtls.connectionless_aoa_enable(cl_aoa_params['cl_aoa_role'],
                                                             cl_aoa_params['cl_aoa_result_mode'],
                                                             sync_handle,
                                                             int(enable),
                                                             cl_aoa_params['cl_aoa_slot_durations'],
                                                             cl_aoa_params['cl_aoa_sample_rate'],
                                                             cl_aoa_params['cl_aoa_sample_size'],
                                                             cl_aoa_params['cl_aoa_sampling_control'],
                                                             cl_aoa_params['max_sample_cte'],
                                                             cl_aoa_params['cl_aoa_pattern_len'],
                                                             cl_aoa_params['cl_aoa_ant_pattern']
                                                             )

        def true_cond_func(sync_dict):
            return sync_dict[self._padv_current_slave].cl_aoa_enable == enable

        self._rtls_wait(true_cond_func, self._padv_sync_dict,
                        "Master node to set connectionless aoa state")

    def padv_create_sync(self, slave, options, skip, syncTimeout, syncCteType):

        if isinstance(slave, str):
            slave = self._get_slave_by_addr(slave)
            if slave is None:
                raise RtlsUtilScanSlaveNotFoundException(
                    "Expected slave not found in scan list")
        elif isinstance(slave, dict):
            if 'addr' not in slave.keys() or 'addrType' not in slave.keys() or 'advSID' not in slave.keys() or 'periodicAdvInt' not in slave.keys():
                raise RtlsUtilException(
                    "Input slave not a string and not contains required keys")
        else:
            raise RtlsUtilException(
                "Input slave is nor string neither dict - invalid input")

        self._padv_current_slave = (slave['addr'], slave['advSID'])
        # Extract bit0 and bit 1 for later usage
        b0 = options & 1
        b1 = options >> 1 & 1

        if b0 == 1 \
                and self._padv_current_slave[0].lower() == "ff:ff:ff:ff:ff:ff" \
                and self._padv_current_slave in self._padv_sync_dict.keys():  # Connect from periodic advertiser list
            self._padv_sync_dict.pop(self._padv_current_slave)  # remove BD address of slave from list to start again

        if self._padv_current_slave not in self._padv_sync_dict.keys():
            self._padv_sync_dict[self._padv_current_slave] = ConnectionlessAOASync(False, False,
                                                                                   True if b1 == 0 else False, False,
                                                                                   False, -1)
        else:
            self._padv_sync_dict[self._padv_current_slave].sync_report_enable = True if b1 == 0 else False

        self._master_node.rtls.create_sync(slave['advSID'],
                                           options,
                                           slave['addrType'],
                                           slave['addr'],
                                           skip,
                                           syncTimeout,
                                           syncCteType
                                           )

        def true_cond_func(sync_dict):
            return sync_dict[self._padv_current_slave].sync_created == True

        self._rtls_wait(true_cond_func, self._padv_sync_dict,
                        "Master node to create sync")

    def padv_create_sync_cancel(self):
        if self._padv_current_slave:
            if self._padv_current_slave in self._padv_sync_dict.keys():
                if not self._padv_sync_dict[self._padv_current_slave].sync_established:
                    self._master_node.rtls.create_sync_cancel()

                    def true_cond_func(x):
                        return x[self._padv_current_slave].sync_created is False

                    self._rtls_wait(
                        true_cond_func, self._padv_sync_dict, "Master node to cancel sync")

                    self._padv_sync_dict.pop(self._padv_current_slave)
                else:
                    raise RtlsUtilException(
                        "Can not cancel sync after it has been established")

            else:
                raise RtlsUtilException(
                    f"Slave address does not exist : {self._padv_current_slave}")
        else:
            raise RtlsUtilException(f"No current slave indicated")

        self._padv_current_slave = None

    def padv_terminate_sync(self, syncHandle):
        slave = self._padv_find_address_by_handle(syncHandle)
        self._padv_current_slave = (slave[0], slave[1])

        if self._padv_sync_dict[self._padv_current_slave].sync_established:
            self._master_node.rtls.terminate_sync(syncHandle)

            def true_cond_func(x):
                return x[self._padv_current_slave].sync_created is False

            self._rtls_wait(true_cond_func, self._padv_sync_dict,
                            "Master node to terminate sync")

            if not self._padv_sync_dict[self._padv_current_slave].in_padv_list:
                self._padv_sync_dict.pop(self._padv_current_slave)

            self._padv_current_slave = None

    def _padv_find_address_by_handle(self, syncHandle):
        ret_address = [key for key in self._padv_sync_dict if
                       syncHandle == self._padv_sync_dict[key].sync_handle]
        ret_address = ret_address[0] if len(ret_address) > 0 else None

        if ret_address is None:
            raise RtlsUtilException(f"No address matches to the wanted handle: {syncHandle}")

        return ret_address

    def padv_periodic_receive_enable(self, syncHandle):
        slave = self._padv_find_address_by_handle(syncHandle)
        self._padv_current_slave = (slave[0], slave[1])

        self._padv_sync_dict[self._padv_current_slave].sync_report_enable = False

        self._master_node.rtls.periodic_receive_enable(syncHandle, 1)

        def true_cond_func(x): return x.sync_report_enable is True

        self._rtls_wait(true_cond_func, self._padv_sync_dict[self._padv_current_slave],
                        "Master node to enable periodic report receive")

    def padv_periodic_receive_disable(self, syncHandle):
        slave = self._padv_find_address_by_handle(syncHandle)
        self._padv_current_slave = (slave[0], slave[1])

        self._padv_sync_dict[self._padv_current_slave].sync_report_enable = True

        self._master_node.rtls.periodic_receive_enable(syncHandle, 0)

        def true_cond_func(x): return x.sync_report_enable is False

        self._rtls_wait(true_cond_func, self._padv_sync_dict[self._padv_current_slave],
                        "Master node to disable periodic report receive")

    def padv_add_device_to_periodic_adv_list(self, slave):
        if isinstance(slave, str):
            slave = self._get_slave_by_addr(slave)
            if slave is None:
                raise RtlsUtilScanSlaveNotFoundException(
                    "Expected slave not found in scan list")
        elif isinstance(slave, dict):
            if 'addr' not in slave.keys() or 'addrType' not in slave.keys() or 'advSID' not in slave.keys() or 'periodicAdvInt' not in slave.keys():
                raise RtlsUtilException(
                    "Input slave not a string and not contains required keys")
        else:
            raise RtlsUtilException(
                "Input slave is nor string neither dict - invalid input")

        self._padv_current_slave = (slave['addr'], slave['advSID'])
        if self._padv_current_slave not in self._padv_sync_dict.keys():
            self._padv_sync_dict[self._padv_current_slave] = ConnectionlessAOASync(
                False, False, False, False, False, -1)

        self._master_node.rtls.add_device_to_periodic_adv_list(
            slave['addrType'], slave['addr'], slave['advSID'])

        true_cond_func = lambda x: x.in_padv_list is True
        self._rtls_wait(true_cond_func, self._padv_sync_dict[(slave['addr'], slave['advSID'])],
                        "Add device to list event")

    def padv_remove_device_from_periodic_adv_list(self, slave):
        if isinstance(slave, str):
            slave = self._get_slave_by_addr(slave)
            if slave is None:
                raise RtlsUtilScanSlaveNotFoundException(
                    "Expected slave not found in scan list")
        elif isinstance(slave, dict):
            if 'addr' not in slave.keys() or 'addrType' not in slave.keys() or 'advSID' not in slave.keys() or 'periodicAdvInt' not in slave.keys():
                raise RtlsUtilException(
                    "Input slave not a string and not contains required keys")
        else:
            raise RtlsUtilException(
                "Input slave is nor string neither dict - invalid input")

        if (slave['addr'], slave['advSID']) not in self._padv_sync_dict.keys():
            raise RtlsUtilException(f"Input slave does not exits in slaves dictionary: {slave['addr']}")
        elif not self._padv_sync_dict[(slave['addr'], slave['advSID'])].in_padv_list:
            raise RtlsUtilException(
                f"Input slave does not exits in embedded periodic advertisers list: {slave['addr']}")
        else:
            self._padv_current_slave = (slave['addr'], slave['advSID'])

            self._master_node.rtls.remove_device_from_periodic_adv_list(slave['addrType'], slave['addr'],
                                                                        slave['advSID'])

            true_cond_func = lambda x: x.in_padv_list is False
            self._rtls_wait(true_cond_func, self._padv_sync_dict[(slave['addr'], slave['advSID'])],
                            "Remove device from list event")

    def padv_read_periodic_adv_list_size(self):
        self._padv_read_list_size_complete.clear()

        self._master_node.rtls.read_periodic_adv_list_size()

        def true_cond_func(x): return x.is_set()

        self._rtls_wait(
            true_cond_func, self._padv_read_list_size_complete, "Read list size event")

        return self.padv_list_size

    def padv_clear_periodic_adv_list(self):
        self._padv_clear_adv_list_complete.clear()

        self._master_node.rtls.clear_periodic_adv_list()

        def true_cond_func(x): return x.is_set()

        self._rtls_wait(
            true_cond_func, self._padv_clear_adv_list_complete, "Clear adv list event")

    def padv_get_sync_handle_by_slave(self, slave):
        if isinstance(slave, str):
            slave = self._get_slave_by_addr(slave)
            if slave is None:
                raise RtlsUtilScanSlaveNotFoundException("Expected slave not found in scan list")
        elif isinstance(slave, dict):
            if 'addr' not in slave.keys() or 'addrType' not in slave.keys() or 'advSID' not in slave.keys() or 'periodicAdvInt' not in slave.keys():
                raise RtlsUtilException("Input slave not a string and not contains required keys")
        else:
            raise RtlsUtilException("Input slave is nor string neither dict - invalid input")

        if (slave['addr'], slave['advSID']) in self._padv_sync_dict.keys():
            return self._padv_sync_dict[(slave['addr'], slave['advSID'])].sync_handle
        else:
            return -1

    def sync(self, slave, options, skip, syncTimeout, syncCteType, scan_time_sec):
        if skip != 0:
            timeout_condition = syncTimeout >= skip * slave['periodicAdvInt']
        else:
            timeout_condition = syncTimeout >= slave['periodicAdvInt']

        if timeout_condition:
            self.padv_create_sync(slave,
                                  options,
                                  skip,
                                  syncTimeout,
                                  syncCteType)
            # Scan again for sync established event
            self.scan(scan_time_sec, slave['addr'], slave['advSID'])

            sync_handle = self.padv_get_sync_handle_by_slave(slave)
        else:
            raise RtlsUtilException("Timeout condition does not satisfied")

        return sync_handle

    def read_heap_size(self):

        self._read_heap_size_complete.clear()

        self._master_node.rtls.heap_req()

        def true_cond_func(x): return x.is_set()

        self._rtls_wait(true_cond_func, self._read_heap_size_complete, "Read heap size event")

        return {'total_heap': self.total_heap, 'free_heap': self.free_heap}

    ######
