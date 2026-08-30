#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
***************************************************************************
*   MSA: ShadowCast - Punkt wejściowy wtyczki QGIS                        *
*   Autor: Mikołaj Sazonov                                                *
***************************************************************************
"""

def classFactory(iface):
    """
    Fabryka wtyczki wywoływana przez QGIS do załadowania wtyczki.
    """
    from .plugin import MSAShadowCastPlugin
    return MSAShadowCastPlugin(iface)
