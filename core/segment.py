import numpy as np
from Queue import deque
from scipy import ndimage

# segmentation
# ============
def threshold(volume, low):
	return np.select([volume>low], [volume], 0)

def neighbors(ijk):
	ns = []
	for d in [-1, 1]:
		for i in xrange(3):
			t = list(ijk)
			t[i] += d
			ns.append(tuple(t))
	return ns

def component(ijk, volume):
	c = deque()
	o = deque([ijk])
	bi, bj, bk = volume.shape
	while len(o) != 0:
		p = o.popleft()
		if p not in c and volume[p] > 0:
			ns = filter(lambda (i, j, k): 0<=i<bi and 0<=j<bj and 0<=k<bk, neighbors(p))
			o += filter(lambda n: n not in o, ns)
			c.append(p)
	return c

def all_components_iter(volume):
	nzs = volume.nonzero()
	cpis = {}
	for i in xrange(len(nzs[0])):
		cpis[(nzs[0][i], nzs[1][i], nzs[2][i])] = None
	
	ncp = 0
	n = 0
	o = (nzs[0][0], nzs[1][0], nzs[2][0])
	while n < len(nzs[0]): 
		c = component(o, volume)
		cc = []
		n += len(c)
		for voxel in c:
			cpis[voxel] = ncp
			cc.append(voxel)
		yield cc

		ncp += 1
		# look for a voxel not yet assigned a component index
		for o in cpis:
			if cpis[o] == None:
				break

def all_components(volume):
        labels, n = ndimage.label(volume)
        print 'segmented %d connected componenets' % n
        for s in ndimage.find_objects(labels):
                yield volume[s]

# filtering
# ---------
def good_size(points, lower, upper):
	return lower < len(points) < upper

def good_extent(points, lower, upper):
	return lower < points.ptp(axis=0).prod() < upper
