import numpy as np
import pandas as pd

def calculate_angles(u,v,Level_Angle = 5):
    camera_position_u = 2000-u
    camera_position_v = 1500 - v

    focal_length = 6.7              # mm
    pixel_size = 1/0.8              # pixel/micrometer
    f = focal_length*1000/pixel_size
    
    azimuth_angle = np.arctan2(camera_position_u,f)
    elevation_angle = np.arctan2(f,(camera_position_v*np.cos(azimuth_angle)))

    level_angle = np.radians(Level_Angle)
    
    # CASE-I AOA ANGLE
    aoabefore = np.arccos(np.cos(azimuth_angle)*np.sin(elevation_angle))

    # CASE-II AOA ANGLE
    aoa = np.arccos(np.cos(elevation_angle)*np.sin(level_angle)+np.cos(level_angle)*np.cos(aoabefore))

    if azimuth_angle>0:
        aoabefore,aoa = -aoabefore,-aoa

    return np.degrees(aoabefore),np.degrees(aoa)



#Functions to Calculate Azimuth and Elevation
def pixel_calculate(LEVELangle,AOAangle1,AOAangle2, return_angles = False):

    aoaangle1 = np.radians(AOAangle1)
    aoaangle2 = np.radians(AOAangle2)
    levelangle = np.radians(LEVELangle)


    elevation_angle = np.arccos((np.cos(aoaangle2)-np.cos(aoaangle1)*np.cos(levelangle))/np.sin(levelangle))
    azimuth_angle = np.arccos(np.cos(aoaangle1)/np.sin(elevation_angle))

    if AOAangle1>0:
        azimuth_angle= -azimuth_angle

    if return_angles:
        return (np.degrees(azimuth_angle),np.degrees(elevation_angle))
    
    
    bool1 = pd.isnull(np.degrees(azimuth_angle))
    bool2 = pd.isnull(np.degrees(elevation_angle))

    if (bool1 | bool2):
        # print("The Azimuth and Elevation Angles are Incorrect")
        return (  -1,-1)
    else:
        focal_length = 6.7 # Focal Length/mm
        pixel_size = 1/0.8  # Individual Pixel size/ micro meter
        f = focal_length * 1000 / pixel_size  # Pixel Focal Length

        camera_positon_u = f * (np.sin(azimuth_angle) / np.cos(azimuth_angle))  # Camera Co-ordinates -> Co-ordinate System Established by the Center of the Camera
        camera_position_v = f * (np.cos(elevation_angle) / (np.cos(azimuth_angle) * np.sin(elevation_angle)))
        

        # Co-ordinate System Conversion: Camera co-ordinate -> GUI Co-ordinate
        u = (2000 - camera_positon_u)
        v = (1500 - camera_position_v)

        return (u, v)