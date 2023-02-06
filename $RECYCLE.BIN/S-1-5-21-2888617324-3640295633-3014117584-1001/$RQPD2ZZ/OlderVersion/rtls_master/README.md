# RTLS System

## Table of Contents

* [General Information](#general-information)
* [Introduction](#Introduction)
* [General Configuration](#general-configuration)
* [Angle of Arrival - Setup](#aoa-setup)
	* [Software Setup](#aoa-software-setup)
	* [Hardware Setup](#aoa-hardware-setup)
	* [Running The Example](#aoa-running-the-example)
	* [Optional For Extra Accuracy](#Optional-for-extra-accuracy)
    * [RAW Mode](#raw-mode)

# <a name="general-informatio"></a>General Information

1. Detailed guide can be found on [SimpleLink Academy](http://dev.ti.com/tirex/explore/node?node=ADoNVRzIjRH1Ft0aHjErQg__pTTHBmu__LATEST)
2. To get usage information for the RTLS Node Manager scripts and GUI please refer to: `tools\ble5stack\rtls_agent\README.md`
3. In order to edit and view how the RTLS subsystem handles uNPI commands, please refer to the following file: `tools\ble5stack\rtls_agent\rtls\rtls\ss_rtls.py`
4. In order to see a usage example, please refer to `tools\ble5stack\rtls_agent\examples\rtls_example.py` which shows how to use a RTLS Master + RTLS Slave + RTLS Passive combination
5. To access GUI, please refer to the readme file found in `tools\ble5stack\rtls_agent`.

# <a name="Introduction"></a>Introduction

This readme contains the following information:
1. How to setup AoA demo
2. Description of commands accepted by RTLS Control and their meaning
Both Connected AoA and Connectionless AoA are activated by OOB example

# <a name="general-configuration"></a>General Configuration

The following is a list of all possible build defines and corresponding options
that can be set for each define in the build_config.opt file:

Add the following define to  build_config.opt (using "-D") to activate the following option:

#### GATT_DB_OFF_CHIP
Indicates that the GATT database is maintained off the chip on the Application Processor (AP).

#### GAP_BOND_MGR
 Used to include the Bond Manager

#### HOST_CONFIG
(BLE Host Build Configurations) Possible Options:

* PERIPHERAL_CFG      - Used to include the GAP Peripheral Role support
* CENTRAL_CFG         - Used to include the GAP Central Role support
* BROADCASTER_CFG     - Used to include the GAP Broadcaster Role support
* OBSERVER_CFG        - Used to include the GAP Observer Role support

#### BLE_V41_FEATURES
Configure the stack to use features from the BLE 4.1 Specification

* L2CAP_COC_CFG       - Enable L2CAP Connection Oriented Channels

#### BLE_V50_FEATURES
Configure the stack to use features from the BLE 5.0 Specification
The following BLE 5.0 features are enabled by default and cannotbe disabled.

* PHY_2MBPS_CFG       - Enable 2 Mbps data rate in the Controller
* HDC_NC_ADV_CFG      - Enable High Duty Cycle Non-Connectable Advertising
* CHAN_ALGO2_CFG      - Enable Channel Selection Algorithm 2

#### HCI_TL_FULL
All supported HCI commands are available via the Tranport Layer's NPI. Intended for NP solution.

#### HCI_TL_NONE
No supported HCI commands are available via the Transport Layer's NPI. Intended for SOC solutions.

#### Periodic Advertising and Connectionless AoA
Receiver - RTLS Master

* MAX_NUM_CTE_BUFS=xx
* USE_PERIODIC_SCAN
* USE_PERIODIC_RTLS

Transmitter - RTLS Slave

* USE_PERIODIC_ADV

#### Combo Roles:
Combo roles can be set by defining multiple roles for HOST_CONFIG. The possible combo roles and HOST_CONFIG defines are:
* Peripheral + Observer  :    PERIPHERAL_CFG+OBSERVER_CFG
* Central + Broadcaster  :    CENTRAL_CFG+BROADCASTER_CFG
* Peripheral + Central   :    PERIPHERAL_CFG+CENTRAL_CFG

# <a name="aoa-setup"></a>Angle of Arrival - Setup
## <a name="aoa-software-setup"></a>Software Setup
AoA is currently supported on all roles with the following caveats:

#### RTLS Master
* Master role will collect I/Q samples
* Master role supports the official BT5.1 Connected AoA implementation
* AoA API's can be accessed by using RTLS Services host module

#### RTLS Slave
* Slave will send out a constant tone at the end of connection packet and it will not collect I/Q samples
* Slave supports the official BT5.1 Connected AoA implementation
* AoA API's can be accessed by using RTLS Services host module
* The tone length is configured by the user using the CTE Time parameter (refer to `tools\ble5stack\rtls_agent\rtls\rtls\ss_rtls.py`). **Note that RTLS Passive only supports reception of a tone of length 20**

#### RTLS Passive
* Passive will collect I/Q samples with the following limitation: **CTE Time is always configured to 20, Sample Rate is always 4Mhz and Sample Size is always 16 bit**
* When using AoA raw output mode (AOA_MODE_RAW), consider the following:
    1. Connection interval of BLE must be at least 300ms to accomodate outputing all of the samples (a large 2k bytes chunk)
    2. Large amounts of heap will be used to support this mode


## <a name="aoa-hardware-setup"></a>Hardware Setup
**Note: Pin 29 will be held high on application initialization in order to enable a TX/RX antenna in cases where BOOSTXL-AOA is attached**

AoA requires 2 devices at minimum: RTLS Master/Slave.
The devices should be flashed with the rtls_master/rtls_slave applications as described above (with AoA flags).
Compile and flash your applications.

* RTLS Master - CC2642R1 LaunchPad with BOOSTXL-AOA

## <a name="Optional-for-extra-accuracy"></a>Optional For Extra Accuracy
Add an RTLS Passive to the setup - also equipped with BOOSTXL-AOA

**For the RTLS Master/Passive hardware setup, please take a look at**
[Angle of Arrival BoosterPack](http://dev.ti.com/tirex/#/?link=Development%20Tools%2FKits%20and%20Boards%2FAngle%20of%20Arrival%20BoosterPack)

## <a name="aoa-running-the-example"></a>Running The Example
The steps to run the out of box example is described in `tools\ble5stack\rtls_agent\README.html`

* Mind the timing when using both features, if the connection interval is insufficient, it may be that the SW stack won't have enough resources to both keep the BLE connection alive and continuously output results
* The best way to check your timings is by using a Logic Analyzer and debugging the RF RX and TX signals. Refer [BLE5-Stack Debugging Guide](http://dev.ti.com/tirex/explore/node?node=AORHSvJNCJkn6rS93wDgGg__pTTHBmu__LATEST).

## <a name="raw-mode"></a>Raw Mode
Note that this mode puts extra strain on the UART and the timing of the system since RAW mode involves outputing large chunks of data.

**When using RAW mode for AoA**
* Minimum recommended latency (Connection Interval) is 300ms
* Maximal recommended latency is 800ms
