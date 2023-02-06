# VisBLE

This is the basic projecct for the paper "VisBLE: Intuitive BLE identification" 

VisBLE is a system that enhance the BLE 5.1 device identification by combining the wireless localization technology and the vision technology.

This project page contains: 
- Azimuth and Elevation estimation based on level meter. 
- Vision Enhanced BLE Identification.

## Some prior prepation：
- Guidelines for using CC26X2 development board: http://dev.ti.com/tirex/explore/node?node=AHYhhuDNTaRXzkOlahOlvA__pTTHBmu__LATEST
- Introduction to the RTLS toolbox: https://dev.ti.com/tirex/content/simplelink_cc13x2_26x2_sdk_4_20_00_35/docs/ble5stack/ble_user_guide/html/ble-stack-5.x-guide/localization-index-cc13x2_26x2.html#angle-of-arrival
- Summary of common device problems: https://e2echina.ti.com/question_answer/wireless_connectivity/bluetooth/f/103/t/185638

## Azimuth and Elevation estimation based on level meter.
The mobile device implements the Level meter app, and the PC device runs Azimuth and elevation and estimation based on level meter. The azimuth and elevation angles are separated from the AoA angle obtained by the Bluetooth chip, and the pixel coordinates of the AoA point cloud are estimated.

## Vision Enhanced BLE Identification.
Images from the camera are inspected and split into mask segments by some pre-trained instance segmentation algorithm(Mask R-CNN).
The mask matching is through both the pixel distance and the homography, a technology to inspect the depth of the mask. 
Since each mask contains thousands of pixels, we use edge detection approaches, such as SIFT and SURF to extract feature points from the masks
