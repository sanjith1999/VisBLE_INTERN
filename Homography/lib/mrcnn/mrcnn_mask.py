# Dependencies
import numpy as np
import matplotlib.pyplot as plt
import cv2 as cv
# Own Dependencies
import mrcnn
import mrcnn
import mrcnn.config
import mrcnn.model
import mrcnn.visualize
import mrcnn.utils
import skimage
import os



# Extracting Co-ordinates of matching points using SIFT Operator
def points_extractor(image1,image2,verbose=False):
    sift = cv.SIFT_create()

    keypoints_1, descriptors_1 = sift.detectAndCompute(image1,None)
    keypoints_2, descriptors_2 = sift.detectAndCompute(image2,None)

    # BFMatcher with default params
    bf = cv.BFMatcher()
    matches = bf.knnMatch(descriptors_1,descriptors_2, k=2)

    # Apply ratio test
    good = []

    for m,n in matches:
        if m.distance < .7*n.distance:
            good.append([m])

    matching_points = np.float32([[keypoints_1[mat[0].queryIdx].pt, keypoints_2[mat[0].trainIdx].pt]  for mat in good ])
    print("Number of Good Matches : ", len(good))

    if verbose:
        # Visualization
        image1_gray=cv.cvtColor(image1,cv.COLOR_BGR2GRAY)
        image2_gray=cv.cvtColor(image2,cv.COLOR_BGR2GRAY)
        f3 = cv.drawMatchesKnn(image1_gray,keypoints_1,image2_gray,keypoints_2,good,None)


        fig = plt.figure(figsize=(18, 6))
        plt.imshow(f3)
        plt.axis("off")
        plt.title("Visualizing Top Matches")
        plt.show()
    return matching_points


# FINDING HOMOGRAPHY BETWEEN TWO IMAGES
def find_homography(mask1, mask2, method=cv.LMEDS, verbose = False):
    im1 = cv.imread(mask1)
    im2 = cv.imread(mask2)
    m_points = points_extractor(im1, im2,verbose)
    src_pts = m_points[:,0,:]
    dst_pts = m_points[:,1,:]
    H,_ = cv.findHomography(src_pts,dst_pts,method)
    return H



# Function to Mask-Out Object
def mask_out_images(IMG_DIR, RESULTS_DIR, item= "bottle"):

    MODEL_DIR = './logs'
    COCO_MODEL_PATH = './weights/mask_rcnn_coco.h5'

    # Class Names
    class_names = ['BG', 'person', 'bicycle', 'car', 'motorcycle', 'airplane',
                'bus', 'train', 'truck', 'boat', 'traffic light',
                'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird',
                'cat', 'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear',
                'zebra', 'giraffe', 'backpack', 'umbrella', 'handbag', 'tie',
                'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
                'kite', 'baseball bat', 'baseball glove', 'skateboard',
                'surfboard', 'tennis racket', 'bottle', 'wine glass', 'cup',
                'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
                'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza',
                'donut', 'cake', 'chair', 'couch', 'potted plant', 'bed',
                'dining table', 'toilet', 'tv', 'laptop', 'mouse', 'remote',
                'keyboard', 'cell phone', 'microwave', 'oven', 'toaster',
                'sink', 'refrigerator', 'book', 'clock', 'vase', 'scissors',
                'teddy bear', 'hair drier', 'toothbrush']

    class InferenceConfig(mrcnn.config.Config):
        # Name of the Configuration
        NAME = 'coco_inference'

        # GPU Parameters
        GPU_COUNT = 1
        IMAGES_PER_GPU = 1

        # Number of class = number of classes +1(Background)
        NUM_CLASSES = len(class_names)

    config = InferenceConfig()
    # config.display()

    # Initialize the Mask R-CNN model for inference and then load the weights.
    model = mrcnn.model.MaskRCNN(mode="inference", config=config, model_dir=MODEL_DIR)

    # Load the weights into the model.
    model.load_weights(filepath=COCO_MODEL_PATH, by_name=True)

    for i in os.listdir(IMG_DIR):    
        count = 0
        print(os.path.join(IMG_DIR,i))
        if(i.split('.')[-1]!='jpg'):
            break
        image = skimage.io.imread(os.path.join(IMG_DIR,i))
        results = model.detect([image],verbose = 0)
        r = results[0]
        # mrcnn.visualize.display_instances(image,r['rois'],r['masks'],r['class_ids'],class_names,r['scores'])
        masks = r['masks']
        for j in range(len(r['class_ids'])):
            if class_names[r['class_ids'][j]]==item:
                count = count + 1
                result = cv.bitwise_and(image,image,mask=(masks[:,:,j]).astype(np.uint8))
                cv.imwrite(os.path.join(RESULTS_DIR,i.split('.')[0]+'_%d'%count+'.jpg'),result)
        print("Number of Objects Detected:",count)
