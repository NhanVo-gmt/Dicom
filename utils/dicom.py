import os
import pydicom as dicom
import numpy as np
from utils import img
from PIL import Image

def read(path_dcm):
    return dicom.dcmread(os.path.join(path_dcm))

def convertToGrayPixelArray(pixel_array):
    if pixel_array.mean() < 4096 / 2:
        return convertToJPGFormat(pixel_array)
    else :
        return 1 - convertToJPGFormat(pixel_array)
    
def convertToJPGFormat(pixel_array):
    return (np.maximum(pixel_array,0)/pixel_array.max())*255 # float pixels
    
class DICOM:
    def __init__(self, path_dcm, path_save):
        self.path_dcm = path_dcm
        self.path_save = path_save

    def process(self):
        self.dcm = read(self.path_dcm)
        pixel_array = self.dcm.pixel_array.astype(float) 
        rescaled_image = convertToGrayPixelArray(pixel_array) # Convert to gray scale and JPG format

        final_image = np.uint8(rescaled_image) # integer pixels
        final_image = Image.fromarray(final_image)
        final_image.save(self.path_save)

        self.image = final_image

        


