# description: GUI application to interactively segment and register 
# ECoG electrodes with post-implant CT and pre-implant MRI
#
# Copyright (C) 2014 Zhongtian Dai
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


import sys, os, traceback, json, csv
from os import path

os.environ['ETS_TOOLKIT'] = 'qt4'

from pyface.qt import QtGui, QtCore
from pyface.qt.QtCore import Qt

#from PySide.QtGui import QApplication, QMainWindow
from ui.mainwindow import Ui_MainWindow
from ui.open_files_dialog import Ui_Dialog as Ui_OpenFilesDialog
from ui.export_dialog import Ui_Dialog as Ui_ExportDialog

from traits.api import HasTraits, Instance, on_trait_change, Int, Dict
from traitsui.api import View, Item
from mayavi.core.ui.api import MayaviScene, MlabSceneModel, SceneEditor
from tvtk.api import tvtk
import mayavi
from mayavi.modules.api import Outline, Text3D, Glyph

from core import io, estimate, register
import numpy as np
from scipy import ndimage, spatial
from sklearn import cluster

from helper import *


class Visualization(HasTraits):
    scene = Instance(MlabSceneModel, ())

    @on_trait_change('scene.activated')
    def update_plot(self):
        # This function is called when the view is opened. We don't
        # populate the scene when the view is not yet open, as some
        # VTK features require a GLContext.

        # We can do normal mlab calls on the embedded scene.
        #self.scene.mlab.test_points3d()
        # maroon background color
        self.scene.background = (0.5, 0, 0)
        #import pdb; pdb.set_trace()
        debug('mayavi initialized')

    # the layout of the dialog created
    view = View(Item('scene', editor=SceneEditor(scene_class=MayaviScene),
                     height=250, width=300, show_label=False),
                resizable=True # We need this to resize with the parent widget
                )

class MayaviQWidget(QtGui.QWidget):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        layout = QtGui.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)
        self.visualization = Visualization()

        # If you want to debug, beware that you need to remove the Qt
        # input hook.
        #QtCore.pyqtRemoveInputHook()
        #import pdb ; pdb.set_trace()
        #QtCore.pyqtRestoreInputHook()

        # The edit_traits call will generate the widget to embed.
        self.ui = self.visualization.edit_traits(parent=self,
                                                 kind='subpanel').control
        layout.addWidget(self.ui)
        self.ui.setParent(self)


class ComponentItem(object):
    prop_map = ['name', 'grid_label', 'grid_id', 'channel_number']
    register_method_color = {}
    editable = {
        'grid_label': {
            'display': 'grid label', 
            'set': lambda x: x.upper(), 
        },
        'grid_id': {
            'display': 'grid id',
            'set': lambda x: int(x) if x.strip().isdigit() else None, 
        },
        'channel_number': {
            'display': 'channel',
            'set': lambda x: int(x) if x.strip().isdigit() else None, 
        },
    }
    grid_color_lut = map(lambda rgb: tuple(map(lambda x: x / 255., rgb)), json.load(open('app/brewer-qualitative.strong.12.json')))
    grid_labels = []

    def __init__(self, name, voxel, transform, 
                 source, surface, outline=None, text=None, 
                 is_electrode=True,
                 register_method=None, register_position=None, register_dura_vertex_id=None,
                 channel_number=None, grid_label=None, grid_id=None,
                 note=None,
                 parent=None):
        self.name = name
        self.voxel = voxel
        self.transform = transform
        self.source = source
        self.surface = surface
        self.outline = outline
        self.text = text
        self.is_electrode = is_electrode
        self._channel_number = channel_number
        self._grid_label = grid_label
        self._grid_id = grid_id
        self.note = note
        self.register_method = register_method
        self.register_position = register_position or self.centroid.reshape(-1)
        self.register_dura_vertex_id = register_dura_vertex_id
        self.dot = None
        self.rod = None

        # for tree structure
        self.parent = parent
        self.children = []
    
    @property
    def points(self):
        ijks = np.asarray(np.nonzero(self.voxel))
        return self.transform[:3, :3].dot(ijks) + self.transform[:3, 3:]
    
    @property
    def centroid(self):
        c = ndimage.measurements.center_of_mass(self.voxel)
        return self.transform[:3, :3].dot(np.reshape(c, (3, -1))) + self.transform[:3, 3:]

    @property
    def grid_label(self):
        return self._grid_label

    @grid_label.setter
    def grid_label(self, value):
        self._grid_label = value.upper().strip()

        if len(self._grid_label) == 0:
            # TODO use some gray default color (BW -> colored)
            self.surface.actor.mapper.scalar_visibility = True            
            return 

        if self.text and self.grid_id:
            self.text.text = '    %s %d' % (self.grid_label, self.grid_id)

        color = ComponentItem.grid_color_lut[0]
        n_color = len(ComponentItem.grid_color_lut)
        if self._grid_label in ComponentItem.grid_labels:
            grid_index = ComponentItem.grid_labels.index(self._grid_label)
            color = ComponentItem.grid_color_lut[grid_index % n_color]
        else:
            ComponentItem.grid_labels.append(self._grid_label)
            color = ComponentItem.grid_color_lut[(-1 % len(ComponentItem.grid_labels)) % n_color]

        #import pdb; pdb.set_trace()
        self.surface.actor.mapper.scalar_visibility = False
        self.surface.actor.property.diffuse_color = color

    @property
    def channel_number(self):
        return self._channel_number

    @channel_number.setter
    def channel_number(self, value):
        if value.strip().isdigit():
            self._channel_number = int(value)
        else:
            self._channel_number = None

    @property
    def grid_id(self):
        return self._grid_id

    @grid_id.setter
    def grid_id(self, value):
        if value.strip().isdigit():
            self._grid_id = int(value)
            if self.text and self.grid_label:
                self.text.text = '      %s %d' % (self.grid_label, self.grid_id)
        else:
            self._grid_id = None
            #self.text.text = ''

    @property
    def id(self):
        return (self.grid_label, self.grid_id)

    def appendChild(self, component):
        self.children.append(component)
        component.parent = self

    def child(self, row):
        if row < len(self.children):
            return self.children[row]
        return None

    def childCount(self):
        return len(self.children)

    def row(self):
        if self.parent:
            return self.parent.children.index(self)
        return 0

    def columnCount(self):
        return len(ComponentItem.prop_map)

    def data(self, column):
        #debug('item.data', getattr(self, ComponentItem.prop_map[column]))
        return getattr(self, ComponentItem.prop_map[column])


class PointComponentItem(ComponentItem):
    def __init__(self, name, xyz,
                 source, surface, outline=None, text=None, 
                 is_electrode=True,
                 register_method=None, register_position=None, register_dura_vertex_id=None,
                 channel_number=None, grid_label=None, grid_id=None,
                 note=None,
                 parent=None):
        self.name = name
        self.xyz = xyz
        self.source = source
        self.surface = surface
        self.outline = outline
        self.text = text
        self.is_electrode = is_electrode
        self._channel_number = channel_number
        self._grid_label = grid_label
        self._grid_id = grid_id
        self.note = note
        self.register_method = register_method
        self.register_position = register_position or self.centroid.reshape(-1)
        self.register_dura_vertex_id = register_dura_vertex_id
        self.dot = None
        self.rod = None

        # for tree structure
        self.parent = parent
        self.children = []

    @property
    def centroid(self):
        return np.asarray([self.xyz]).T

    @property
    def points(self):
        return self.centroid


