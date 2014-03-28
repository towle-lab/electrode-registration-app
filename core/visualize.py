from mayavi import mlab
import numpy as np

# visualize
# =========
def isosurface(volume, lattice=None, **kwargs):
	if lattice == None:
		return mlab.contour3d(volume, **kwargs)
	xx, yy, zz = lattice
	return mlab.contour3d(xx, yy, zz, volume, **kwargs)
	
def mesh(vertices, faces, **kwargs):
	xx, yy, zz = vertices
	return mlab.triangular_mesh(xx, yy, zz, faces, **kwargs)

def line(point0, point1, **kwargs):
	xx, yy, zz = np.asarray([point0, point1]).T
	return mlab.plot3d(xx, yy, zz, **kwargs)

def dots(points, **kwargs):
	xx, yy, zz = np.asarray(points).T
	return mlab.points3d(xx, yy, zz, **kwargs)

def clear():
        return mlab.clf()
