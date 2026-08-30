# MSA: ShadowCast — 2.5D Building Shadow Vector Analysis for QGIS

[![QGIS 3.x](https://img.shields.io/badge/QGIS-3.0%2B-589632.svg?logo=qgis&logoColor=white)](https://qgis.org/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python: 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB.svg?logo=python&logoColor=white)](https://python.org/)

**MSA: ShadowCast** is a high-performance QGIS plugin and Processing algorithm designed for accurate, physically consistent 2.5D vector shadow analysis of building footprints.

Unlike naive 2D shadow extrusion tools that erroneously cast shadows across roofs of taller adjacent buildings, **MSA: ShadowCast** calculates true inter-building height relationships and generates clean, topology-validated vector layers for both **Ground Shadows** and **Roof Shadows**.

---

## 🌟 Key Features

- **Accurate 2.5D Inter-Building Occlusion:**
  - Lower buildings in front of taller buildings cast shadows onto facades without incorrectly covering higher roofs.
  - Taller buildings cast geometrically precise shadows onto lower adjacent roofs based on relative height difference ($\Delta H = H_{caster} - H_{target}$).
- **Merged Single-Polygon per Roof (No Duplicate Overlays):**
  - Shadows from multiple surrounding casters onto a single target roof are automatically dissolved into a single continuous polygon.
  - Attribute table tracks total shaded area ($m^2$), percentage of roof shaded ($0-100\%$), number of casting buildings, and list of caster IDs.
- **Clean Continuous Ground Shadows:**
  - Full ground-level shadow footprint with building basements/footprints cleanly subtracted.
- **Flexible Height / Storey Input:**
  - Supports numeric columns (`Integer`, `Double`) as well as unstructured text columns (`String`, e.g. `"3"`, `"5 kondygnacji"`, `"2,5"`, `"12.0 m"`).
  - Customizable storey-to-meter multiplier (default: $3.0\text{ m}$).
- **NOAA High-Precision Solar Engine:**
  - Automatic calculation of solar azimuth and elevation from Date, Time, and UTC Timezone offset based on layer centroid.
  - Option to manually specify solar azimuth ($0-360^\circ$) and elevation ($0-90^\circ$).
- **High Performance:**
  - Leverages `Shapely STRtree` spatial indexing to process thousands of buildings per second.

---

## 📐 Methodology

$$\vec{d}(\Delta H) = \frac{\Delta H}{\tan(\beta)} \cdot \begin{bmatrix} -\sin(\alpha) \\ -\cos(\alpha) \end{bmatrix}$$

Where:
- $\alpha$: Solar Azimuth angle ($0^\circ = \text{North}$, $90^\circ = \text{East}$, $180^\circ = \text{South}$, $270^\circ = \text{West}$)
- $\beta$: Solar Elevation angle ($0^\circ - 90^\circ$ above horizon)
- $\Delta H$: Relative height difference ($H_{caster} - H_{target}$ for roofs, or $H_{caster}$ for ground)

---

## 🚀 Installation

### Option 1: Copy to QGIS Plugins Folder
Copy the `msa_shadowcast` directory to your active QGIS profile's python plugins directory:

- **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
- **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`

Then open QGIS, go to **Plugins -> Manage and Install Plugins... -> Installed**, and enable **MSA: ShadowCast**.

---

## 🖥️ Usage

1. Open QGIS.
2. Click the **MSA: ShadowCast** icon on the Vector toolbar, or navigate to **Vector -> MSA: ShadowCast**, or find it in **Processing Toolbox -> Analiza Solarna -> MSA: ShadowCast**.
3. Configure the parameters:
   - **Input Layer:** Building polygon/multipolygon layer in a projected metric coordinate reference system (e.g., EPSG:2180 / UTM).
   - **Height Field:** Select attribute with storey count or height.
   - **Solar Parameters:** Specify Date/Time or manual Azimuth and Elevation.
4. Click **Run**.

---

## 📊 Output Layers

1. **Ground Shadows (`Cienie na gruncie`):**
   - Clean vector polygons of ground shadows excluding building footprints.
2. **Roof Shadows (`Cienie na dachach`):**
   - Merged polygons of shadow on lower roofs with fields: `target_fid`, `roof_h_m`, `roof_area_m2`, `shadow_area_m2`, `shadow_pct`, `caster_count`, `caster_fids`.
3. **Building Solar Statistics (Optional):**
   - Input building layer enriched with roof area and shade percentage metrics.

---

## 👤 Author

**Mikołaj Sazonov**  
Email: [shadowcast@sazonov.work](mailto:shadowcast@sazonov.work)  
GitHub: [@mikolajsazonov-bit](https://github.com/mikolajsazonov-bit)

---

## 📄 License

This project is licensed under the GNU General Public License v3.0 — see the [LICENSE](LICENSE) file for details.
