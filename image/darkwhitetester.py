import cv2
import os
import numpy as np

image_path = "./image/dark.png"

im16 = cv2.imread(image_path)
ratio = np.amax(im16) / 256
img8 = (im16 / ratio).astype('uint8')

gray = cv2.cvtColor(img8, cv2.COLOR_BGR2GRAY)

if (cv2.mean(gray)[0] < 255/2):
    print("black")
else:
    print("white")
