import os
import pydicom as dicom 
import matplotlib.pylab as plt 

path_dcm = "./sample.dcm"
image_data = dicom.dcmread(os.path.join(path_dcm))
image = image_data.pixel_array
image = 255-(image / 4096) * 255