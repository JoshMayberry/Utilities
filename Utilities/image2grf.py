from PIL import Image
import re
import numpy as np

def image2grf(fileSource, fileDestination, scale, position):
	"""Converts any image to a .GRF file for use with zebra printers."""

	#Open the image
	image = Image.open(fileSource)
	image = image.convert("1") #Ensure that it is black and white image

	#Resize image to desired size
	size = (scale, scale)
	image.thumbnail(size, Image.ANTIALIAS)

	#Convert image to binary array
	bitmap = np.asarray(image, dtype = 'int')
	bitmap = np.asarray(bitmap, dtype = 'str').tolist()

	#Convert binary array to binary string
	binaryString = ""
	for row in bitmap:
		#Join the row to the string
		row = "".join(row)

		#Make each pixel square (for some reason it is rectangular)
		binaryString += row
		binaryString += row
		binaryString += row
		binaryString += row

	#Convert binary string to hex string
	hexString = re.sub("0","F",binaryString)
	hexString = re.sub("1","0",hexString)

	#Calculate bytes per row and total bytes
	bytesPerRow = len(bitmap[0]) / 2 
	totalBytes = bytesPerRow * len(bitmap) * 4 #0.5 for each line piece in a line

	#Save GRF
	fileName = re.findall(".*[\\\\/](.*?)\.", fileSource)[0]
	fileHandle = open(fileDestination + "/" + fileName + ".grf", "w")

	data = "~DGimage," + str(totalBytes) + "," + str(bytesPerRow) + "," + hexString
	fileHandle.write(data)

	data = "\n\n^XA\n^FO20,20^XGR:SAMPLE.GRF,1,1^FS\n^XZ"
	fileHandle.write(data)

	fileHandle.close()

if __name__ == '__main__':
	image2grf(r"test.bmp", r"", 100, (20, 20))
