# RTLS Agent

RTLS Agent folder contains custom python package (rtls, unpi and rtls_util) and example to present capability of RTLS CCI, AoA and CL AOA for CC26x2. 

## Getting Started

Instructions below will setup your python environment with required packages.  

### Prerequisites

- The latest version of [Python 3.7]( https://www.python.org )

    Note: Python 3.7 should be installed at **_C:\Python37_**. 
    
    If it is not the case, you have to modify the content of `package.bat` / `package.sh` to have the variables `PYTHON3` and `PIP3` pointing on the right location
    ```
    rem set PYTHON3=C:\Python37\python
    rem set PIP3=C:\Python37\Scripts\pip
    set PYTHON3=<Python 3.7 directory>\python
    set PIP3=<Python 3.7 directory>\Scripts\pip
    ```


- [Code Composer Studio (CCS)](http://www.ti.com/tool/CCSTUDIO) 
- Set of three CC26x2 devices.


### Installing
* Setup external packages in case you network is behind a proxy use ```[--proxy]```
    ```
    cd <rtls_agent folder>
    
    c:\Python37\Scripts\pip.exe install -r requirements.txt [--proxy <www.proxy.com>]
    ```

* Setup Texas Instrument custom packages

    ```
    cd <rtls_agent folder>
    
    package.bat -c -b -u -i 
    ```
    
    for more information about package.bat try

    ```
    cd <rtls_agent folder>
    
    package.bat -h 
    ```
* Import the examples rtls_master, rtls_slave and (if needed) rtls_passive under CCS. The examples are stored under examples\rtos\CC26X2R1_LAUNCHXL\ble5stack.
Build the binaries and flash the devices.
  
     
## Running Non-Visual Demo

Non-visual demo its python example that uses rtls_util packages to start and run RTLS CCI / CL AOA / AOA functionality for CC26x2.   

Before executing example open and edit **<rtls_agent dir>/examples/rtls_example_with_rtls_util.py** in order to enable / disable functionality.

Executing example: 
```
cd <rtls_agent folder>/examples

c:\Python37\python.exe rtls_example_with_rtls_util.py  
```


## Running Visual Demo

##### Visual demo based on two elements
* Backend - Application that communicates with devices and reports to the frontend via WebSocket
* Frontend - Based on Angular 8

##### Required
* Installed latest Chrome browser 

##### Step by step guide to start visual demo:

1. Open CMD / Terminal at **<rtls_agent folder>/rtls_ui**
2. Start **rtls_ui** 
    ```
    rtls_ui.exe [Windows 10]
    rtls_ui [Ubuntu 18.04]
    rtls_ui_macos [macOS Catalina]
    ``` 
3. Wait for the Chrome to start on http://127.0.0.1:5005 [ <sup id="n1">[1](#f1)</sup> ]
4. Refresh UI to latest by hiting CTRL + F5
5. Press on "Get Started !"
6. Select RTLS feature
7. Select RTLS master device
8. Press on "Auto Play" to start the auto process of:
    1. Scanning for Slave
    2. Selecting best Slave by RSSI
    3. Connecting to selected Slave
    4. Starting available features

##### Notes
<b id="n1">1</b>: In case UI not start in Chrome. Open Chrome and type URL manually [↩](#a1)
