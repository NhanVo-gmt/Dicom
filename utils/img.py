import cv2 

def saveImageFile(save_path, pixel_array):
    cv2.imwrite(save_path, pixel_array)