import numpy as np

def random_unit_vec():
	# uniform distribution over spherical surface gives pdf_theta ~ sin(theta)
	y = np.random.rand()
	x = np.sqrt(1. - 4. * (y-0.5)**2)

	return np.asmatrix(spherical2cartesian(1., x, np.random.rand()*2.*np.pi))

def cylinder(n, r, t, volshape=(64, 64, 64), voxDim=(1., 1., 1.), c=None):
	"""
	param r: radius in mm
	param t: thickness in mm
	"""
	if c == None:
		c = np.array(map(lambda x: x/2., np.asarray(volshape)))

	vol = np.ndarray(volshape, dtype=np.uint8)
	for uvw, val in np.ndenumerate(vol):
		p = np.transpose([(np.asarray(uvw) - c) * voxDim])
		pn = n.dot(p)[0,0] * n.T
		pp = p - pn
		if pp.T.dot(pp)[0,0] < r**2 and pn.T.dot(pn)[0,0] < (t/2.)**2:
			vol[uvw] = 1.
		else:
			vol[uvw] = 0.
	return vol

def spherical2cartesian(r, theta, phi):
	z = r * np.cos(theta)
	x = r * np.sin(theta) * np.cos(phi)
	y = r * np.sin(theta) * np.sin(phi)
	return x, y, z

def add_outliers(volume, p, fill=1):
        for uvw, val in np.ndenumerate(volume):
                if val == 0 and np.random.rand() < p: 
                        volume[uvw] = fill
        return volume

def remove_inliers(volume, p, fill=0):
        for uvw, val in np.ndenumerate(volume):
                if val != 0 and np.random.rand() < p:
                        volume[uvw] = fill
        return volume
        
if __name__ == '__main__':
	from core import segment, utils, estimate, visualize
        
        n = random_unit_vec()
        #n = np.asarray([[0., 0., 1.]])
        vres = (16, 20, 18)
        vdim = (0.5, 0.7, 0.5)
        
        xx, yy, zz = np.asarray(np.mgrid[:vres[0], :vres[1], :vres[2]], dtype=np.float)
        xx *= vdim[0]
        yy *= vdim[1]
        zz *= vdim[2]
	volume = cylinder(n, 3, 2, volshape=vres, voxDim=vdim)
        
        add_outliers(volume, 0.2)
        remove_inliers(volume, 0.1)

        cs = segment.all_components(volume)
        cs.sort(key=lambda c: len(c))
        c = cs[-1]

        vol = np.zeros(vres)
        utils.add(vol, utils.points(c))
	visualize.isosurface(vol, (xx, yy, zz), contours=[0.5])
        
        hc = estimate.hollow(c)
        points = utils.points(c, np.diag(vdim + (1.,)))
        pa = estimate.principal_axis(estimate.inertia_matrix(points))
        bfp = estimate.fit_plane(points)
        rpf, bf = estimate.ransac_find_plane(utils.points(hc, np.diag(vdim + (1.,))), len(hc) * 0.4, 0.01, 100)
        
        print 'ground truth:', n
        print 'principal axis:', pa, np.abs(n.dot(pa.T)[0,0])
        print 'best fitting planes:', bfp, np.abs(n.dot(bfp.T)[0,0])
        print 'RANSAC plane finding:', rpf, np.abs(n.dot(rpf.T)[0,0]), bf*1./len(hc)