class ComponentModel(QtCore.QAbstractItemModel):
    def __init__(self):
        super(ComponentModel, self).__init__(None)
        self.root_item = ComponentItem(None, None, None, None, None, register_position=(0,0,0), is_electrode=False)
        
    def index(self, row, column, parent=QtCore.QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()
        
        parent_item = self.root_item
        if parent.isValid():
            parent_item = parent.internalPointer()
        
        child_item = parent_item.child(row)
        if child_item:
            index = self.createIndex(row, column, child_item)
            child_item.index = index
            return index
        else:
            return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()
            
        child_item = index.internalPointer()
        parent_item = child_item.parent

        if parent_item == None or parent_item == self.root_item:
            return QtCore.QModelIndex()
        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0
        parent_item = self.root_item
        if parent.isValid():
            parent_item = parent.internalPointer()
        return parent_item.childCount()

    def columnCount(self, parent):
        return len(ComponentItem.prop_map)

    def data(self, index, role):
        #debug('model.data', index, role)
        if not index.isValid():
            return None

        item = index.internalPointer()
        if role == Qt.DisplayRole:
            return item.data(index.column())
        if role == Qt.ForegroundRole and not item.is_electrode:
            return QtGui.QBrush(QtGui.QColor(128, 128, 128))

        return None

    def headerData(self, section, orientation, role):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            attr = ComponentItem.prop_map[section]
            if attr in ComponentItem.editable:
                return ComponentItem.editable[attr]['display']
            else:
                return attr
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled

        default_flags = super(ComponentModel, self).flags(index)
        if ComponentItem.prop_map[index.column()] in ComponentItem.editable:
            return default_flags | Qt.ItemIsEditable | Qt.ItemIsEnabled

        return default_flags | Qt.ItemIsSelectable | Qt.ItemIsEnabled

    def setData(self, index, value, role):
        if index.isValid() and role == Qt.EditRole:
            prop = ComponentItem.prop_map[index.column()]
            setattr(index.internalPointer(), prop, value)
            self.dataChanged.emit(index, index)
            return True
        return False

    def itemFromIndex(self, index):
        if not index.isValid():
            return self.root_item
        
        return index.internalPointer()
        
    def hasChildren(self, index):
        item = self.root_item
        if index.isValid():
            item = index.internalPointer()

        return item.childCount() > 0


class FlattenTreeProxyModel(QtGui.QAbstractProxyModel):
    '''implements a pre-order traversal of a tree-like model to 
    flatten the index for a list-like model'''

    def __init__(self):
        super(FlattenTreeProxyModel, self).__init__()
        self.list_to_tree = {}
        self.tree_to_list = {}
    
    def build_index_maps(self):
        self.layoutAboutToBeChanged.emit()
        self.list_to_tree = {}
        self.tree_to_list = {}

        sm = self.sourceModel()
        o = [QtCore.QModelIndex()]
        idx = 0
        while len(o) > 0:
            x = o.pop()
            y = sm.itemFromIndex(x)
            if isinstance(y, ComponentItem) and y.is_electrode:
                # TODO optimize this
                tree_index_tuple = self.serialize_tree_index(x)
                self.list_to_tree[idx] = tree_index_tuple
                self.tree_to_list[tree_index_tuple] = idx
                idx += 1
            if sm.hasChildren(x):
                for r in reversed(xrange(sm.rowCount(x))):
                    o.append(sm.index(r, 0, x))

        debug('built indices')

        #debug(self.list_to_tree)
        #debug(self.tree_to_list)
        #import pdb; pdb.set_trace()
        self.layoutChanged.emit()

        
    def serialize_tree_index(self, tree_index):
        i = tree_index
        rs = []
        while i and i.isValid():
            rs.append(i.row())
            i = i.parent()
        return tuple(rs)

    def inflate_tree_index(self, rows, column):
        sm = self.sourceModel()
        rs = list(rows)
        if len(rs) == 0:
            return QtCore.QModelIndex()
        elif len(rs) == 1:
            return sm.index(rs[0], column)

        i = QtCore.QModelIndex()
        while len(rs) > 1:
            r = rs.pop()
            i = sm.index(r, 0, i)
        return sm.index(rs.pop(), column, i)

    def mapFromSource(self, source_index):
        i = self.serialize_tree_index(source_index)
        try:
            r = self.createIndex(self.tree_to_list[i], source_index.column(), source_index.internalPointer())
            #debug('from source', source_index, i, self.tree_to_list[i], r)
            return r
        except:
            return QtCore.QModelIndex()


    def mapToSource(self, proxy_index):
        try:
            r = self.inflate_tree_index(self.list_to_tree[proxy_index.row()], proxy_index.column())
            #debug('to source', proxy_index, r)
            return r
        except:
            return QtCore.QModelIndex()

    def hasChildren(self, parent):
        if not parent.isValid():
            return True
        return False


    def index(self, row, column, parent):
        if row < 0 or column < 0:
            return QtCore.QModelIndex()

        r = self.inflate_tree_index(self.list_to_tree[row], column)
        if r.isValid():
            return self.mapFromSource(r)
 
        return QtCore.QModelIndex()


    def parent(self, index):
        if index.isValid():
            return QtCore.QModelIndex()
        return None


    def rowCount(self, parent=QtCore.QModelIndex()):
        if not parent.isValid():
            return len(self.list_to_tree)
        return 0

    def columnCount(self, index):
        return self.sourceModel().columnCount(index)

    def headerData(self, section, orientation, role):
        return self.sourceModel().headerData(section, orientation, role)


@QtCore.Slot()
def open_project():
    fn, t = QtGui.QFileDialog.getOpenFileName(caption='Open an existing project...', filter='Project file (*.prj);; Any file (*.*)')

@QtCore.Slot()
def save_project():
    fn, t = QtGui.QFileDialog.getSaveFileName(caption='Save a project...', dir='untitled.prj')
    

class Application(object):
    # data source
    ct = None
    ct_path = '/home/vtowle/source/sample/emily/ct.hdr'
    dura = None
    dura_path = '/home/vtowle/source/sample/emily/lh.dura'
    # optional
    pial = None
    pial_path = None
    
    # data
    ct_volume = None
    dura_vertices = None
    dura_faces = None
    dura_vertices_kdtree = None

    # view
    camera_pose = None
    camera_pose_history = []

    # parameters
    segment_value_threshold = 3200
    segment_distance_threshold = 25.
    segment_size_threshold = 5.

    # scene objects
    ct_fig = None
    dura_fig = None
    dura_surf = None
    pial_fig = None
    
    # processing state
    stages =  ['initial', 'data loaded', 'segmented']
    current_stage = stages[0]

    # segmented components
    components = []
    slices = []
    pickable_actors = {}

    #segment_model = QtGui.QStandardItemModel()
    segment_model = ComponentModel()
    segment_selection_model = None
    
    # UI states
    modes = ['free', 'manual add', 'manual register']
    mode = 'free'

    # local config path
    config_dir = path.expanduser(path.join('~', '.electrode_registration'))
    config_path = path.join(config_dir, 'electrode_registration.config.json')

    def __init__(self, ui, mlab, config=None):
        # load configurations 
        if not path.exists(self.config_dir):
            debug('configuration directory %s does not exist' % self.config_dir)
            os.mkdir(self.config_dir)
            debug('created configuration directory')
        elif path.exists(self.config_path):
            info('loading configurations from %s' % self.config_path)
            with open(self.config_path, 'rb') as f:
                # set up parameters from config json
                debug(json.load(f))
        
        self.mlab = mlab
        self.ui = ui
        
        # wire up the GUI
        ui.actionOpen.triggered.connect(self.open_ct_dura)
        # segment panel slider + spinbox
        ui.horizontalSlider_distance.sliderMoved.connect(lambda x: ui.doubleSpinBox_distance.setValue(x))
        ui.doubleSpinBox_distance.valueChanged.connect(lambda x: ui.horizontalSlider_distance.setValue(x))
        ui.horizontalSlider_size.sliderMoved.connect(lambda x: ui.doubleSpinBox_size.setValue(x / 10.))
        ui.doubleSpinBox_size.valueChanged.connect(lambda x: ui.horizontalSlider_size.setValue(x * 10.))
        ui.pushButton_segment.clicked.connect(self.segment)
        ui.pushButton_preview_threshold.clicked.connect(self.preview_threshold)
        ui.actionOpenPial.triggered.connect(self.open_pial)
        ui.actionHideThresholdingPreview.triggered.connect(self.hide_preview)

        # set up mlab figure
        self.fig = mlab.gcf()
        self.engine = mlab.get_engine()
    
        # edit tab
        ui.treeView_edit.setModel(self.segment_model)
        # show only the first column
        for i in xrange(1, len(ComponentItem.prop_map)):
            ui.treeView_edit.setColumnHidden(i, True)

        self.segment_selection_model = ui.treeView_edit.selectionModel()
        ui.pushButton_add.toggled.connect(self.manual_add)
        ui.pushButton_remove.clicked.connect(self.remove_segment)
        ui.pushButton_restore.clicked.connect(self.restore_segment)
        ui.pushButton_split.clicked.connect(self.split_component)

        # register tab
        self.register_model = FlattenTreeProxyModel()
        self.register_model.setSourceModel(self.segment_model)
        ui.pushButton_nearest.clicked.connect(self.do_register_nearest)
        ui.pushButton_principal.clicked.connect(self.do_register_principal_axis)
        ui.pushButton_svd.clicked.connect(self.do_register_svd)
        ui.pushButton_manual.toggled.connect(self.do_register_manual)
        ui.pushButton_unregister.clicked.connect(self.unregister)
       
        # label tab
        self.label_model = QtGui.QSortFilterProxyModel()
        self.label_model.setSourceModel(self.register_model)
        ui.pushButton_export.clicked.connect(self.export)
        ui.pushButton_assign_grid_label.clicked.connect(self.batch_assign_grid_label)

        # advanced menu
        ui.actionExport_segmentation_dataset.triggered.connect(self.export_segmentation_dataset)


    @classmethod
    def from_dict(cls, obj):
        pass
        
    def to_dict(self):
        pass

    @QtCore.Slot()
    def hide_preview(self):
        info('hide thresholding preview')
        try:
            debug('preview exists')
            self.preview_contour_surface.visible = False
            self.ui.pushButton_hide_preview.setEnabled(False)
        except AttributeError:
            warn('no existing thresholding preview')

    @QtCore.Slot()
    def open_pial(self):
        info('open pial mesh')
        fn, t = QtGui.QFileDialog.getOpenFileName(caption='Open Pial Mesh...', 
                                                  filter='Pial File (*.pial);; Any File (*)', 
                                                  options=QtGui.QFileDialog.DontUseNativeDialog)
        if fn:
            info('reading pial mesh from %s' % fn)
            try:
                self.pial = read_surface(fn)
                vs, fs, m = self.pial
                x, y, z = vs.T
                
                if self.pial_fig:
                    self.pial_fig.remove()
                    info('removed existing pial mesh')

                source = self.mlab.pipeline.triangular_mesh_source(x, y, z, fs)
                transform_filter = build_transform_filter(self.mlab, source, m)
                normal_filter = self.mlab.pipeline.poly_data_normals(transform_filter)
                normal_filter.filter.feature_angle = 80.

                surface = self.mlab.pipeline.surface(normal_filter, color=(0.8, 0.8, 0.8))
                self.pial_fig = source
                self.pial_path = fn
            except:
                err('failed to read pial')
                print_traceback()

    @QtCore.Slot()
    def open_ct_dura(self):
        dialog = QtGui.QDialog()

        # init GUI
        dialog_ui = Ui_OpenFilesDialog()
        dialog_ui.setupUi(dialog)
        if self.dura_path:
            dialog_ui.duraLineEdit.setText(self.dura_path)
        if self.ct_path:
            dialog_ui.ctLineEdit.setText(self.ct_path)

        # set up file dialogs
        ct_file_dialog = QtGui.QFileDialog()
        ct_file_dialog.setFileMode(QtGui.QFileDialog.ExistingFile)
        ct_file_dialog.setNameFilters(['NIfTI File (*.img *.hdr *.nii)', 'Any file (*)'])
        dialog_ui.ctPushButton.clicked.connect(ct_file_dialog.exec_)
        ct_file_dialog.fileSelected.connect(dialog_ui.ctLineEdit.setText)

        #dialog_ui.ctPushButton.clicked.connect(lambda : browse_file(dialog_ui.ctLineEdit, 'Open CT Volume', 'Nifti file (*.img *.hdr);; Any file (*.*)'))
        #dialog_ui.duraPushButton.clicked.connect(lambda : browse_file(dialog_ui.duraLineEdit, 'Open Dura Mesh', ''))

        dura_file_dialog = QtGui.QFileDialog()
        dura_file_dialog.setFileMode(QtGui.QFileDialog.ExistingFile)
        dura_file_dialog.setNameFilters(['Dura File (*.dura *.pial-outer-smoothed)', 'Any File (*)'])
        dialog_ui.duraPushButton.clicked.connect(dura_file_dialog.exec_)
        dura_file_dialog.fileSelected.connect(dialog_ui.duraLineEdit.setText)

        def validate():
            '''validate the CT and dura paths input'''
            if dialog_ui.ctLineEdit.text() != '' and dialog_ui.duraLineEdit.text() != '':
                dialog.accept()
            else:
                QtGui.QErrorMessage(dialog).showMessage('Both CT and dura are required.')
                err('both CT and dura paths are needed.')
        
        dialog_ui.buttonBox.accepted.connect(validate)

        # show file dialog
        if QtGui.QDialog.Accepted == dialog.exec_():
            info('read CT and dura paths')
            self.read_ct_dura(dialog_ui.ctLineEdit.text(), dialog_ui.duraLineEdit.text())

    def read_ct_dura(self, ct_path, dura_path):
        info('reading CT from %s' % ct_path)
        info('reading dura mesh from %s' % dura_path)
        try:
            try:
                del self.preview_contour_filter
                del self.preview_contour_surface
                self.ui.pushButton_hide_preview.setEnabled(False)
                debug('removed threshold preview')
            except:
                debug('no threshold preview to remove')
            
            # load CT and dura
            self.ct = io.read_nifti(ct_path)
            self.dura = read_surface(dura_path)
            
            # replace paths
            self.ct_path = ct_path
            self.dura_path = dura_path

            self.dura_vertices, self.dura_faces, mc = self.dura 
            x, y, z = self.dura_vertices.T

            self.ct_volume = self.ct.getDataArray()

            info('loaded CT')
            info('loaded dura mesh')

            # update panel parameters
            debug('updating panel parameters')
            ct_max = self.ct_volume.max()
            debug('CT maximum intensity is %d' % ct_max)
            self.ui.spinBox_threshold.setMaximum(ct_max)
            self.ui.horizontalSlider_threshold.setMaximum(ct_max)


            # set default segmentation parameters
            debug('setting default segmentation parameters')
            self.ui.spinBox_threshold.setValue(min(self.segment_value_threshold, ct_max))
            self.ui.doubleSpinBox_distance.setValue(self.segment_distance_threshold)
            self.ui.doubleSpinBox_size.setValue(self.segment_size_threshold)

            # enable panels
            self.ui.frame_segment.setEnabled(True)
            self.ui.frame_segment_config.setEnabled(True)
            self.ui.pushButton_segment.setEnabled(True)
            debug('enabled panels')
            
            # draw dura
            try:
                # remove existing CT and dura figures if any
                if self.ct_fig:
                    self.ct_fig.remove()
                    self.ct_fig = None
                    info('CT figure removed')
                if self.dura_fig:
                    self.dura_fig.remove()
                    info('removed previous dura mesh figure')
                source = self.mlab.pipeline.triangular_mesh_source(x, y, z, self.dura_faces)
                transform_filter = build_transform_filter(self.mlab, source, mc)
                normal_filter = self.mlab.pipeline.poly_data_normals(transform_filter)
                surface = self.mlab.pipeline.surface(normal_filter, color=(0.8, 0.8, 0.8), opacity=0.5)
                self.dura_fig = source
                self.dura_surf = surface
                info('drew dura mesh')
            except:
                err('failed to draw dura mesh')
                print_traceback()
        except:
            err('failed to load CT and dura mesh')
            print_traceback()

    
    def preview_threshold(self):
        mlab = self.mlab
        ct = self.ct
        threshold = self.ui.spinBox_threshold.value()
        info('preview thresholding result at %d' % threshold)
        try:
            # change the threshold level if a contour filter
            # has been created already
            self.preview_contour_filter.filter.contours = [threshold]
            self.preview_contour_surface.visible = True
        except AttributeError:
            # the contour filter is not present, create the
            # whole pipeline
            
            img = ct.getDataArray().T
            #ndimage.gaussian_filter(img, 0.5, output=img)
            source = mlab.pipeline.scalar_field(img)
            
            contour_filter = mlab.pipeline.contour(source)
            contour_filter.filter.contours = [threshold]

            transform_filter = build_transform_filter(mlab, contour_filter, ct.getSForm())

            normal_filter = mlab.pipeline.poly_data_normals(transform_filter)
            surface = mlab.pipeline.surface(normal_filter, color=(0.2, 0.9, 0.4))
            # register the contour filter to application
            self.preview_contour_filter = contour_filter
            self.preview_contour_surface = surface
            self.ct_fig = source
        info('completed CT intensity threshold preview')
        debug('enable hide preview button')
        self.ui.pushButton_hide_preview.setEnabled(True)
    

    @wrap_get_set_view
    def segment(self):
        info('segmenting CT')
        threshold = self.ui.spinBox_threshold.value()
        distance = self.ui.doubleSpinBox_distance.value()
        size = self.ui.doubleSpinBox_size.value()
        if threshold > 0. and distance >= 0. and size >= 0.:
            # sane segmentation parameters
            info('valid segmentation parameters')
            self.segment_value_threshold = threshold
            self.segment_size_threshold = size
            self.segment_distance_threshold = distance
            info('thresholding on CT intensity value at %d...' % threshold)

            ct_high = np.asarray(np.where(threshold <= self.ct.getDataArray().T, True, False), 'i1')
            #info('done thresholding on CT intensity value')
            labels = ndimage.label(ct_high)[0]
            slices = ndimage.find_objects(labels)
            info('found %d connected components' % len(slices))

            info('done thresholding CT')
            sf = self.ct.getSForm()
            dv = np.product(self.ct.getVoxDims())
            debug('vox dims %r, dv = %f' % (self.ct.getVoxDims(), dv))

            debug('building KD-tree of %d dura vertices' % len(self.dura_vertices))
            self.dura_vertices_kdtree = spatial.cKDTree(self.dura_vertices + self.dura[2][:3, 3:].T)

            info('segmenting electrodes')
            #self.component_figs = []
            #root = self.segment_model.invisibleRootItem()
            root = self.segment_model.root_item
            n = 0
            
            #view = self.get_view()

            for i, s in enumerate(slices):
                bbc0 = np.reshape(map(lambda x: max(0, x.start - 1), s), (-1, 1))
                bbc1 = np.reshape(map(lambda x: x.stop + 1, s), (-1, 1))
                bb_center = sf[:3, :3].dot(bbc0 + bbc1) / 2. + sf[:3, 3:]
                distance, index = self.dura_vertices_kdtree.query(bb_center[:, 0])
                voxel = np.asarray(np.where(labels[slice(bbc0[0], bbc1[0]), slice(bbc0[1], bbc1[1]), slice(bbc0[2], bbc1[2])] == i + 1, 1, 0), 'i1')
                size = voxel.sum() * dv
                #debug('component %d' % i)
                if self.segment_size_threshold < size and distance < self.segment_distance_threshold:
                    #debug('component %d, size %.2fmm^3, %.2fmm away from dura, bounded at %r is segmented' % (i, size, distance, s))
                    co = sf[:3, :3].dot(bbc0)
                    m = np.array(sf)
                    m[:3, 3:] += co
                    component = self.create_segment(voxel, m, 'component %d' % n)
                    #component.setEditable(False)
                    root.appendChild(component)
                    # inverse index
                    self.pickable_actors[repr(component.surface.actor.actor)] = component
                    n += 1

            info('done segmenting, selected %d out of %d connected components' % (n, len(slices)))

            #self.set_view(*view)
            
            debug('add picker callback')
            def pick_callback(picker):
                for actor in reversed(picker.actors):
                    if repr(actor) in self.pickable_actors:
                        target = self.pickable_actors[repr(actor)]
                        debug('picked %r' % target)
                        break
                else:
                    debug('no component is picked')
                    return 

                self.segment_selection_model.select(target.index, QtGui.QItemSelectionModel.Toggle)
                self.ui.treeView_edit.scrollTo(target.index)
                ridx = self.register_model.mapFromSource(target.index)
                self.ui.listView_register.scrollTo(ridx)
                self.ui.tableView_label.scrollTo(self.label_model.mapFromSource(ridx))

            # add pick callback, make picker more precise
            picker = self.fig.on_mouse_pick(pick_callback, type='cell', button='Left')
            picker.tolerance = 0.005

            debug('defining manual add + registration callback')
            def pick_manual_callback(picker):
                if self.mode == 'manual register':
                    component = self.segment_model.itemFromIndex(self.register_model.mapToSource(self.register_selection_model.selectedIndexes()[0]))
                    v = self.get_view()
                    dura_id, to_position = self.register_manual(picker.pick_position)
                    self.register_electrode(component, to_position, color=(0.7, 0.2, 0.9))
                    component.register_method = 'manual'
                    component.register_dura_vertex_id = dura_id
                    self.set_view(*v)
                elif self.mode == 'manual add':
                    v = self.get_view()
                    new_component = self.add_electrode(picker.pick_position)
                    n = self.segment_model.root_item.childCount()
                    self.segment_model.beginInsertRows(QtCore.QModelIndex(), n, n+1)

                    self.pickable_actors[repr(new_component.surface.actor.actor)] = new_component
                    self.segment_model.root_item.appendChild(new_component)

                    self.segment_model.endInsertRows()
                    self.register_model.build_index_maps()
                    self.set_view(*v)
                    self.update_component_count()
                    self.update_electrode_count()

            self.fig.on_mouse_pick(pick_manual_callback, type='cell', button='Right')

            # set up tree edit selection model
            def segment_model_selection_callback(selected, deselected):
                #import pdb; pdb.set_trace()
                for idx in selected.indexes():
                    item = self.segment_model.itemFromIndex(idx)
                    self.toggle_component_selection(item, True)
                for idx in deselected.indexes():
                    item = self.segment_model.itemFromIndex(idx)
                    self.toggle_component_selection(item, False)
                
            self.segment_selection_model.selectionChanged.connect(segment_model_selection_callback)
            
            info('edit tab enabled')
            self.ui.label_component_count.setText(str(n))
            self.ui.label_register_electrode_count.setText(str(n))
            self.ui.label_edit_electrode_count.setText(str(n))
            self.ui.tab_edit.setEnabled(True)

            info('register tab enabled')
            self.ui.tab_register.setEnabled(True)
            self.register_model.build_index_maps()
            self.ui.listView_register.setModel(self.register_model)
            self.register_selection_model = self.ui.listView_register.selectionModel()
            
            info('label tab enabled')
            self.ui.tab_label.setEnabled(True)
            self.ui.tableView_label.setModel(self.label_model)
            self.label_selection_model = self.ui.tableView_label.selectionModel()
            d = self.ui.tableView_label.itemDelegateForColumn(1)
            #import pdb; pdb.set_trace()

            # synchronize selection models
            def segment_to_other_selections(selected, deselected):
                for idx in selected.indexes():
                    ridx = self.register_model.mapFromSource(idx)
                    lidx = self.label_model.mapFromSource(ridx)
                    #debug('selected', idx, ridx, lidx)
                    self.register_selection_model.select(ridx, QtGui.QItemSelectionModel.Select | QtGui.QItemSelectionModel.Rows)
                    self.label_selection_model.select(lidx, QtGui.QItemSelectionModel.Select | QtGui.QItemSelectionModel.Rows)
                for idx in deselected.indexes():
                    ridx = self.register_model.mapFromSource(idx)
                    lidx = self.label_model.mapFromSource(ridx)
                    #debug('deselected', idx, ridx, lidx)
                    self.register_selection_model.select(ridx, QtGui.QItemSelectionModel.Deselect | QtGui.QItemSelectionModel.Rows)
                    self.label_selection_model.select(lidx, QtGui.QItemSelectionModel.Deselect | QtGui.QItemSelectionModel.Rows)


            self.segment_selection_model.selectionChanged.connect(segment_to_other_selections)
            self.segment_selection_model.selectionChanged.connect(self.update_selection_counts)

            def register_to_segment_selections(selected, deselected):
                for idx in selected.indexes():
                    sidx = self.register_model.mapToSource(idx)
                    #debug('selected', idx, sidx)
                    self.segment_selection_model.select(sidx, QtGui.QItemSelectionModel.Select)
                for idx in deselected.indexes():
                    sidx = self.register_model.mapToSource(idx)
                    #debug('deselected', idx, sidx)
                    self.segment_selection_model.select(sidx, QtGui.QItemSelectionModel.Deselect)

            self.register_selection_model.selectionChanged.connect(register_to_segment_selections)
            self.register_selection_model.selectionChanged.connect(self.update_selection_counts)

            def label_to_register_selections(selected, deselected):
                for idx in selected.indexes():
                    if idx.column() == 0:
                        ridx = self.label_model.mapToSource(idx)
                        #sidx = self.register_model.mapToSource(ridx)
                        #debug('selected', idx, ridx)
                        self.register_selection_model.select(ridx, QtGui.QItemSelectionModel.Select)
                for idx in deselected.indexes():
                    if idx.column() == 0:
                        ridx = self.label_model.mapToSource(idx)
                        #sidx = self.register_model.mapToSource(ridx)
                        #debug('deselected', idx, ridx)
                        self.register_selection_model.select(ridx, QtGui.QItemSelectionModel.Deselect)

            self.label_selection_model.selectionChanged.connect(label_to_register_selections)
            self.label_selection_model.selectionChanged.connect(self.update_selection_counts)

        else:
            err('invalid segmentation parameters')
            QtGui.QErrorMessage(dialog).showMessage('Some segmentation parameters are invalid.')


    def toggle_component_selection(self, component, select=None):
        target = component.surface
        outline = target.parent.children[-1]
        if isinstance(outline, mayavi.modules.outline.Outline):
            debug('outline exists')
            if select == None:
                outline.visible = not outline.visible
            else:
                outline.visible = select
        elif select == None or select:
            debug('outline does not exist, add new outline')
            ol = Outline()
            self.engine.add_filter(ol, target)

            ol.actor.actor.pickable = False

            if isinstance(component, PointComponentItem):
                x, y, z = component.xyz
                ol.manual_bounds = True
                ol.bounds = (x-2, x+2, y-2, y+2, z-2, z+2)

        if outline.visible:
            debug('target is selected')
        else:
            debug('target is deselected')


    def _remove_segment(self, component):
        component.source.visible = False
        component.is_electrode = False
        if component.dot:
            component.dot.visible = False
        if component.rod:
            component.rod.visible = False

        self.segment_selection_model.select(component.index, QtGui.QItemSelectionModel.Deselect)
        

    def remove_segment(self):
        for idx in self.segment_selection_model.selectedIndexes():
            item = self.segment_model.itemFromIndex(idx)
            self._remove_segment(item)
        self.register_model.build_index_maps()
        self.update_electrode_count()
        self.update_register_count()
        #self.ui.label_electrode_num.setText(str(self.register_model.rowCount(QtCore.QModelIndex())))


    def _restore_segment(self, component):
        component.source.visible = True
        component.is_electrode = True
        if component.dot:
            component.dot.visible = True
        if component.rod:
            component.rod.visible = True


    # TODO decorator for model node count change
    def restore_segment(self):
        for idx in self.segment_selection_model.selectedIndexes():
            item = self.segment_model.itemFromIndex(idx)
            self._restore_segment(item)
        self.register_model.build_index_maps()
        self.update_electrode_count()
        self.update_register_count()
        #self.ui.label_electrode_num.setText(str(self.register_model.rowCount(QtCore.QModelIndex())))


    @QtCore.Slot(bool)
    def manual_add(self, checked):
        if checked:
            if self.mode == 'free':
                self.mode = 'manual add'
                self.dura_surf.actor.actor.pickable = False
                info('enter manual add mode')
            else:
                self.ui.pushButton_add.setChecked(False)
        else:
            self.mode = 'free'
            self.dura_surf.actor.actor.pickable = True
            info('leave manual add mode')


    def split_voxel(self, voxel, n_piece):
        #import pdb; pdb.set_trace()
        d = self.ct.getVoxDims()
        ijk = np.asarray(np.nonzero(voxel)).T
        xyz = ijk * d
        #debug(xyz)
        centroids, label, inertia = cluster.k_means(xyz, n_piece)
        debug('k means ended with inertia %f' % inertia)
        #return map(lambda i: ijk[np.argwhere(label == i)], xrange(n_piece))
        return ijk, label

    @wrap_get_set_view
    def split_component(self):
        n_piece = self.ui.spinBox_split.value()

        #view = self.get_view()

        for idx in self.ui.treeView_edit.selectedIndexes():
            component = self.segment_model.itemFromIndex(idx)
            info('splitting %s into %d pieces' % (component.name, n_piece))
            
            ijks, labels = self.split_voxel(component.voxel, n_piece)
            voxel = np.array(component.voxel)
            for l, (i, j, k) in enumerate(ijks):
                voxel[i, j, k] = labels[l] + 1
            # create new segments
            slices = ndimage.find_objects(voxel)
            root = self.segment_model.root_item
            for i, s in enumerate(slices):
                debug(s)
                bbc0 = np.reshape(map(lambda x: x.start - 1, s), (-1, 1))
                bbc1 = np.reshape(map(lambda x: x.stop + 1, s), (-1, 1))
                new_voxel = np.asarray(np.where(voxel[slice(bbc0[0], bbc1[0]), slice(bbc0[1], bbc1[1]), slice(bbc0[2], bbc1[2])] == i + 1, 1, 0), 'i1')
                co = component.transform[:3, :3].dot(bbc0)
                m = np.array(component.transform)
                m[:3, 3:] += co
                new_component = self.create_segment(new_voxel, m, 'split %d' % i)
                self.pickable_actors[repr(new_component.surface.actor.actor)] = new_component
                # tree layout
                self.segment_model.beginInsertRows(idx, component.childCount(), component.childCount()+1)
                component.appendChild(new_component)
                self.segment_model.endInsertRows()
            # remove the original segment
            self._remove_segment(component)
            self.ui.treeView_edit.expand(idx)
            self.ui.treeView_edit.scrollTo(idx, QtGui.QAbstractItemView.PositionAtTop)
        #self.set_view(*view)

        self.register_model.build_index_maps()
        self.update_electrode_count()
        self.update_component_count()
        self.update_register_count()

        #debug('electrode #', self.register_model.rowCount(QtCore.QModelIndex()))
        #import pdb; pdb.set_trace()
        #self.ui.label_electrode_num.setText(str(self.register_model.rowCount(QtCore.QModelIndex())))


    def create_segment(self, voxel, transform, name='component'):
        source = self.mlab.pipeline.scalar_field(voxel)
        contour_filter = self.mlab.pipeline.contour(source)
        contour_filter.filter.contours = [0.5]
        transform_filter = build_transform_filter(self.mlab, contour_filter, transform)
        normal_filter = self.mlab.pipeline.poly_data_normals(transform_filter)
        normal_filter.filter.feature_angle = 80.
        surface = self.mlab.pipeline.surface(normal_filter)
        component = ComponentItem(name, voxel, transform, source, surface)
        x, y, z = component.centroid.flatten()
        component.text = self.mlab.text3d(x, y, z, '', scale=2.)
        return component
        
    
    def add_electrode(self, xyz, color=(0.3, 0.3, 0.3)):
        x, y, z = xyz
        s = self.mlab.points3d([x], [y], [z], color=color, scale_factor=2.5)
        # m = np.eye(4)
        # m[:3, 3] = xyz
        # m[:3, :3] *= 8
        # v = np.zeros((3, 3, 3), dtype='i1')
        # v[1, 1, 1] = 1.
        #return self.create_segment(v, m, 'added')
        # TODO new type of component with no voxel
        component = PointComponentItem('added %d' % self.register_model.rowCount(QtCore.QModelIndex()), xyz, s.parent.parent, s)
        x, y, z = component.centroid.flatten()
        component.text = self.mlab.text3d(x, y, z, '', scale=2.)
        return component


    def register_electrode(self, component, to_position, color=(1., 1., 1.)):
        debug('registering electrode %s to %r' % (component.name, to_position))
        if component.dot:
            component.dot.remove()
        if component.rod:
            component.rod.remove()
        # draw dot and rod
        x, y, z = to_position
        component.dot = self.mlab.points3d([x], [y], [z], color=color, scale_factor=2)
        component.dot.actor.actor.pickable = 0
        xx, yy, zz = np.vstack([component.centroid.T, [to_position]]).T
        component.rod = self.mlab.plot3d(xx, yy, zz, color=color, tube_radius=0.5)
        component.rod.actor.actor.pickable = 0
        component.register_position = to_position


    def register_nearest(self, component):
        c = component.centroid.reshape(-1)
        i = self.dura_vertices_kdtree.query(c)[1]
        p = self.dura_vertices[i] + self.dura[2][:3, 3:].T
        return i, p[0]


    def register_pa(self, component):
        i = estimate.inertia_matrix(component.points.T)
        n = estimate.principal_axis(i)
        ce = component.centroid.reshape(-1)
        return register.line_surf_intersection(ce, n, self.dura_vertices + self.dura[2][:3, 3:].T)


    def register_svd(self, component):
        n = estimate.fit_plane(component.points.T)
        ce = component.centroid.reshape(-1)
        return register.line_surf_intersection(ce, n, self.dura_vertices + self.dura[2][:3, 3:].T)


    def register_manual(self, xyz):
        i = self.dura_vertices_kdtree.query(xyz)[1]
        p = self.dura_vertices[i] + self.dura[2][:3, 3:].T
        return i, p[0]


    @QtCore.Slot()
    @wrap_get_set_view
    def do_register_nearest(self):
        info('registering electrodes to nearest vertices on dura')
        for idx in self.register_selection_model.selectedIndexes():
            if idx.column() == 0:
                component = self.segment_model.itemFromIndex(self.register_model.mapToSource(idx))
                dura_id, to_position = self.register_nearest(component)
                self.register_electrode(component, to_position, color=(0.9, 0.7, 0.2))
                component.register_method = 'nearest'
                component.register_dura_vertex_id = dura_id
        self.update_register_count()


    @QtCore.Slot()
    @wrap_get_set_view
    def do_register_principal_axis(self):
        info('registering electrodes by projecting along their principal axes')
        for idx in self.register_selection_model.selectedIndexes():
            if idx.column() == 0:
                component = self.segment_model.itemFromIndex(self.register_model.mapToSource(idx))
                dura_id, to_position = self.register_pa(component)
                self.register_electrode(component, to_position, color=(0.2, 0.9, 0.2))
                component.register_method = 'principal axis'
                component.register_dura_vertex_id = dura_id
        self.update_register_count()


    @QtCore.Slot()
    @wrap_get_set_view
    def do_register_svd(self):
        info('registering electrodes by projecting along their best fitted planes\' normals')
        for idx in self.register_selection_model.selectedIndexes():
            if idx.column() == 0:
                component = self.segment_model.itemFromIndex(self.register_model.mapToSource(idx))
                dura_id, to_position = self.register_svd(component)
                self.register_electrode(component, to_position, color=(0.2, 0.7, 0.9))
                component.register_method = 'best fitted plane'
                component.register_dura_vertex_id = dura_id
        self.update_register_count()


    @QtCore.Slot(bool)
    def do_register_manual(self, checked):
        # TODO dynamic enable/disable state
        if checked:
            selected = filter(lambda x: x.column()==0, self.register_selection_model.selectedIndexes())
            if len(selected) == 1 and self.mode == 'free':
                info('start registering electrodes manually')
                self.toggle_components_pickable(False)
                self.mode = 'manual register'
                self.update_register_count()
            else:
                debug('manual registration only supports single selection')
                self.ui.pushButton_manual.setChecked(False)
            
        else:
            info('stop manual registration mode')
            self.mode = 'free'
            #import pdb; pdb.set_trace()
            self.toggle_components_pickable(True)
            #self.fig.on_mouse_pick(self.pick_register_point_callback, type='cell', button='Right', remove=True)
            #self.pick_register_point_callback = None


    @QtCore.Slot()
    @wrap_get_set_view
    def unregister(self):
        info('unregistering electrodes')
        for idx in self.register_selection_model.selectedIndexes():
            if idx.column() == 0:
                component = self.segment_model.itemFromIndex(self.register_model.mapToSource(idx))
                if component.dot:
                    component.dot.remove()
                if component.rod:
                    component.rod.remove()
                    component.register_position = component.centroid.reshape(-1)
                    component.register_method = None
                    component.register_dura_vertex_id = None
        self.update_register_count()


    def get_view(self):
        view = self.mlab.view()
        roll = self.mlab.roll()
        debug('view saved')
        return view, roll


    def set_view(self, view, roll):
        self.mlab.view(*view)
        self.mlab.roll(roll)
        debug('view set')


    def toggle_components_pickable(self, pickable):
        debug('toggling components pickability')
        sm = self.segment_model
        o = [QtCore.QModelIndex()]
        while len(o) > 0:
            x = o.pop()
            component = sm.itemFromIndex(x)
            if isinstance(component, ComponentItem) and component.is_electrode:
                component.surface.actor.actor.pickable = pickable
            if sm.hasChildren(x):
                for r in xrange(sm.rowCount(x)):
                    o.append(sm.index(r, 0, x))


    def pick_dura_point(self):
        pass


    def update_electrode_count(self):
        sm = self.segment_model
        o = [QtCore.QModelIndex()]
        n = 0
        while len(o) > 0:
            x = o.pop()
            y = sm.itemFromIndex(x)
            if isinstance(y, ComponentItem) and y.is_electrode:
                n += 1
            if sm.hasChildren(x):
                for r in xrange(sm.rowCount(x)):
                    o.append(sm.index(r, 0, x))
        
        self.ui.label_edit_electrode_count.setText(str(n))
        self.ui.label_register_electrode_count.setText(str(n))

        debug('updated electrode count: %d' % n)


    def update_component_count(self):
        sm = self.segment_model
        o = [QtCore.QModelIndex()]
        n = -1
        while len(o) > 0:
            x = o.pop()
            n += 1
            if sm.hasChildren(x):
                for r in xrange(sm.rowCount(x)):
                    o.append(sm.index(r, 0, x))
        
        self.ui.label_component_count.setText(str(n))

        debug('updated component count: %d' % n)


    def update_selection_counts(self):
        n = len(filter(lambda x: x.column()==0, self.ui.treeView_edit.selectedIndexes()))
        m = len(filter(lambda x: x.column()==0, self.ui.listView_register.selectedIndexes()))
        self.ui.label_edit_select_count.setText(str(n))
        self.ui.label_register_select_count.setText(str(m))
        self.ui.label_label_select_count.setText(str(m))


    def update_register_count(self):
        n = self.register_model.rowCount()
        n_registered = 0
        for i in xrange(n):
            electrode =  self.segment_model.itemFromIndex(self.register_model.mapToSource(self.label_model.mapToSource(self.label_model.index(i, 0))))
            if electrode and electrode.register_method:
                n_registered += 1
        info('registered electrode count: %d' % n_registered)
        self.ui.label_register_complete_count.setText(str(n_registered))


    @QtCore.Slot()
    def export(self):
        info('export result')

        dialog = QtGui.QDialog()
        dialog_ui = Ui_ExportDialog()
        dialog_ui.setupUi(dialog)

        def browse_csv():
            fn, t = QtGui.QFileDialog.getSaveFileName(dir='electrodes.csv',
                                                      caption='Save CSV to...', 
                                                      filter='CSV File (*.csv);;Any File (*)')
            dialog_ui.lineEdit_csv.setText(fn)
        dialog_ui.pushButton_csv_browse.clicked.connect(browse_csv)
        dialog_ui.pushButton_csv_export.clicked.connect(lambda : self.export_csv(dialog_ui.lineEdit_csv.text(), dialog_ui.checkBox_only_selected.isChecked()))
    
        def browse_dat():
            if dialog_ui.checkBox_per_grid.isChecked():
                fn = QtGui.QFileDialog.getExistingDirectory(dir='electrodes',
                                                            caption='Save Freesurfer Pointsets to...') 
                fn += os.sep
            else:
                fn, t = QtGui.QFileDialog.getSaveFileName(dir='electrodes.dat',
                                                          caption='Save Freesurfer Pointset to...', 
                                                          filter='Freesurfer Pointset File (*.dat);;Any File (*)')
                
            dialog_ui.lineEdit_dat.setText(fn)
        dialog_ui.pushButton_dat_browse.clicked.connect(browse_dat)
        dialog_ui.pushButton_dat_export.clicked.connect(lambda : self.export_dat(dialog_ui.lineEdit_dat.text(), dialog_ui.checkBox_only_selected.isChecked(), dialog_ui.checkBox_per_grid.isChecked()))

        dialog.exec_()


    def export_csv(self, fn, only_selected=False):
        info('output csv: %s' % fn)
        n_electrode = self.label_model.rowCount()
        with open(fn, 'wb') as f:
            w = csv.DictWriter(f, ['component name', 'grid label', 'grid id', 'channel number', 'original location.x', 'original location.y', 'original location.z', 'register method', 'registered location.x', 'registered location.y', 'registered location.z', 'dura vertex id', 'note'])
            w.writeheader()

            if only_selected:
                electrodes = map(lambda i: self.segment_model.itemFromIndex(self.register_model.mapToSource(self.label_model.mapToSource(i))), filter(lambda x: x.column() == 0, self.label_selection_model.selectedIndexes()))
            else:
                electrodes = map(lambda i: self.segment_model.itemFromIndex(self.register_model.mapToSource(self.label_model.mapToSource(self.label_model.index(i, 0)))), xrange(n_electrode))

            for electrode in electrodes:
                if electrode:
                    w.writerow({
                        'component name': electrode.name,
                        'grid label': electrode.grid_label,
                        'grid id': electrode.grid_id,
                        'channel number': electrode.channel_number,
                        'original location.x': electrode.centroid[0,0], 
                        'original location.y': electrode.centroid[1,0], 
                        'original location.z': electrode.centroid[2,0], 
                        'register method': electrode.register_method or 'none',
                        'registered location.x': electrode.register_position[0], 
                        'registered location.y': electrode.register_position[1], 
                        'registered location.z': electrode.register_position[2],
                        'dura vertex id': electrode.register_dura_vertex_id,
                        'note': electrode.note,
                    })
        info('finish exporting')


    def export_dat(self, path, only_selected=False, per_grid=False):
        n_electrode = self.label_model.rowCount()
        if only_selected:
            electrodes = map(lambda i: self.segment_model.itemFromIndex(self.register_model.mapToSource(self.label_model.mapToSource(i))), filter(lambda x: x.column() == 0, self.label_selection_model.selectedIndexes()))
        else:
            electrodes = map(lambda i: self.segment_model.itemFromIndex(self.register_model.mapToSource(self.label_model.mapToSource(self.label_model.index(i, 0)))), xrange(n_electrode))
        if per_grid:
            # interpret path as path to its directory
            path = os.path.dirname(path)
            if not os.path.exists(path):
                os.makedirs(path)
            labels = set(map(lambda x: x.grid_label, electrodes))
            info('exporting labels %r to %s' % (labels, path))
            for label in labels:
                self.export_freesurfer_dat(os.path.join(path, '%s.dat' % label), filter(lambda x: x.grid_label==label, electrodes))
        else:
            self.export_freesurfer_dat(path, electrodes)


    def export_freesurfer_dat(self, fn, electrodes):
        with open(fn, 'wb') as f:
            n = 0
            for electrode in electrodes:
                if electrode:
                    f.write('%f %f %f\n' % tuple(electrode.register_position))
                    n += 1
            # write footer
            f.write('info\n')
            f.write('numpoints %d\n' % n)
            f.write('useRealRAS 1')
        info('finish exporting %d electrodes to %s' % (len(electrodes), fn))
            

    def batch_assign_grid_label(self):
        info('assigning grid label %s to electrodes in batch' % self.ui.lineEdit_grid_label.text())
        col = ComponentItem.prop_map.index('grid_label')
        for idx in self.label_selection_model.selectedIndexes():
            if idx.column() == col:
                self.label_model.setData(idx, self.ui.lineEdit_grid_label.text().strip())
                self.label_model.dataChanged.emit(idx, idx)


    def export_segmentation_dataset(self):
        info('exporting segmentation dataset for training classifiers')

        fn, t = QtGui.QFileDialog.getSaveFileName(caption='Export Segmentation Dataset...', 
                                                  filter='CSV File (*.csv);; Any File (*)',
                                                  options=QtGui.QFileDialog.DontUseNativeDialog)
        
        if fn:
            sm = self.segment_model
            o = [QtCore.QModelIndex()]
            components = []
            while len(o) > 0:
                x = o.pop()
                y = sm.itemFromIndex(x)
                if isinstance(y, ComponentItem) and not isinstance(y, PointComponentItem) and x.isValid():
                    components.append(y)
                if sm.hasChildren(x):
                    for r in reversed(xrange(sm.rowCount(x))):
                        o.append(sm.index(r, 0, x))
            with open(fn, 'wb') as f:
                w = csv.DictWriter(f, ['size', 'centroid.x', 'centroid.y', 'centroid.z', 'ptp.x', 'ptp.y', 'ptp.z', 'dura_distance', 'is_top_segment', 'children_count', 'electrode_count'])
                w.writeheader()
                for component in components:
                    centroid = component.centroid.reshape(-1)
                    ptps = component.points.ptp(axis=1)
                    dv = np.product(self.ct.getVoxDims())
                    distance, index = self.dura_vertices_kdtree.query(centroid)

                    electrode_count = 1 if component.is_electrode else 0
                    if not component.is_electrode and component.childCount() > 0:
                        o = [component]
                        while len(o) > 0:
                            x = o.pop()
                            if x.is_electrode:
                                electrode_count += 1
                            for child in x.children:
                                o.append(child)

                    w.writerow({
                        'size': dv * component.voxel.sum() ,
                        'centroid.x': centroid[0],
                        'centroid.y': centroid[1],
                        'centroid.z': centroid[2],
                        'ptp.x': ptps[0], 
                        'ptp.y': ptps[1], 
                        'ptp.z': ptps[2],
                        'dura_distance': distance,
                        'is_top_segment': 1 if component.parent == sm.root_item else 0,
                        'children_count': component.childCount(),
                        'electrode_count': electrode_count,
                    })
                    # note components containing electrodes vs electrodes 
                    # electrode_count=1 and children_count>0 vs electrode_count=1 and children_count=0
            info('exported to %s' % fn)

def build_transform_filter(mlab, input, affine):
    filter = mlab.pipeline.transform_data(input)
    m = tvtk.Matrix4x4()
    m.from_array(affine)
    filter.transform.set_matrix(m)
    filter.widget.off()
    return filter

def read_surface(filename):
    vertices, faces, affine, offset = io.read_surf(filename)
    m = np.eye(4)
    m[:3, 3] = offset
    return vertices, faces, m

if __name__ == '__main__':
    info('starting application')
    app = QtGui.QApplication.instance()

    window = QtGui.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(window)
    
    mayavi_widget = MayaviQWidget()
    window.setCentralWidget(mayavi_widget)

    main = Application(ui=ui, mlab=mayavi_widget.visualization.scene.mlab)
    
    window.show()
    app.exec_()

    info('exited')
