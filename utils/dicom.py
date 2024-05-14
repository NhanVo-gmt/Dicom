import os
import pydicom as dicom 

def read(path_dcm):
    return dicom.dcmread(os.path.join(path_dcm))

def convertToGrayPixelArray(pixel_array):
    if pixel_array.mean() < 4096 / 2:
        return (pixel_array / 4096) * 255
    else :
        return 1 - (pixel_array / 4096) * 255




