#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
***************************************************************************
*   MSA: ShadowCaster - Algorytm Geoprocesingu dla QGIS 3.x               *
*   Autor: Mikołaj Sazonov                                                *
*   Opis: Wektorowa analiza cieni budynków 2.5D z eliminacją błędów 2D   *
***************************************************************************
"""

import math
import re
from datetime import datetime

from qgis.PyQt.QtCore import QCoreApplication, QVariant
from qgis.core import (
    Qgis,
    QgsProcessing,
    QgsProcessingAlgorithm,
    QgsProcessingException,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterEnum,
    QgsProcessingParameterField,
    QgsProcessingParameterNumber,
    QgsProcessingParameterString,
    QgsProcessingParameterFeatureSink,
    QgsProcessingUtils,
    QgsVectorLayer,
    QgsFillSymbol,
    QgsSingleSymbolRenderer,
    QgsFeature,
    QgsFeatureSink,
    QgsGeometry,
    QgsFields,
    QgsField,
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsCoordinateReferenceSystem
)

import shapely
import shapely.wkt
import shapely.affinity
from shapely.geometry import Polygon, MultiPolygon, box, GeometryCollection
from shapely.ops import unary_union


def parse_height_value(raw_val, default=1.0):
    """
    Inteligentnie parsuje wartość liczbową wysokości lub kondygnacji.
    Obsługuje typy int, float, a także teksty, np:
    '3', '3.5', '3,5', '4 kondygnacje', '12 m', '2-piętrowy'.
    """
    if raw_val is None:
        return default
    if isinstance(raw_val, (int, float)):
        if math.isnan(raw_val):
            return default
        return float(raw_val)

    s = str(raw_val).strip().replace(',', '.')
    if not s:
        return default

    try:
        return float(s)
    except ValueError:
        match = re.search(r'[-+]?\d*\.?\d+', s)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return default

    return default


def to_multipolygon_shapely(geom, min_area=0.001):
    """
    Ekstrahuje wyłącznie części poligonowe (2D) z dowolnej geometrii Shapely
    (Polygon, MultiPolygon, GeometryCollection) i odrzuca artefakty liniowe/punktowe.
    Zwraca zawsze czysty obiekt MultiPolygon lub None.
    """
    if geom is None or geom.is_empty:
        return None

    polys = []

    def _collect(g):
        if g is None or g.is_empty:
            return
        if isinstance(g, Polygon):
            if g.is_valid and g.area >= min_area:
                polys.append(g)
            elif not g.is_valid:
                valid_g = shapely.make_valid(g)
                _collect(valid_g)
        elif isinstance(g, MultiPolygon):
            for sub_p in g.geoms:
                _collect(sub_p)
        elif hasattr(g, 'geoms'):
            for sub_g in g.geoms:
                _collect(sub_g)

    _collect(geom)

    if not polys:
        return None

    mp = MultiPolygon(polys)
    if not mp.is_valid:
        mp = shapely.make_valid(mp)
        return to_multipolygon_shapely(mp, min_area=min_area)
    return mp


def calculate_sun_position(lat, lon, dt, utc_offset_hours=2.0):
    """
    Oblicza azymut (stopnie od północy zgodnie z ruchem wskazówek zegara)
    oraz kąt elewacji (stopnie nad horyzontem) wg algorytmu NOAA.
    """
    year = dt.year
    month = dt.month
    day = dt.day
    hour = dt.hour
    minute = dt.minute
    second = dt.second

    if month <= 2:
        year -= 1
        month += 12
    A = math.floor(year / 100)
    B = 2 - A + math.floor(A / 4)
    day_fraction = (hour - utc_offset_hours + minute / 60.0 + second / 3600.0) / 24.0
    jd = math.floor(365.25 * (year + 4716)) + math.floor(30.6001 * (month + 1)) + day + B - 1524.5 + day_fraction

    t = (jd - 2451545.0) / 36525.0
    l0 = (280.46646 + t * (36000.76983 + 0.0003032 * t)) % 360.0
    m = 357.52911 + t * (35999.05029 - 0.0001537 * t)
    m_rad = math.radians(m)

    c = (math.sin(m_rad) * (1.914602 - t * (0.004817 + 0.000014 * t)) +
         math.sin(2 * m_rad) * (0.019993 - 0.000101 * t) +
         math.sin(3 * m_rad) * 0.000289)

    sun_true_lon = l0 + c
    omega = 125.04 - 1934.136 * t
    omega_rad = math.radians(omega)
    sun_app_lon = sun_true_lon - 0.00569 - 0.00478 * math.sin(omega_rad)

    eps0 = 23 + (26 + ((21.448 - t * (46.815 + t * (0.00059 - t * 0.001813)))) / 60.0) / 60.0
    eps = eps0 + 0.00256 * math.cos(omega_rad)
    eps_rad = math.radians(eps)

    sin_dec = math.sin(eps_rad) * math.sin(math.radians(sun_app_lon))
    dec_rad = math.asin(sin_dec)
    dec_deg = math.degrees(dec_rad)

    tan_eps_half = math.tan(eps_rad / 2.0)
    y = tan_eps_half * tan_eps_half
    ecc = 0.016708634 - t * (0.000042037 + 0.0000001267 * t)
    l0_rad = math.radians(l0)
    eot = 4.0 * math.degrees(
        y * math.sin(2 * l0_rad) -
        2 * ecc * math.sin(m_rad) +
        4 * ecc * y * math.sin(m_rad) * math.cos(2 * l0_rad) -
        0.5 * y * y * math.sin(4 * l0_rad) -
        1.25 * ecc * ecc * math.sin(2 * m_rad)
    )

    local_time_min = hour * 60.0 + minute + second / 60.0
    tst = (local_time_min + eot + 4.0 * lon - 60.0 * utc_offset_hours) % 1440.0

    ha = tst / 4.0 - 180.0
    if ha < -180.0:
        ha += 360.0
    ha_rad = math.radians(ha)

    lat_rad = math.radians(lat)
    cos_zenith = (math.sin(lat_rad) * math.sin(dec_rad) +
                  math.cos(lat_rad) * math.cos(dec_rad) * math.cos(ha_rad))
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    zenith_rad = math.acos(cos_zenith)
    elevation_deg = 90.0 - math.degrees(zenith_rad)

    sin_zenith = math.sin(zenith_rad)
    if sin_zenith > 1e-6:
        cos_az = (math.sin(lat_rad) * math.cos(zenith_rad) - math.sin(dec_rad)) / (math.cos(lat_rad) * sin_zenith)
        cos_az = max(-1.0, min(1.0, cos_az))
        az_deg = math.degrees(math.acos(cos_az))
        if ha > 0:
            azimuth_deg = (az_deg + 180.0) % 360.0
        else:
            azimuth_deg = (540.0 - az_deg) % 360.0
    else:
        azimuth_deg = 180.0

    return azimuth_deg, elevation_deg


def get_shadow_vector(azimuth_deg, elevation_deg, height_m):
    """
    Oblicza wektor przesunięcia cienia (dx, dy) w metrach dla danej wysokości.
    Azymut: 0° = N, 90° = E, 180° = S, 270° = W.
    """
    if elevation_deg <= 0.5:
        return 0.0, 0.0

    elev_rad = math.radians(elevation_deg)
    az_rad = math.radians(azimuth_deg)

    unit_dx = -math.sin(az_rad) / math.tan(elev_rad)
    unit_dy = -math.cos(az_rad) / math.tan(elev_rad)

    return height_m * unit_dx, height_m * unit_dy


def construct_polygon_shadow(geom, dx, dy):
    """
    Tworzy poligon rzutu cienia dla geometrii Shapely (Polygon/MultiPolygon).
    """
    if geom is None or geom.is_empty or (abs(dx) < 1e-6 and abs(dy) < 1e-6):
        return geom

    if isinstance(geom, MultiPolygon):
        parts = [construct_polygon_shadow(p, dx, dy) for p in geom.geoms if not p.is_empty]
        valid_parts = [p for p in parts if p is not None and not p.is_empty]
        return unary_union(valid_parts) if valid_parts else Polygon()

    if not isinstance(geom, Polygon) or geom.exterior is None:
        return geom

    shifted_poly = shapely.affinity.translate(geom, xoff=dx, yoff=dy)
    quads = []

    coords = list(geom.exterior.coords)
    for i in range(len(coords) - 1):
        p1 = coords[i]
        p2 = coords[i+1]
        p1_shift = (p1[0] + dx, p1[1] + dy)
        p2_shift = (p2[0] + dx, p2[1] + dy)
        quad = Polygon([p1, p2, p2_shift, p1_shift])
        if quad.is_valid and not quad.is_empty and quad.area > 1e-6:
            quads.append(quad)

    for interior in geom.interiors:
        icoords = list(interior.coords)
        for i in range(len(icoords) - 1):
            p1 = icoords[i]
            p2 = icoords[i+1]
            p1_shift = (p1[0] + dx, p1[1] + dy)
            p2_shift = (p2[0] + dx, p2[1] + dy)
            quad = Polygon([p1, p2, p2_shift, p1_shift])
            if quad.is_valid and not quad.is_empty and quad.area > 1e-6:
                quads.append(quad)

    all_parts = [geom, shifted_poly] + quads
    union_res = unary_union(all_parts)
    if not union_res.is_valid:
        union_res = shapely.make_valid(union_res)
    return union_res


class MSAShadowAnalysis25DAlgorithm(QgsProcessingAlgorithm):
    """
    Główny algorytm MSA: ShadowCaster.
    """

    INPUT = 'INPUT'
    HEIGHT_MODE = 'HEIGHT_MODE'
    HEIGHT_FIELD = 'HEIGHT_FIELD'
    STOREY_HEIGHT = 'STOREY_HEIGHT'
    SUN_INPUT_MODE = 'SUN_INPUT_MODE'
    SUN_AZIMUTH = 'SUN_AZIMUTH'
    SUN_ELEVATION = 'SUN_ELEVATION'
    DATETIME_STR = 'DATETIME_STR'
    UTC_OFFSET = 'UTC_OFFSET'
    
    OUTPUT_GROUND_SHADOWS = 'OUTPUT_GROUND_SHADOWS'
    OUTPUT_ROOF_SHADOWS = 'OUTPUT_ROOF_SHADOWS'
    OUTPUT_BUILDINGS_STATS = 'OUTPUT_BUILDINGS_STATS'

    def tr(self, string):
        return QCoreApplication.translate('MSAShadowAnalysis25DAlgorithm', string)

    def createInstance(self):
        return MSAShadowAnalysis25DAlgorithm()

    def name(self):
        return 'shadow_analysis_25d'

    def displayName(self):
        return self.tr('MSA: ShadowCaster (Wektorowa analiza cieni 2.5D)')

    def group(self):
        return self.tr('Analiza Solarna')

    def groupId(self):
        return 'solar_shadows'

    def shortHelpString(self):
        return self.tr(
            "<h3>MSA: ShadowCaster - Wektorowa Analiza Cieni 2.5D</h3>"
            "<p>Narzędzie generuje fizycznie poprawne wektory cieni rzucanych przez budynki:</p>"
            "<ul>"
            "<li><b>Cienie na gruncie:</b> Zunifikowane poligony cieni terenu ze stylem półprzezroczystym (50% czarny, bez obrysu) oraz wyciętymi obrysami budynków.</li>"
            "<li><b>Cienie na dachach:</b> Scalone poligony zacienienia dachów niższych obiektów (1 obiekt per budynek, bez nakładających się duplikatów).</li>"
            "<li><b>Statystyki budynków:</b> Warstwa wejściowa wzbogacona o pole powierzchni dachu, powierzchnię zacienioną oraz procent zacienienia dachu.</li>"
            "</ul>"
            "<p><b>Obsługa pól:</b> Pole kondygnacji/wysokości może być numeryczne lub tekstowe (np. '3', '4.5', '2 kondygnacje').</p>"
        )

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Warstwa wejściowa budynków (Poligony)'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.HEIGHT_MODE,
                self.tr('Sposób określenia wysokości budynku'),
                options=[
                    self.tr('Liczba kondygnacji (mnożona przez wysokość kondygnacji)'),
                    self.tr('Wysokość bezpośrednio w metrach')
                ],
                defaultValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.HEIGHT_FIELD,
                self.tr('Pole z liczbą kondygnacji lub wysokością (tekstowe lub numeryczne)'),
                parentLayerParameterName=self.INPUT,
                type=QgsProcessingParameterField.Any,
                defaultValue='LICZBAKONDYGNACJI'
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.STOREY_HEIGHT,
                self.tr('Wysokość jednej kondygnacji [m] (gdy wybrano liczbę kondygnacji)'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=3.0,
                minValue=0.5,
                maxValue=30.0
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.SUN_INPUT_MODE,
                self.tr('Tryb wyznaczenia pozycji słońca'),
                options=[
                    self.tr('Ręczne podanie Azymutu i Kąta elewacji'),
                    self.tr('Automatyczne wyliczenie z Daty, Czasu i Lokalizacji')
                ],
                defaultValue=1
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.SUN_AZIMUTH,
                self.tr('Azymut słońca [0-360°] (Ręczny)'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=180.0,
                minValue=0.0,
                maxValue=360.0
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.SUN_ELEVATION,
                self.tr('Elewacja / wysokość słońca nad horyzontem [0-90°] (Ręczna)'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=45.0,
                minValue=0.5,
                maxValue=90.0
            )
        )

        self.addParameter(
            QgsProcessingParameterString(
                self.DATETIME_STR,
                self.tr('Data i godzina lokalna (RRRR-MM-DD GG:MM:SS)'),
                defaultValue='2026-06-21 12:00:00'
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.UTC_OFFSET,
                self.tr('Strefa czasowa / przesunięcie UTC [godziny] (np. +2 dla Polski w lecie)'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=2.0,
                minValue=-12.0,
                maxValue=14.0
            )
        )

        # Output sinks
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_GROUND_SHADOWS,
                self.tr('Cienie na gruncie (Ground Shadows - Scalone)'),
                QgsProcessing.TypeVectorPolygon
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_ROOF_SHADOWS,
                self.tr('Cienie na dachach (Roof Shadows - Scalone per budynek)'),
                QgsProcessing.TypeVectorPolygon
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT_BUILDINGS_STATS,
                self.tr('Budynki ze statystykami nasłonecznienia'),
                QgsProcessing.TypeVectorPolygon,
                optional=True
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        source_crs = source.sourceCrs()
        if source_crs.isGeographic():
            feedback.reportError(
                self.tr("UWAGA: Warstwa wejściowa jest w stopniach geograficznych. "
                        "Dla precyzyjnych obliczeń w metrach zaleca się układ rzutowany (np. EPSG:2180)!"),
                fatalError=False
            )

        height_mode = self.parameterAsEnum(parameters, self.HEIGHT_MODE, context)
        height_field = self.parameterAsString(parameters, self.HEIGHT_FIELD, context)
        storey_height = self.parameterAsDouble(parameters, self.STOREY_HEIGHT, context)
        sun_mode = self.parameterAsEnum(parameters, self.SUN_INPUT_MODE, context)

        # 1. Pozycja słońca
        if sun_mode == 0:
            azimuth = self.parameterAsDouble(parameters, self.SUN_AZIMUTH, context)
            elevation = self.parameterAsDouble(parameters, self.SUN_ELEVATION, context)
        else:
            dt_str = self.parameterAsString(parameters, self.DATETIME_STR, context)
            utc_offset = self.parameterAsDouble(parameters, self.UTC_OFFSET, context)
            try:
                dt = datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    dt = datetime.strptime(dt_str.strip(), "%Y-%m-%d %H:%M")
                except Exception:
                    raise QgsProcessingException(f"Niepoprawny format daty i czasu: {dt_str}. Użyj 'RRRR-MM-DD GG:MM:SS'.")

            extent = source.sourceExtent()
            center_pt = extent.center()
            if source_crs.authid() != 'EPSG:4326':
                tr_to_wgs84 = QgsCoordinateTransform(source_crs, QgsCoordinateReferenceSystem('EPSG:4326'), context.transformContext())
                center_pt_wgs84 = tr_to_wgs84.transform(center_pt)
            else:
                center_pt_wgs84 = center_pt

            lon = center_pt_wgs84.x()
            lat = center_pt_wgs84.y()

            azimuth, elevation = calculate_sun_position(lat, lon, dt, utc_offset_hours=utc_offset)
            feedback.pushInfo(f"Lokalizacja centroidu: Lat {lat:.4f}°, Lon {lon:.4f}°")

        feedback.pushInfo(f"=== Parametry słoneczne: Azymut = {azimuth:.2f}°, Elewacja = {elevation:.2f}° ===")

        if elevation <= 0.1:
            raise QgsProcessingException(f"Słońce znajduje się pod horyzontem (elewacja {elevation:.2f}°). Brak cieni słonecznych.")

        unit_dx, unit_dy = get_shadow_vector(azimuth, elevation, 1.0)

        # 2. Wczytanie budynków i geometrii
        total_count = source.featureCount()
        feedback.pushInfo(f"Wczytywanie {total_count} budynków z pola '{height_field}'...")

        buildings = []
        bldgs_shapely_list = []
        max_height = 0.0

        for feat in source.getFeatures():
            geom = feat.geometry()
            if geom.isNull() or geom.isEmpty():
                continue

            raw_h = feat[height_field] if height_field and height_field in feat.fields().names() else None
            h_val = parse_height_value(raw_h, default=1.0)

            if height_mode == 0:
                height_m = max(1.0, h_val * storey_height)
            else:
                height_m = max(1.0, h_val)

            if height_m > max_height:
                max_height = height_m

            wkt_str = geom.asWkt()
            s_geom = shapely.wkt.loads(wkt_str)
            if not s_geom.is_valid:
                s_geom = shapely.make_valid(s_geom)

            s_geom_mp = to_multipolygon_shapely(s_geom, min_area=0.01)
            if s_geom_mp is None or s_geom_mp.is_empty:
                continue

            b_data = {
                'fid': feat.id(),
                'height': height_m,
                'geom': s_geom_mp,
                'feature': feat
            }
            buildings.append(b_data)
            bldgs_shapely_list.append(s_geom_mp)

        n_bldgs = len(buildings)
        feedback.pushInfo(f"Poprawnie wczytano {n_bldgs} obiektów. Maksymalna wysokość: {max_height:.1f} m.")

        if n_bldgs == 0:
            return {}

        tree = shapely.STRtree(bldgs_shapely_list)

        # 3. Przygotowanie ujść danych
        fields_ground = QgsFields()
        fields_ground.append(QgsField('shadow_id', QVariant.Int))
        fields_ground.append(QgsField('area_m2', QVariant.Double))
        (sink_ground, dest_ground) = self.parameterAsSink(
            parameters, self.OUTPUT_GROUND_SHADOWS, context,
            fields_ground, QgsWkbTypes.MultiPolygon, source_crs
        )

        fields_roof = QgsFields()
        fields_roof.append(QgsField('target_fid', QVariant.LongLong))
        fields_roof.append(QgsField('roof_h_m', QVariant.Double))
        fields_roof.append(QgsField('roof_area_m2', QVariant.Double))
        fields_roof.append(QgsField('shadow_area_m2', QVariant.Double))
        fields_roof.append(QgsField('shadow_pct', QVariant.Double))
        fields_roof.append(QgsField('caster_count', QVariant.Int))
        fields_roof.append(QgsField('caster_fids', QVariant.String))
        (sink_roof, dest_roof) = self.parameterAsSink(
            parameters, self.OUTPUT_ROOF_SHADOWS, context,
            fields_roof, QgsWkbTypes.MultiPolygon, source_crs
        )

        sink_stats, dest_stats = None, None
        if parameters.get(self.OUTPUT_BUILDINGS_STATS) is not None:
            fields_stats = QgsFields(source.fields())
            fields_stats.append(QgsField('calc_h_m', QVariant.Double))
            fields_stats.append(QgsField('roof_area_m2', QVariant.Double))
            fields_stats.append(QgsField('roof_shade_m2', QVariant.Double))
            fields_stats.append(QgsField('roof_shade_pct', QVariant.Double))
            (sink_stats, dest_stats) = self.parameterAsSink(
                parameters, self.OUTPUT_BUILDINGS_STATS, context,
                fields_stats, source.wkbType(), source_crs
            )

        # 4. Obliczenia: Cienie na dachach
        feedback.pushInfo("Rozpoczynanie obliczeń cieni na dachach...")
        roof_shading_data = {b['fid']: {'geoms': [], 'casters': []} for b in buildings}

        step = 0
        for j, b_target in enumerate(buildings):
            if feedback.isCanceled():
                break

            target_geom = b_target['geom']
            target_h = b_target['height']
            target_fid = b_target['fid']

            minx, miny, maxx, maxy = target_geom.bounds
            delta_search_x = -unit_dx * max_height
            delta_search_y = -unit_dy * max_height
            
            search_box = box(
                min(minx, minx + delta_search_x),
                min(miny, miny + delta_search_y),
                max(maxx, maxx + delta_search_x),
                max(maxy, maxy + delta_search_y)
            )

            candidate_indices = tree.query(search_box)
            for cand_idx in candidate_indices:
                b_caster = buildings[cand_idx]
                if b_caster['fid'] == target_fid:
                    continue

                caster_h = b_caster['height']
                if caster_h <= target_h:
                    continue

                delta_h = caster_h - target_h
                dx_rel = delta_h * unit_dx
                dy_rel = delta_h * unit_dy

                shadow_rel = construct_polygon_shadow(b_caster['geom'], dx_rel, dy_rel)
                
                if shadow_rel.intersects(target_geom):
                    raw_intersection = shadow_rel.intersection(target_geom)
                    roof_shadow_mp = to_multipolygon_shapely(raw_intersection, min_area=0.01)

                    if roof_shadow_mp is not None and not roof_shadow_mp.is_empty and roof_shadow_mp.area > 0.01:
                        roof_shading_data[target_fid]['geoms'].append(roof_shadow_mp)
                        roof_shading_data[target_fid]['casters'].append(b_caster['fid'])

            step += 1
            if step % 500 == 0:
                feedback.setProgress(int((step / n_bldgs) * 50))

        feedback.pushInfo("Zapisywanie unikalnych, scalonych cieni na dachach...")
        roof_merged_geoms = {}

        for b in buildings:
            t_fid = b['fid']
            r_data = roof_shading_data[t_fid]
            if not r_data['geoms']:
                continue

            raw_union = unary_union(r_data['geoms'])
            merged_roof_mp = to_multipolygon_shapely(raw_union, min_area=0.01)

            if merged_roof_mp is not None and not merged_roof_mp.is_empty and merged_roof_mp.area > 0.01:
                roof_merged_geoms[t_fid] = merged_roof_mp

                qgs_geom = QgsGeometry.fromWkt(merged_roof_mp.wkt)
                if not qgs_geom.isMultipart():
                    qgs_geom.convertToMultiType()

                roof_area = b['geom'].area
                shadow_area = merged_roof_mp.area
                shadow_pct = (shadow_area / roof_area * 100.0) if roof_area > 0 else 0.0
                unique_casters = sorted(set(r_data['casters']))
                casters_str = ", ".join(map(str, unique_casters))
                casters_cnt = len(unique_casters)

                feat_r = QgsFeature()
                feat_r.setGeometry(qgs_geom)
                feat_r.setAttributes([
                    t_fid,
                    round(b['height'], 2),
                    round(roof_area, 2),
                    round(shadow_area, 2),
                    round(shadow_pct, 2),
                    casters_cnt,
                    casters_str
                ])
                sink_roof.addFeature(feat_r, QgsFeatureSink.FastInsert)

        feedback.pushInfo("Zakończono obliczenia cieni na dachach.")

        # 5. Obliczenia: Cienie na gruncie
        feedback.pushInfo("Generowanie cieni na gruncie i wycinanie obrysów budynków...")
        all_ground_shadows = []
        for b in buildings:
            if feedback.isCanceled():
                break
            h = b['height']
            dx = h * unit_dx
            dy = h * unit_dy
            g_shadow = construct_polygon_shadow(b['geom'], dx, dy)
            if g_shadow is not None and not g_shadow.is_empty and g_shadow.area > 0.01:
                all_ground_shadows.append(g_shadow)

        if all_ground_shadows:
            union_ground_shadows = unary_union(all_ground_shadows)
            union_all_buildings = unary_union(bldgs_shapely_list)

            raw_clean_ground = union_ground_shadows.difference(union_all_buildings)
            clean_ground_mp = to_multipolygon_shapely(raw_clean_ground, min_area=0.05)

            if clean_ground_mp is not None and not clean_ground_mp.is_empty:
                for shadow_idx, p in enumerate(clean_ground_mp.geoms):
                    if p.is_empty or p.area < 0.05:
                        continue
                    qgs_g = QgsGeometry.fromWkt(p.wkt)
                    if not qgs_g.isMultipart():
                        qgs_g.convertToMultiType()

                    feat_g = QgsFeature()
                    feat_g.setGeometry(qgs_g)
                    feat_g.setAttributes([shadow_idx + 1, round(p.area, 2)])
                    sink_ground.addFeature(feat_g, QgsFeatureSink.FastInsert)

        feedback.setProgress(80)

        # 6. Statystyki nasłonecznienia budynków
        if sink_stats is not None:
            feedback.pushInfo("Zapisywanie statystyk budynków...")
            for b in buildings:
                if feedback.isCanceled():
                    break
                orig_feat = b['feature']
                geom_shapely = b['geom']
                roof_area = geom_shapely.area
                
                merged_shade = roof_merged_geoms.get(b['fid'])
                if merged_shade is not None:
                    shade_area = merged_shade.area
                else:
                    shade_area = 0.0

                shade_pct = (shade_area / roof_area * 100.0) if roof_area > 0 else 0.0

                new_feat = QgsFeature()
                new_feat.setGeometry(orig_feat.geometry())
                new_attrs = list(orig_feat.attributes())
                new_attrs.extend([
                    round(b['height'], 2),
                    round(roof_area, 2),
                    round(shade_area, 2),
                    round(shade_pct, 2)
                ])
                new_feat.setAttributes(new_attrs)
                sink_stats.addFeature(new_feat, QgsFeatureSink.FastInsert)

        feedback.setProgress(100)
        feedback.pushInfo("Sukces! Wszystkie warstwy cieni 2.5D zostały wygenerowane.")

        results = {
            self.OUTPUT_GROUND_SHADOWS: dest_ground,
            self.OUTPUT_ROOF_SHADOWS: dest_roof
        }
        if sink_stats is not None:
            results[self.OUTPUT_BUILDINGS_STATS] = dest_stats

        self.output_results = results
        return results

    def postProcessAlgorithm(self, context, feedback):
        """
        Automatyczne nadawanie stylu warstwom wynikowym cieni:
        Czarny z 50% przezroczystością (Alpha 128) i bez obrysu zewnętrznego.
        """
        results = getattr(self, 'output_results', {})
        for out_key in [self.OUTPUT_GROUND_SHADOWS, self.OUTPUT_ROOF_SHADOWS]:
            dest_id = results.get(out_key)
            if not dest_id:
                continue

            layer = QgsProcessingUtils.mapLayerFromString(dest_id, context)
            if layer is not None and isinstance(layer, QgsVectorLayer):
                # Styl: Czarny 50% przezroczystości (0,0,0,128), styl wypełnienia solid, brak linii konturu
                symbol = QgsFillSymbol.createSimple({
                    'color': '0,0,0,128',
                    'style': 'solid',
                    'outline_style': 'no',
                    'outline_color': '0,0,0,0'
                })
                layer.setRenderer(QgsSingleSymbolRenderer(symbol))
                layer.triggerRepaint()

                # Jeśli warstwa jest zapisana na dysku, zapisz plik stylu .qml obok
                try:
                    source_path = layer.source()
                    if source_path and not source_path.startswith('memory:'):
                        clean_path = source_path.split('|')[0]
                        if clean_path.endswith(('.gpkg', '.shp', '.geojson', '.sqlite')):
                            qml_path = clean_path.rsplit('.', 1)[0] + '.qml'
                            layer.saveNamedStyle(qml_path)
                except Exception as err:
                    if feedback:
                        feedback.pushDebugInfo(f"Sidecar .qml style notice: {err}")

        return super().postProcessAlgorithm(context, feedback)
