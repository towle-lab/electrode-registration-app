import numpy as np
import nifti
import re

# file IO
# =======
def _fread3(fobj):
    """Read a 3-byte int from an open binary file object

    Parameters
    ----------
    fobj : file
        File descriptor

    Returns
    -------
    n : int
        A 3 byte int
    """
    b1, b2, b3 = np.fromfile(fobj, ">u1", 3)
    return (b1 << 16) + (b2 << 8) + b3

def _fread3_many(fobj, n):
    """Read 3-byte ints from an open binary file object.

    Parameters
    ----------
    fobj : file
        File descriptor

    Returns
    -------
    out : 1D array
        An array of 3 byte int
    """
    b1, b2, b3 = np.fromfile(fobj, ">u1", 3 * n).reshape(-1,
                                                    3).astype(np.int).T
    return (b1 << 16) + (b2 << 8) + b3

def read_geometry(fp):
    """Read a triangular format Freesurfer surface mesh.

    Parameters
    ----------
    fp : str
        Path to surface file

    Returns
    -------
    coords : numpy array
        nvtx x 3 array of vertex (x, y, z) coordinates
    faces : numpy array
        nfaces x 3 array of defining mesh triangles
    """
    magic = _fread3(fp)
    if magic == 16777215:  # Quad file
        nvert = _fread3(fp)
        nquad = _fread3(fp)
        coords = np.fromfile(fp, ">i2", nvert * 3).astype(np.float)
        coords = coords.reshape(-1, 3) / 100.0
        quads = _fread3_many(fp, nquad * 4)
        quads = quads.reshape(nquad, 4)
        #
        #   Face splitting follows
        #
        faces = np.zeros((2 * nquad, 3), dtype=np.int)
        nface = 0
        for quad in quads:
            if (quad[0] % 2) == 0:
                faces[nface] = quad[0], quad[1], quad[3]
                nface += 1
                faces[nface] = quad[2], quad[3], quad[1]
                nface += 1
            else:
                faces[nface] = quad[0], quad[1], quad[2]
                nface += 1
                faces[nface] = quad[0], quad[2], quad[3]
                nface += 1

    elif magic == 16777214:  # Triangle file
        create_stamp = fp.readline()
        fp.readline()
        vnum = np.fromfile(fp, ">i4", 1)[0]
        fnum = np.fromfile(fp, ">i4", 1)[0]
        coords = np.fromfile(fp, ">f4", vnum * 3).reshape(vnum, 3)
        faces = np.fromfile(fp, ">i4", fnum * 3).reshape(fnum, 3)
    else:
        raise ValueError("File does not appear to be a Freesurfer surface")

    coords = coords.astype(np.float)  # XXX: due to mayavi bug on mac 32bits
    return coords, faces

def read_vol_geom(fp):
    # ignore 4 lines at the beginning
    fp.readline()
    fp.readline()
    fp.readline()
    fp.readline()
    
    # local to world transform
    ras2xyz = np.zeros((3, 3))

    ras2xyz[0] = map(float, re.findall(r'^xras\s+=\s+(.+)\s+(.+)\s+(.+)', fp.readline())[0])
    ras2xyz[1] = map(float, re.findall(r'^yras\s+=\s+(.+)\s+(.+)\s+(.+)', fp.readline())[0])
    ras2xyz[2] = map(float, re.findall(r'^zras\s+=\s+(.+)\s+(.+)\s+(.+)', fp.readline())[0])

    c = np.array(map(float, re.findall(r'^cras\s+=\s+(.+)\s+(.+)\s+(.+)', fp.readline())[0]))

    return ras2xyz, c

def read_surf(fp):
    if isinstance(fp, basestring):
        fp = open(fp, 'rb')
    with fp:
        vs, fs = read_geometry(fp)
        ras2xyz, c = read_vol_geom(fp)
        return vs, fs, ras2xyz, c

def read_nifti(fp):
    return nifti.NiftiImage(fp)
