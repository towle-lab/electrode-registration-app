import numpy as np

# registration
# ============
def naive_nearest_point(points, xyz):
	min_d = None
	min_p = None
	min_i = None
	for i, p in enumerate(points):
		nd = np.linalg.norm(p - xyz)
		if nd < min_d or None == min_d:
			min_d = nd
			min_i = i
			min_p = p

	return min_i, min_p
        
def line_surf_intersection(xyz, n, points, intersection_threshold=3): 
	'''@param n unit vector along the line'''
	s = np.ndarray((len(points),))
	# d = np.array((len(points),))
	intersects = []
	for i, p in enumerate(points):
		pp = p - xyz
		s[i] = n.dot(pp)
		d = np.linalg.norm(pp - s[i] * n)
		if d < intersection_threshold:
			intersects.append((i, d, s[i], p))
	intersects.sort(key=lambda x: np.abs(x[2]))
	# FIXME the case where the line does not intersect with the dura

	# print intersects[:20], intersects[0]
	# print intersects[0]
	# use the sign of s[i] to separate out two groups
	# FIXME this naive approach breaks for electrodes lying on the outside
	# nearer_group = filter(lambda x: np.sign(x[2]) == np.sign(intersects[0][2]), intersects)
	# nearer_group = filter(lambda x: np.sign(x[2]) == np.sign(intersects[0][2]), intersects)
	mid = np.mean(map(lambda x: np.abs(x[2]), intersects))
	nearer_group = filter(lambda x: np.abs(x[2]) < mid, intersects)
	nearer_group.sort(key=lambda x: np.abs(x[1]))
	# print nearer_group[:10]

	if len(nearer_group) == 0:
		return 0, np.array([0, 0, 0])
	return nearer_group[0][0], nearer_group[0][-1]
