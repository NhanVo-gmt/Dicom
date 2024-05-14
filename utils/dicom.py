import os
import pydicom as dicom
from utils import img


def read(path_dcm):
    return dicom.dcmread(os.path.join(path_dcm))

def convertToGrayPixelArray(pixel_array):
    if pixel_array.mean() < 4096 / 2:
        return (pixel_array / 4096) * 255
    else :
        return 1 - (pixel_array / 4096) * 255
    
class DICOM:
    def __init__(self, path_dcm, path_save):
        self.path_dcm = path_dcm
        self.path_save = path_save

    def process(self):
        image_data = read(self.path_dcm)
        self.image = convertToGrayPixelArray(image_data.pixel_array)
        img.saveImageFile(self.path_save, self.image)

        


