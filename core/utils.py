import numpy as np

# helpers
# =======
def parseQForm(qform=None, affine=None, offset=None):
	if qform == None and affine == None and offset == None:
		qform = np.eye(4)
	if affine == None:
		affine = qform[:3, :3]
	if offset == None:
		offset = qform[:3, 3:]
	return affine, offset

def points(component, qform=None, affine=None, offset=None):
	affine, offset = parseQForm(qform, affine, offset)
	return np.array(map(lambda ijk: ras(ijk, qform, affine, offset), component))

def add(volume, points, index=1, qform=None, affine=None, offset=None):
	affine, offset = parseQForm(qform, affine, offset)
	affine_I = np.asmatrix(affine).I
	for ras in points:
		ijk = affine_I * (np.matrix(ras).T - offset)
		volume[tuple(np.squeeze(np.asarray(np.rint(ijk), dtype=np.int)))] = index
	return volume

        
# IJK-RAS conversion
# ==================
def ras(ijk, qform=None, affine=None, offset=None):
	affine, offset = parseQForm(qform, affine, offset)
	ras = affine * np.matrix(ijk).T + offset
	return tuple(ras.T.tolist()[0])

def ijk(ras, qform=None, affine=None, offset=None):
	affine, offset = parseQForm(qform, affine, offset)
	ijk = np.asmatrx(affine).I * (np.matrix(ras).T - offset)
	return tuple(ijk.T.tolist()[0])
