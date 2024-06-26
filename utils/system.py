import torch, PIL, cv2, time
import numpy as np
from . import smartdisplay, morphology
import pydicom as dicom 

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
YELLOW = (255, 255, 0)
ORANGE = (226, 143, 65)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
NORMAL, MILD, MODERATE, SEVERE = WHITE, YELLOW, ORANGE, RED
COLOR_A = (118, 186, 153)
COLOR_B = (173, 207, 159)

# Filter the largest connected white component and return new image with that component
def filter_mask_binary(mask):
    _, mask = cv2.threshold(mask,127,255,cv2.THRESH_BINARY)                 # Isolate the black and white component (changes to binary image)
    h, w = mask.shape                                                       # Get the width and height
    mask = (mask//255).astype(np.uint8)                                     # Change all non-zero to 1 into binary format
    cnts, _ = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE) # Find all connected white points 
    cnt = max(cnts, key = cv2.contourArea)                                  # Get the largest area
    out = np.zeros(mask.shape, np.uint8)                                    # Draw new black image with the same shape
    out = cv2.drawContours(out, [cnt], -1, 255, cv2.FILLED)                 # Draw that area onto the new image
    _, out = cv2.threshold(out,127,255,cv2.THRESH_BINARY)                   # Isolate like the first line
    return out


# Blend 2 image im2, im3 onto the im1 while highlighting part in im2, im3 with different color
def imageWithMasks(im1, im2, im3, COLOR_A, COLOR_B):
    alpha = 0.3                                                             # Set the basic alpha
    im1rgb = cv2.cvtColor(im1, cv2.COLOR_GRAY2RGB)                          # change img1 from grayscale to rgb store in im1rgb
    #im1rgb = np.uint8(im1)
    im2 = cv2.threshold(im2, 128, 255, cv2.THRESH_BINARY)[1]                # Similar to above isolation
    im2rgb = cv2.cvtColor(im2, cv2.COLOR_GRAY2RGB)                          # Change to rgb type
    im2rgb = np.where(im2rgb==BLACK, im2rgb, COLOR_A)                       # Position with BLACK color will be replaced by COLOR_A
    im2rgb = np.uint8(im2rgb)                                               # Change to uint8 type
    im3 = cv2.threshold(im3, 128, 255, cv2.THRESH_BINARY)[1]                
    im3rgb = cv2.cvtColor(im3, cv2.COLOR_GRAY2RGB)
    im3rgb = np.where(im3rgb==BLACK, im3rgb, COLOR_B)
    im3rgb = np.uint8(im3rgb)
    im4rgb = im1rgb.copy()
    im4rgb = cv2.addWeighted(im2rgb + im3rgb, alpha, im4rgb, 1 - alpha, 0, im4rgb)  # Blend 2 img together in img4rgb
    im5 = cv2.threshold(im2 + im3, 128, 255, cv2.THRESH_BINARY)[1]           # Add 2 img and seperate white and black
    im5rgb = cv2.cvtColor(im5, cv2.COLOR_GRAY2RGB)                 
    res1 = np.where(im5rgb!=BLACK, im4rgb, BLACK)                            # Any element ISN'T BLACK will be replace by that position in img4rgb
    res2 = np.where(im5rgb==BLACK, im1rgb, BLACK)                            # Any element IS BLACK will be replace by img1rgbx
    res3 = cv2.bitwise_or(res1,res2)                                         # Perform OR operation on 2 images
    return res3

def readDCMFile():
    image_path = './sample.dcm'
    ds = dicom.dcmread(image_path)
    return ds


