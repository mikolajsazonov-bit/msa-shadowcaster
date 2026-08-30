#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
***************************************************************************
*   MSA: ShadowCaster - Punkt wejściowy wtyczki QGIS                      *
*   Autor: Mikołaj Sazonov                                                *
***************************************************************************
"""

def classFactory(iface):
    """
    Fabryka wtyczki wywoływana przez QGIS do załadowania wtyczki.
    """
    from .plugin import MSAShadowCasterPlugin
    return MSAShadowCasterPlugin(iface)
