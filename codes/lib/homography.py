# Dependencies
import numpy as np
import matplotlib.pyplot as plt
import cv2 as cv


# Extracting Co-ordinates of matching points using SIFT Operator
def points_extractor(image1, image2,  verbose=False,feature_descriptor='ORB'):
    if feature_descriptor == 'ORB':
        orb = cv.ORB_create()
        keypoints_1, descriptors_1 = orb.detectAndCompute(image1, None)
        keypoints_2, descriptors_2 = orb.detectAndCompute(image2, None)
    else:
        sift = cv.SIFT_create()
        keypoints_1, descriptors_1 = sift.detectAndCompute(image1, None)
        keypoints_2, descriptors_2 = sift.detectAndCompute(image2, None)

    # BFMatcher with default params
    bf = cv.BFMatcher()
    matches = bf.knnMatch(descriptors_1, descriptors_2, k=2)

    # Apply ratio test
    good = []

    for m, n in matches:
        if m.distance < .75 * n.distance:
            good.append([m])

    matching_points = np.float32([[keypoints_1[mat[0].queryIdx].pt, keypoints_2[mat[0].trainIdx].pt] for mat in good])
    if verbose:
        print("Number of Good Matches : ", len(good))

    if verbose:
        # Visualization
        f3 = cv.drawMatchesKnn(image1, keypoints_1, image2, keypoints_2, good, None)

        fig = plt.figure(figsize=(18, 6))
        plt.imshow(f3)
        plt.axis("off")
        plt.title("Visualizing Top Matches")
        plt.show()
    return matching_points


# FINDING HOMOGRAPHY BETWEEN TWO IMAGES
def find_homography(mask1, mask2, method=cv.RANSAC, verbose=False,feature_descriptor = 'ORB'):
    # im1 = cv.imread(mask1)
    # im2 = cv.imread(mask2)
    m_points = points_extractor(mask1, mask2, verbose,feature_descriptor)
    if m_points.shape[0]<4:
        print("Unmatched Masks")
        return None
    src_pts = m_points[:, 0, :]
    dst_pts = m_points[:, 1, :]
    H, _ = cv.findHomography(src_pts, dst_pts, method)
    return H





