from ctypes import *

import numpy as np
import os
import cv2

os.system('go build -o pigo.so -buildmode=c-shared pigo.go')
pigo = cdll.LoadLibrary('./pigo.so')

MAX_NDETS = 2048

# define class GoPixelSlice to map to:
# C type struct { void *data; GoInt len; GoInt cap; }
class GoPixelSlice(Structure):
	_fields_ = [
		("pixels", POINTER(c_ubyte)), ("len", c_longlong), ("cap", c_longlong),
	]

# Obtain the camera pixels and transfer them to Go through Ctypes.
def process_frame(pixs):
	dets = np.zeros(3 * MAX_NDETS, dtype=np.float32)
	pixels = cast((c_ubyte * len(pixs))(*pixs), POINTER(c_ubyte))

	# call FindFaces
	faces = GoPixelSlice(pixels, len(pixs), len(pixs))
	pigo.FindFaces.argtypes = [GoPixelSlice]
	pigo.FindFaces.restype = c_void_p

	# Call the exported FindFaces function from Go.
	ndets = pigo.FindFaces(faces)
	data_pointer = cast(ndets, POINTER((c_longlong * 3) * MAX_NDETS))

	if data_pointer :
		buffarr = ((c_longlong * 3) * MAX_NDETS).from_address(addressof(data_pointer.contents))
		res = np.ndarray(buffer=buffarr, dtype=c_longlong, shape=(3,3))

		# The first value of the buffer aray represents the buffer length.
		dets_len = res[0][0]
		res = np.delete(res, 0, 0) # delete the first element from the array
		dets = list(res.reshape(-1, 3))[0:dets_len]

		return dets


# initialize the camera
width, height = 640, 480
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

while(True):
	ret, frame = cap.read()
	pixs = np.ascontiguousarray(frame[:, :, 1]).flatten()

	# We need to make sure that the whole frame size is transfered over Go, 
	# otherwise we might getting an index out of range panic error.
	if len(pixs) == width*height:
		dets = process_frame(pixs) # pixs needs to be np.uint8 array
		if dets is not None:
			for det in dets:
				mask = np.zeros((height, width, 3), dtype=np.uint8)
				mask = cv2.circle(mask, (int(det[1]), int(det[0])), int(det[2]/2.0), (255, 255, 255), -1)
				frame = np.where(mask!=np.array([255, 255, 255]), frame, cv2.blur(frame, (30, 30), 0))

	cv2.imshow('Faceblur demo', frame)

	if cv2.waitKey(5) & 0xFF == ord('q'):
		break

cap.release()
cv2.destroyAllWindows()