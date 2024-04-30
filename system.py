import pydicom as dicom 
import matplotlib.pylab as plt 

image_path = './sample.dcm'
ds = dicom.dcmread(image_path)

plt.imshow(ds.pixel_array)