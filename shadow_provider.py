#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
***************************************************************************
*   MSA: ShadowCast - QgsProcessingProvider dla QGIS 3.x                  *
*   Autor: Mikołaj Sazonov                                                *
***************************************************************************
"""

import os
from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider
from .shadow_algorithm import MSAShadowAnalysis25DAlgorithm


class MSAShadowCastProvider(QgsProcessingProvider):
    """
    Dostawca algorytmów analizy słonecznej MSA: ShadowCast w panelu Narzędzi geoprocesingu.
    """

    def __init__(self):
        super().__init__()

    def id(self):
        return 'msa_shadowcast'

    def name(self):
        return 'MSA: ShadowCast'

    def icon(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        return super().icon()

    def longName(self):
        return self.name()

    def loadAlgorithms(self):
        self.addAlgorithm(MSAShadowAnalysis25DAlgorithm())