class system():

    # Initialize module for the class
    def __init__(self, detectModule, segmentModule, measureModule, device = "cpu"):
        self.detectModule = detectModule
        self.segmentModule = segmentModule
        self.measureModule = measureModule
        self.device = torch.device(device)
        self.clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        self.erosion = morphology.Erosion2d(1, 1, 10, soft_max=False)
        self.dilation = morphology.Dilation2d(1, 1, 10, soft_max=False)
        
    
    def assess(self,imagePath, visualise = False, flip = False):
        t0 = time.time()                                                                  # Get the time
        self.imagePath = imagePath                                                        # Assign the image path
        if flip == False:                                                                 # Read the image in color and grayscale and flip if needed
            self.imageRGB = cv2.imread(imagePath, cv2.IMREAD_COLOR)
            self.imageGRAY = cv2.imread(imagePath, cv2.IMREAD_GRAYSCALE)
        else:
            self.imageRGB = cv2.flip(cv2.imread(imagePath, cv2.IMREAD_COLOR),1)
            self.imageGRAY = cv2.flip(cv2.imread(imagePath, cv2.IMREAD_GRAYSCALE),1)
        self.imageCLAHE = self.clahe.apply(self.imageGRAY)                                 # Apply Histogram Equalizer to emphasize the CONTRAST color
        self.imageCLAHERGB = cv2.cvtColor(self.clahe.apply(self.imageGRAY), cv2.COLOR_GRAY2RGB)     # Change to RGB mode after using Histogram
        self.imageHeight, self.imageWidth = self.imageGRAY.shape                           # Getting height and Width from the image
        t1 = time.time()

        # This is a function using YOLO detection to retrieve the bounding box and extracting data into a series of detaching, cpu,.. and convert to numpy
        self.allDetect = self.detectModule.predict(self.imageCLAHERGB, save_txt = False, save_conf = True, verbose=False)[0].boxes.data.detach().cpu().numpy().astype("int")
        t2 = time.time()

        # Filter vertebra from all Detect
        self.vertebraDetect = self.allDetect[self.allDetect[:,5] == 0][np.flip(self.allDetect[self.allDetect[:,5] == 0,1].argsort())][:-1]
        crop_list_1 = []
        self.vertebraDetectPad = []
        for count, box in enumerate(self.vertebraDetect):
            pad = 0.2
            x1, y1, x2, y2 = box[0:4]                       # Extract coordinate from bounding box
            padX, padY = int((x2-x1)*pad), int((y2-y1)*pad) # Calculate padding from width and height

            # Adjust the bounding box to stay within the image width and height
            if y1 >= padY: y1 = y1 - padY
            if y1 < padY: y1 = 0
            if y2 + padY <= self.imageHeight: y2 = y2 + padY
            if y2 + padY > self.imageHeight: y2 = self.imageHeight
            if x1 >= padX: x1 = x1 - padX
            if x1 < padX: x1 = 0
            if x2 + padX <= self.imageWidth: x2 = x2 + padX
            if x2 + padX > self.imageWidth: x2 = self.imageWidth
            self.vertebraDetectPad.append([x1,y1,x2,y2])     # Adding all the points (both upper and lower) in detect pad
            crop = self.imageGRAY[y1:y2,x1:x2]               # Extract the vertebra region from the bounding box
            crop_enhanced = cv2.cvtColor(self.clahe.apply(crop),cv2.COLOR_GRAY2RGB)     # Change to RGB color mode
            #crop_enhanced = cv2.cvtColor(self.imageCLAHE[y1:y2,x1:x2],cv2.COLOR_GRAY2RGB)
            crop_list_1.append([crop, crop_enhanced])

        crop_list_2 = []
        self.spine = []
        with torch.no_grad():   # Deativate auto grad engine -> saving memory usage and computation
            self.segmentModule.eval()   # Change from training mode to inteference mode ( for doing tasks )
            t3 = time.time()
            for crop, crop_enhanced in crop_list_1:
                
                # Resize image
                # Change type from image to tensor and change format
                # Use segment module
                # Use sigmoid activate function (map input to 0 to 1, for binary classification)
                # Applies dilation operation (add pixel to object boundaries)
                # Applies erosion operation (remove pixel to object boundaries)

                crop_maskA = cv2.resize(filter_mask_binary(self.erosion(self.dilation(torch.sigmoid(self.segmentModule(torch.Tensor(cv2.resize(crop_enhanced/255, (256, 256))).permute(2, 0, 1).unsqueeze(0).to(self.device))).cpu())).squeeze(1).detach().numpy()[0]*255),(crop_enhanced.shape[1],crop_enhanced.shape[0]))
                crop_maskB = cv2.resize(filter_mask_binary(cv2.flip(self.erosion(self.dilation(torch.sigmoid(self.segmentModule(torch.Tensor(cv2.resize(cv2.flip(crop_enhanced,0)/255, (256, 256))).permute(2, 0, 1).unsqueeze(0).to(self.device))).cpu())).squeeze(1).detach().numpy()[0],0)*255),(crop_enhanced.shape[1],crop_enhanced.shape[0]))
                crop_list_2.append([crop, crop_maskA, crop_maskB])
        t4 = time.time()
        for crop, crop_maskA, crop_maskB in crop_list_2:
            vertebra = self.measureModule(crop,[crop_maskA,crop_maskB]) # Get all vertebra points
            self.spine.append(vertebra)
        t5 = time.time()
        self.elapsed, self.detectElapsed, self.segmentElapsed, self.measureElapsed = t5-t0, t2-t1, t4-t3, t5-t4
        
        self.fracture = 0
        for COUNT, VERTEBRA in enumerate(self.spine):
            if VERTEBRA.valid == 1 and COUNT > 0:
                if VERTEBRA.l > 0.2: self.fracture = 1 # Find if the vertebra has fractures
        
        if visualise == True:
            result = self.imageRGB.copy()

            # Draw a rectangle based on the vertabra detect points
            for COUNT, VERTEBRA in enumerate(self.spine):
                box = self.vertebraDetectPad[COUNT]   # Get all the vertebra detect points
                anchor = [box[0], box[1]]
                x1, y1, x2, y2 = box[0], box[1], box[2], box[3]
                cv2.rectangle(result,[x1,y1],[x2,y2],RED,2)  # Draw a rectangle around 4 points
            self.outputDetection = result

            maskA = np.zeros(result.shape[0:2], dtype = "uint8")  # Get the width and height of image and create a 2D array based on that
            maskB = np.zeros(result.shape[0:2], dtype = "uint8")
            for COUNT, VERTEBRA in enumerate(self.spine):
                if VERTEBRA.valid == 1 and COUNT > 0:
                    box = self.vertebraDetectPad[COUNT]
                    anchor = [box[0], box[1]]
                    x1, y1, x2, y2 = box[0], box[1], box[2], box[3]
                    maskA_temp = np.zeros(result.shape[0:2], dtype = "uint8")
                    maskB_temp = np.zeros(result.shape[0:2], dtype = "uint8")
                    maskA_temp[y1:y2,x1:x2] = VERTEBRA.A.input      # Copy the input from current vertebra to following region on maskA_temp
                    maskB_temp[y1:y2,x1:x2] = VERTEBRA.B.input
                    maskA = cv2.bitwise_or(maskA, maskA_temp)       # Combine 2 images to get the hightlighted part on maskA_temp
                    maskB = cv2.bitwise_or(maskB, maskB_temp)
            self.outputSegmentation = np.array([maskA, maskB])      # Get 2 hightlighted part - image to result
            
            result = np.zeros(result.shape[0:3], dtype = "uint8")   # Create a 3D array based on the result shape

            # Draw circle for the small points (including 4 vertebras and 2 middles) and connecting them using line
            for COUNT, VERTEBRA in enumerate(self.spine):
                if VERTEBRA.valid == 1 and COUNT > 0:
                    COLOR_CODE = WHITE
                    move_x = 200
                    box = self.vertebraDetectPad[COUNT]  
                    anchor = [box[0], box[1]]
                    position = anchor + VERTEBRA.centroid
                    cv2.line(result, anchor + VERTEBRA.a1, anchor + VERTEBRA.a2, COLOR_CODE, 3)
                    cv2.line(result, anchor + VERTEBRA.m1, anchor + VERTEBRA.m2, COLOR_CODE, 3)
                    cv2.line(result, anchor + VERTEBRA.p1, anchor + VERTEBRA.p2, COLOR_CODE, 3)
                    # Draw area between points
                    POINTS = np.array([[anchor + VERTEBRA.a1], [anchor + VERTEBRA.m1], 
                              [anchor + VERTEBRA.p1], [anchor + VERTEBRA.p2],
                              [anchor + VERTEBRA.m2], [anchor + VERTEBRA.a2]
                              ])
                    POINTS = POINTS.reshape((-1,1,2))
                    overlay = result.copy()
                    cv2.fillPoly(overlay, [POINTS], COLOR_CODE)

                    alpha = 0.4
                    result = cv2.addWeighted(overlay, alpha, result, 1 - alpha, 0)

                    cv2.circle(result, (anchor + VERTEBRA.a1), 7, COLOR_CODE, -1)
                    cv2.circle(result, (anchor + VERTEBRA.a2), 7, COLOR_CODE, -1)
                    cv2.circle(result, (anchor + VERTEBRA.m1), 7, COLOR_CODE, -1)
                    cv2.circle(result, (anchor + VERTEBRA.m2), 7, COLOR_CODE, -1)
                    cv2.circle(result, (anchor + VERTEBRA.p1), 7, COLOR_CODE, -1)
                    cv2.circle(result, (anchor + VERTEBRA.p2), 7, COLOR_CODE, -1)
            self.outputMeasurement = result
            
            # Draw circle for the small points (including 4 vertebras and 2 middles) and connecting them using line
            # Adding color based on the severion of the fracture
            # Adding text for more information of the fracture
            result = imageWithMasks(self.imageGRAY,maskA,maskB,COLOR_A,COLOR_B)
            FONT_SCALE = 1.5
            for COUNT, VERTEBRA in enumerate(self.spine):
                if VERTEBRA.valid == 1 and COUNT > 0:
                    if VERTEBRA.l > 0.2 and VERTEBRA.l <= 0.25: COLOR_CODE = MILD
                    elif VERTEBRA.l > 0.25 and VERTEBRA.l <= 0.40: COLOR_CODE = MODERATE
                    elif VERTEBRA.l > 0.40: COLOR_CODE = SEVERE
                    else: COLOR_CODE = NORMAL
                    move_x = 180
                    box = self.vertebraDetectPad[COUNT]  
                    anchor = [box[0], box[1]]
                    position = anchor + VERTEBRA.centroid
                    cv2.line(result,  anchor + VERTEBRA.a1, anchor + VERTEBRA.a2, COLOR_CODE, 3)
                    cv2.line(result, anchor + VERTEBRA.m1, anchor + VERTEBRA.m2, COLOR_CODE, 3)
                    cv2.line(result, anchor + VERTEBRA.p1, anchor + VERTEBRA.p2, COLOR_CODE, 3)
                    # Draw area between points
                    POINTS = np.array([[anchor + VERTEBRA.a1], [anchor + VERTEBRA.m1], 
                              [anchor + VERTEBRA.p1], [anchor + VERTEBRA.p2],
                              [anchor + VERTEBRA.m2], [anchor + VERTEBRA.a2]
                              ])
                    POINTS = POINTS.reshape((-1,1,2))
                    overlay = result.copy()
                    cv2.fillPoly(overlay, [POINTS], COLOR_CODE)

                    alpha = 0.4
                    result = cv2.addWeighted(overlay, alpha, result, 1 - alpha, 0)

                    cv2.circle(result, (anchor + VERTEBRA.a1), 7, COLOR_CODE, -1)
                    cv2.circle(result, (anchor + VERTEBRA.a2), 7, COLOR_CODE, -1)
                    cv2.circle(result, (anchor + VERTEBRA.m1), 7, COLOR_CODE, -1)
                    cv2.circle(result, (anchor + VERTEBRA.m2), 7, COLOR_CODE, -1)
                    cv2.circle(result, (anchor + VERTEBRA.p1), 7, COLOR_CODE, -1)
                    cv2.circle(result, (anchor + VERTEBRA.p2), 7, COLOR_CODE, -1)
                    cv2.putText(result, ("Ha: {} mm".format(round(VERTEBRA.ha*0.15,1))), (position[0]+move_x, position[1]-70), cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, COLOR_CODE, 6)   
                    cv2.putText(result, ("Hm: {} mm".format(round(VERTEBRA.hm*0.15,1))), (position[0]+move_x, position[1]-25), cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, COLOR_CODE, 6)
                    cv2.putText(result, ("Hp: {} mm".format(round(VERTEBRA.hp*0.15,1))), (position[0]+move_x, position[1]+20), cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, COLOR_CODE, 6)
                    cv2.putText(result, ("Loss: {}%".format(round(VERTEBRA.l*100,1))), (position[0]+move_x, position[1]+65), cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, COLOR_CODE, 6)
            self.output = result
            
            result = cv2.cvtColor(self.imageGRAY,cv2.COLOR_GRAY2RGB)
            for COUNT, VERTEBRA in enumerate(self.spine):
                if VERTEBRA.valid == 1 and COUNT > 0:
                    if VERTEBRA.l > 0.2 and VERTEBRA.l <= 0.25: COLOR_CODE = MILD
                    elif VERTEBRA.l > 0.25 and VERTEBRA.l <= 0.40: COLOR_CODE = MODERATE
                    elif VERTEBRA.l > 0.40: COLOR_CODE = SEVERE
                    else: COLOR_CODE = NORMAL
                    if VERTEBRA.l > 0.2:
                        move_x = 180
                        box = self.vertebraDetectPad[COUNT]  
                        anchor = [box[0], box[1]]
                        position = anchor + VERTEBRA.centroid
                        cv2.line(result,  anchor + VERTEBRA.a1, anchor + VERTEBRA.a2, COLOR_CODE, 3)
                        cv2.line(result, anchor + VERTEBRA.m1, anchor + VERTEBRA.m2, COLOR_CODE, 3)
                        cv2.line(result, anchor + VERTEBRA.p1, anchor + VERTEBRA.p2, COLOR_CODE, 3)
                        # Draw area between points
                        POINTS = np.array([[anchor + VERTEBRA.a1], [anchor + VERTEBRA.m1], 
                                [anchor + VERTEBRA.p1], [anchor + VERTEBRA.p2],
                                [anchor + VERTEBRA.m2], [anchor + VERTEBRA.a2]
                                ])
                        POINTS = POINTS.reshape((-1,1,2))
                        overlay = result.copy()
                        cv2.fillPoly(overlay, [POINTS], COLOR_CODE)

                        alpha = 0.4
                        result = cv2.addWeighted(overlay, alpha, result, 1 - alpha, 0)

                        cv2.circle(result, (anchor + VERTEBRA.a1), 7, COLOR_CODE, -1)
                        cv2.circle(result, (anchor + VERTEBRA.a2), 7, COLOR_CODE, -1)
                        cv2.circle(result, (anchor + VERTEBRA.m1), 7, COLOR_CODE, -1)
                        cv2.circle(result, (anchor + VERTEBRA.m2), 7, COLOR_CODE, -1)
                        cv2.circle(result, (anchor + VERTEBRA.p1), 7, COLOR_CODE, -1)
                        cv2.circle(result, (anchor + VERTEBRA.p2), 7, COLOR_CODE, -1)
                        cv2.putText(result, ("Ha: {} mm".format(round(VERTEBRA.ha*0.15,1))), (position[0]+move_x, position[1]-70), cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, COLOR_CODE, 6)   
                        cv2.putText(result, ("Hm: {} mm".format(round(VERTEBRA.hm*0.15,1))), (position[0]+move_x, position[1]-25), cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, COLOR_CODE, 6)
                        cv2.putText(result, ("Hp: {} mm".format(round(VERTEBRA.hp*0.15,1))), (position[0]+move_x, position[1]+20), cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, COLOR_CODE, 6)
                        cv2.putText(result, ("Loss: {}%".format(round(VERTEBRA.l*100,1))), (position[0]+move_x, position[1]+65), cv2.FONT_HERSHEY_SIMPLEX, FONT_SCALE, COLOR_CODE, 6)
            self.fracture = result
            
            self.workflow = np.array([self.imageRGB, 
                                      self.imageCLAHERGB, 
                                      self.outputDetection, 
                                      cv2.cvtColor(self.outputSegmentation[0],cv2.COLOR_GRAY2RGB),
                                      cv2.cvtColor(self.outputSegmentation[1],cv2.COLOR_GRAY2RGB),
                                      self.outputMeasurement, 
                                      self.output,
                                      self.fracture])