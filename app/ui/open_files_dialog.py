# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/open_files_dialog.ui'
#
# Created: Thu Oct 31 15:38:50 2013
#      by: pyside-uic 0.2.15 running on PySide 1.2.1
#
# WARNING! All changes made in this file will be lost!

from PySide import QtCore, QtGui

class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(657, 151)
        self.verticalLayout = QtGui.QVBoxLayout(Dialog)
        self.verticalLayout.setObjectName("verticalLayout")
        self.horizontalLayout = QtGui.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.label = QtGui.QLabel(Dialog)
        self.label.setObjectName("label")
        self.horizontalLayout.addWidget(self.label)
        self.ctLineEdit = QtGui.QLineEdit(Dialog)
        self.ctLineEdit.setObjectName("ctLineEdit")
        self.horizontalLayout.addWidget(self.ctLineEdit)
        self.ctPushButton = QtGui.QPushButton(Dialog)
        self.ctPushButton.setObjectName("ctPushButton")
        self.horizontalLayout.addWidget(self.ctPushButton)
        self.verticalLayout.addLayout(self.horizontalLayout)
        self.horizontalLayout_2 = QtGui.QHBoxLayout()
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.label_2 = QtGui.QLabel(Dialog)
        self.label_2.setObjectName("label_2")
        self.horizontalLayout_2.addWidget(self.label_2)
        self.duraLineEdit = QtGui.QLineEdit(Dialog)
        self.duraLineEdit.setObjectName("duraLineEdit")
        self.horizontalLayout_2.addWidget(self.duraLineEdit)
        self.duraPushButton = QtGui.QPushButton(Dialog)
        self.duraPushButton.setObjectName("duraPushButton")
        self.horizontalLayout_2.addWidget(self.duraPushButton)
        self.verticalLayout.addLayout(self.horizontalLayout_2)
        spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.buttonBox = QtGui.QDialogButtonBox(Dialog)
        self.buttonBox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Open)
        self.buttonBox.setCenterButtons(False)
        self.buttonBox.setObjectName("buttonBox")
        self.verticalLayout.addWidget(self.buttonBox)

        self.retranslateUi(Dialog)
        QtCore.QObject.connect(self.buttonBox, QtCore.SIGNAL("rejected()"), Dialog.reject)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        Dialog.setWindowTitle(QtGui.QApplication.translate("Dialog", "Open CT and dura...", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("Dialog", "CT volume", None, QtGui.QApplication.UnicodeUTF8))
        self.ctLineEdit.setPlaceholderText(QtGui.QApplication.translate("Dialog", "path to co-registered CT head scan", None, QtGui.QApplication.UnicodeUTF8))
        self.ctPushButton.setText(QtGui.QApplication.translate("Dialog", "Browse...", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText(QtGui.QApplication.translate("Dialog", "Dura mesh", None, QtGui.QApplication.UnicodeUTF8))
        self.duraLineEdit.setPlaceholderText(QtGui.QApplication.translate("Dialog", "path to dura surface mesh", None, QtGui.QApplication.UnicodeUTF8))
        self.duraPushButton.setText(QtGui.QApplication.translate("Dialog", "Browse...", None, QtGui.QApplication.UnicodeUTF8))

