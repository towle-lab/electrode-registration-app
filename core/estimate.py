import numpy as np
from segment import neighbors

# TODO add ransac registration method
#from ransac.ransac import run_ransac
#from ransac import plane_fitting


# normal estimation
# =================

# principal axis
# --------------
def skew_symmetric_matrix(v):
	x, y, z = v
	return np.matrix([
		[0., -z, y],
		[z, 0., -x],
		[-y, x, 0.]
		])

def inertia_matrix(points):
	c = centroid(points)
	I = np.matrix(np.zeros((3, 3)))
	for ras in points:
		s = skew_symmetric_matrix(ras - c)
		I -= s.dot(s)
	return I

def principal_axis(I):
	w, v = np.linalg.eigh(I)
	n = max(zip(w, map(lambda i: v[:,i], range(3))), key=lambda x: x[0])[1]
	return np.asarray(n.T)[0]

# plane fitting
# -------------
def fit_plane(points):
	m = np.hstack([points, np.ones((len(points), 1))])
	v = np.linalg.svd(np.asmatrix(m))[-1].T
	n0 = np.squeeze(np.asarray(v[:3, 3:]))
	# n1 = np.squeeze(np.asarray(v[:3, 2:3]))
	# nn0, nn1 = map(lambda n: n / np.linalg.norm(n), (n0, n1))
	# return np.squeeze(np.asarray(nn0)), np.squeeze(np.asarray(nn1))
        return np.squeeze(np.asarray(n0 / np.linalg.norm(n0)))

# RANSAC plane finding
# --------------------
# def hollow(component):
# 	# TODO use more efficient method
# 	ui, uj, uk = np.max(component, axis=0) + 1
# 	li, lj, lk = np.min(component, axis=0) - 1

# 	hollow_component = list(component)
# 	for ijk in component:
# 		ns = filter(lambda (i, j, k): li<=i<ui and lj<=j<uj and lk<=k<uk, neighbors(ijk))
# 		for uvw in ns:
# 			if uvw not in component:
# 				break
# 		else:
# 			hollow_component.remove(ijk)
#         return hollow_component
                        
# def ransac_find_plane(points, goal_inliers=None, tolerance=0.01, max_iterations=64):
#         if goal_inliers == None:
#                 goal_inliers = len(points) * 0.4
# 	best_model, best = run_ransac(points, plane_fitting.estimate, lambda m, xyz: plane_fitting.is_inlier(m, xyz, tolerance), 3, goal_inliers, max_iterations)
# 	return best_model[:3] / np.linalg.norm(best_model[:3]), best

# centroid estimation
# ===================
def centroid(points):
	return points.sum(axis=0) * 1. / len(points)
