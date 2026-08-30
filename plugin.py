#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
***************************************************************************
*   MSA: ShadowCast - Główna klasa wtyczki QGIS                           *
*   Autor: Mikołaj Sazonov                                                *
***************************************************************************
"""

import os
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsApplication
import processing

from .shadow_provider import MSAShadowCastProvider


class MSAShadowCastPlugin(object):
    """
    Główna klasa wtyczki MSA: ShadowCast dla QGIS 3.x.
    """

    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None
        self.plugin_dir = os.path.dirname(__file__)

    def tr(self, message):
        return QCoreApplication.translate('MSAShadowCastPlugin', message)

    def initProcessing(self):
        self.provider = MSAShadowCastProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action = QAction(
            icon,
            self.tr('MSA: ShadowCast - Analiza Cieni Budynków'),
            self.iface.mainWindow()
        )
        self.action.setStatusTip(self.tr('Uruchom analizę cieni budynków 2.5D (MSA: ShadowCast)'))
        self.action.triggered.connect(self.run)

        # Dodanie do paska narzędzi i menu Wektor
        self.iface.addVectorToolBarIcon(self.action)
        self.iface.addPluginToVectorMenu(self.tr('MSA: ShadowCast'), self.action)

    def unload(self):
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)

        if self.action is not None:
            self.iface.removePluginVectorMenu(self.tr('MSA: ShadowCast'), self.action)
            self.iface.removeVectorToolBarIcon(self.action)

    def run(self):
        """
        Otwiera okno dialogowe algorytmu MSA: ShadowCast.
        """
        processing.execAlgorithmDialog('msa_shadowcast:shadow_analysis_25d')
