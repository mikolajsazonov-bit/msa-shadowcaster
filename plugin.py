#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
***************************************************************************
*   MSA: ShadowCaster - Główna klasa wtyczki QGIS                         *
*   Autor: Mikołaj Sazonov                                                *
***************************************************************************
"""

import os
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsApplication
import processing

from .shadow_provider import MSAShadowCasterProvider


class MSAShadowCasterPlugin(object):
    """
    Główna klasa wtyczki MSA: ShadowCaster dla QGIS 3.x.
    """

    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None
        self.plugin_dir = os.path.dirname(__file__)

    def tr(self, message_en: str, message_pl: str = None) -> str:
        from .i18n import tr as i18n_tr
        return i18n_tr(message_en, message_pl, 'MSAShadowCasterPlugin')

    def initProcessing(self):
        self.provider = MSAShadowCasterProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()

        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        self.action = QAction(
            icon,
            self.tr('MSA: ShadowCaster - Building Shadow Analysis', 'MSA: ShadowCaster - Analiza Cieni Budynków'),
            self.iface.mainWindow()
        )
        self.action.setStatusTip(self.tr(
            'Run 2.5D building shadow vector analysis (MSA: ShadowCaster)',
            'Uruchom analizę cieni budynków 2.5D (MSA: ShadowCaster)'
        ))
        self.action.triggered.connect(self.run)

        # Dodanie do paska narzędzi i menu Wektor
        self.iface.addVectorToolBarIcon(self.action)
        self.iface.addPluginToVectorMenu(self.tr('MSA: ShadowCaster', 'MSA: ShadowCaster'), self.action)

    def unload(self):
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)

        if self.action is not None:
            self.iface.removePluginVectorMenu(self.tr('MSA: ShadowCaster'), self.action)
            self.iface.removeVectorToolBarIcon(self.action)

    def run(self):
        """
        Otwiera okno dialogowe algorytmu MSA: ShadowCaster.
        """
        processing.execAlgorithmDialog('msa_shadowcaster:shadow_analysis_25d')
