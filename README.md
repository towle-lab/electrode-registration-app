electrode-registration-app
==========================

a GUI application for registering ECoG electrodes onto pre-implant dura surface.


screenshot
----------
![screenshot](https://raw.github.com/towle-lab/electrode-registration-app/master/screenshot.register+label.png)


dependency
----------
- [`VTK`](http://www.vtk.org/), on Ubuntu, you can install it via `apt`: `$ sudo apt-get install python-vtk`. 
- [`Qt`](http://qt-project.org/)
- mayavi
- numpy, scipy
- PySide
- pynifti
- ansicolors

You can install the required python packages via `$ pip install -r requirements.txt`


usage
-----
`$ python -m app.app`


license
-------
The software is licensed under GPLv2 for **non-commercial** usage. Please contact the authors if you are interested in commercial license.


authors
-------
Zhongtian (Falcon) Dai