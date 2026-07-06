"""
UrbanCool AI — Phase 1: OSMnx Data Collection Module
backend/src/data_collection/osm_collector.py

Strategy (2-tier):
  Tier 1 — Direct Overpass QL via requests.post()
    Bypasses OSMnx's buggy _get_overpass_pause() completely.
    Tries 5 public Overpass endpoints until one responds.

  Tier 2 — Geofabrik PBF download + pyrosm
    Downloads Gujarat OSM extract (~130 MB) from Geofabrik CDN.
    Parsed locally with pyrosm; no API dependency at all.

Output GeoJSONs:
  data/raw/osm_roads.geojson
  data/raw/osm_buildings.geojson
  data/raw/osm_water.geojson
  data/raw/osm_greenspace.geojson
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import LineString, Point, Polygon, MultiPolygon

log = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

# ── Ahmedabad bounding box (S, W, N, E) — Overpass QL convention ─────────────
BBOX_SWNE = "22.87,72.46,23.13,72.72"   # for [bbox:S,W,N,E] in QL
BBOX_NSEW = (23.13, 22.87, 72.72, 72.46)  # (N, S, E, W) for pyrosm clip

# ── Overpass API mirrors (maps.mail.ru confirmed reachable — always first) ────
OVERPASS_ENDPOINTS = [
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",  # ✅ CONFIRMED OK
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
]

# ── Geofabrik fallback ────────────────────────────────────────────────────────
GEOFABRIK_URL = "https://download.geofabrik.de/asia/india/gujarat-latest.osm.pbf"
PBF_PATH      = RAW_DIR / "gujarat-latest.osm.pbf"

# ── Overpass QL templates ─────────────────────────────────────────────────────
QL_ROADS = f"""
[out:json][timeout:180][bbox:{BBOX_SWNE}];
(
  way["highway"]["highway"!~"^(footway|path|steps|pedestrian|cycleway|track|service)$"];
);
out geom;
"""

QL_BUILDINGS = f"""
[out:json][timeout:180][bbox:{BBOX_SWNE}];
(
  way["building"];
  relation["building"]["type"="multipolygon"];
);
out geom;
"""

QL_WATER = f"""
[out:json][timeout:180][bbox:{BBOX_SWNE}];
(
  way["natural"~"^(water|wetland)$"];
  way["waterway"~"^(river|canal|stream)$"];
  way["landuse"="reservoir"];
  relation["natural"="water"]["type"="multipolygon"];
);
out geom;
"""

QL_GREEN = f"""
[out:json][timeout:180][bbox:{BBOX_SWNE}];
(
  way["leisure"~"^(park|garden|recreation_ground)$"];
  way["landuse"~"^(grass|forest|meadow|village_green)$"];
  relation["leisure"~"^(park|garden|recreation_ground)$"]["type"="multipolygon"];
);
out geom;
"""


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 1 — Direct Overpass QL via requests
# ═══════════════════════════════════════════════════════════════════════════════

def _post_overpass(ql: str, timeout: int = 200) -> dict[str, Any]:
    """
    POST a raw Overpass QL query, cycling through all known mirrors.
    Returns the parsed JSON dict on first success.
    Raises RuntimeError if all mirrors fail.
    """
    last_exc: Exception | None = None
    for url in OVERPASS_ENDPOINTS:
        try:
            log.info("Querying Overpass: %s ...", url)
            resp = requests.post(
                url,
                data={"data": ql},
                timeout=timeout,
                headers={"Accept-Encoding": "gzip, deflate"},
            )
            resp.raise_for_status()
            data = resp.json()
            elem_count = len(data.get("elements", []))
            log.info("  Got %d elements from %s", elem_count, url)
            return data
        except Exception as exc:
            log.warning("  Endpoint %s failed (%s: %s)", url, type(exc).__name__, exc)
            last_exc = exc
            time.sleep(2)          # brief pause before next mirror

    raise RuntimeError(
        f"All {len(OVERPASS_ENDPOINTS)} Overpass endpoints failed. "
        f"Last error: {last_exc}"
    ) from last_exc


def _way_to_geometry(elem: dict):
    """
    Convert an Overpass 'way' element (with geometry key) to a Shapely geometry.
    Returns Polygon if ring is closed, LineString otherwise.
    """
    if "geometry" not in elem or len(elem["geometry"]) < 2:
        return None
    coords = [(pt["lon"], pt["lat"]) for pt in elem["geometry"]]
    if len(coords) >= 4 and coords[0] == coords[-1]:
        try:
            return Polygon(coords)
        except Exception:
            return LineString(coords)
    return LineString(coords)


def _overpass_json_to_gdf(
    data: dict,
    keep_tags: list[str] | None = None,
    geom_filter: str | None = None,    # "polygon" | "line" | None
) -> gpd.GeoDataFrame:
    """
    Parse an Overpass JSON response into a GeoDataFrame (EPSG:4326).

    Parameters
    ----------
    data        : Parsed Overpass JSON dict.
    keep_tags   : Tag keys to retain as columns (None = all tags).
    geom_filter : 'polygon'/'line' to filter by geometry type, None = keep all.
    """
    rows = []
    for elem in data.get("elements", []):
        if elem["type"] != "way":
            continue
        geom = _way_to_geometry(elem)
        if geom is None or geom.is_empty:
            continue
        if geom_filter == "polygon" and not isinstance(geom, Polygon):
            continue
        if geom_filter == "line" and not isinstance(geom, LineString):
            continue

        tags = elem.get("tags", {})
        row: dict[str, Any] = {"osmid": elem["id"], "geometry": geom}
        if keep_tags is None:
            row.update(tags)
        else:
            for k in keep_tags:
                row[k] = tags.get(k)
        rows.append(row)

    if not rows:
        log.warning("No features parsed from Overpass response.")
        return gpd.GeoDataFrame(columns=["osmid", "geometry"],
                                geometry="geometry", crs="EPSG:4326")

    gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")
    # Coerce all tag columns to str to avoid Fiona serialisation issues
    for col in gdf.columns:
        if col == "geometry":
            continue
        gdf[col] = gdf[col].astype(str).replace("None", None)
    log.info("Parsed %d features into GeoDataFrame.", len(gdf))
    return gdf


# ═══════════════════════════════════════════════════════════════════════════════
# TIER 2 — Geofabrik PBF download + pyrosm
# ═══════════════════════════════════════════════════════════════════════════════

def _download_geofabrik_pbf() -> Path:
    """
    Download Gujarat OSM PBF from Geofabrik if not already cached.
    Shows a progress bar; file is ~130 MB.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if PBF_PATH.exists():
        log.info("PBF already cached at %s — skipping download.", PBF_PATH)
        return PBF_PATH

    log.info("Downloading Gujarat PBF from Geofabrik (~130 MB) ...")
    log.info("URL: %s", GEOFABRIK_URL)

    resp = requests.get(GEOFABRIK_URL, stream=True, timeout=300)
    resp.raise_for_status()
    total = int(resp.headers.get("content-length", 0))
    downloaded = 0
    with open(PBF_PATH, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1 << 20):  # 1 MB chunks
            fh.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = downloaded / total * 100
                log.info("  %.1f%% (%d / %d MB)", pct,
                         downloaded >> 20, total >> 20)
    log.info("PBF saved to %s", PBF_PATH)
    return PBF_PATH


def _pbf_roads(pbf_path: Path) -> gpd.GeoDataFrame:
    import pyrosm
    n, s, e, w = BBOX_NSEW
    osm = pyrosm.OSM(str(pbf_path), bounding_box=[w, s, e, n])
    roads = osm.get_network(network_type="driving+walking")
    if roads is None or roads.empty:
        return gpd.GeoDataFrame(columns=["osmid", "highway", "name",
                                          "length", "geometry"],
                                geometry="geometry", crs="EPSG:4326")
    keep = [c for c in ["id", "highway", "name", "geometry"] if c in roads.columns]
    roads = roads[keep].rename(columns={"id": "osmid"})
    return roads.to_crs(epsg=4326)


def _pbf_buildings(pbf_path: Path) -> gpd.GeoDataFrame:
    import pyrosm
    n, s, e, w = BBOX_NSEW
    osm = pyrosm.OSM(str(pbf_path), bounding_box=[w, s, e, n])
    bldgs = osm.get_buildings()
    if bldgs is None or bldgs.empty:
        return gpd.GeoDataFrame(columns=["osmid", "building", "geometry"],
                                geometry="geometry", crs="EPSG:4326")
    keep = [c for c in ["id", "building", "name", "geometry"] if c in bldgs.columns]
    bldgs = bldgs[keep].rename(columns={"id": "osmid"})
    bldgs_utm = bldgs.to_crs(epsg=32643)
    bldgs["area_m2"] = bldgs_utm.geometry.area.round(1)
    return bldgs.to_crs(epsg=4326)


def _pbf_natural(pbf_path: Path, tag_filter: dict) -> gpd.GeoDataFrame:
    import pyrosm
    n, s, e, w = BBOX_NSEW
    osm = pyrosm.OSM(str(pbf_path), bounding_box=[w, s, e, n])
    feats = osm.get_natural(custom_filter=tag_filter)
    if feats is None or feats.empty:
        return gpd.GeoDataFrame(columns=["osmid", "geometry"],
                                geometry="geometry", crs="EPSG:4326")
    keep = [c for c in ["id", "natural", "waterway", "landuse",
                         "leisure", "name", "geometry"] if c in feats.columns]
    feats = feats[keep].rename(columns={"id": "osmid"})
    return feats.to_crs(epsg=4326)


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API — tries Tier 1, falls back to Tier 2
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_raw_dir() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def fetch_road_network(save: bool = True) -> gpd.GeoDataFrame:
    """
    Download the Ahmedabad road network.

    Tier 1: Direct Overpass QL POST (no OSMnx).
    Tier 2: Geofabrik PBF + pyrosm.

    Saved to: data/raw/osm_roads.geojson
    """
    log.info("Fetching road network ...")

    # ── Tier 1 ────────────────────────────────────────────────────────────────
    try:
        data = _post_overpass(QL_ROADS)
        roads = _overpass_json_to_gdf(
            data,
            keep_tags=["highway", "name"],
            geom_filter=None,
        )
        # Compute length in metres
        roads_utm = roads.to_crs(epsg=32643)
        roads["length_m"] = roads_utm.geometry.length.round(1)
        log.info("Tier 1 road network: %d features", len(roads))
    except Exception as exc:
        log.warning("Tier 1 failed (%s). Falling back to Geofabrik PBF ...", exc)
        pbf = _download_geofabrik_pbf()
        roads = _pbf_roads(pbf)
        log.info("Tier 2 road network: %d features", len(roads))

    if save:
        _ensure_raw_dir()
        out = RAW_DIR / "osm_roads.geojson"
        roads.to_file(out, driver="GeoJSON")
        log.info("Saved -> %s", out)

    return roads


def fetch_building_footprints(save: bool = True) -> gpd.GeoDataFrame:
    """
    Download building footprints.

    Saved to: data/raw/osm_buildings.geojson
    """
    log.info("Fetching building footprints ...")

    try:
        data = _post_overpass(QL_BUILDINGS)
        buildings = _overpass_json_to_gdf(data, keep_tags=["building", "name"],
                                           geom_filter="polygon")
        bldgs_utm = buildings.to_crs(epsg=32643)
        buildings["area_m2"] = bldgs_utm.geometry.area.round(1)
        log.info("Tier 1 buildings: %d features", len(buildings))
    except Exception as exc:
        log.warning("Tier 1 failed (%s). Falling back to Geofabrik PBF ...", exc)
        pbf = _download_geofabrik_pbf()
        buildings = _pbf_buildings(pbf)
        log.info("Tier 2 buildings: %d features", len(buildings))

    if save:
        _ensure_raw_dir()
        out = RAW_DIR / "osm_buildings.geojson"
        buildings.to_file(out, driver="GeoJSON")
        log.info("Saved -> %s", out)

    return buildings


def fetch_water_bodies(save: bool = True) -> gpd.GeoDataFrame:
    """
    Download water bodies (rivers, canals, lakes, reservoirs).

    Saved to: data/raw/osm_water.geojson
    """
    log.info("Fetching water bodies ...")

    try:
        data = _post_overpass(QL_WATER)
        water = _overpass_json_to_gdf(data,
                                       keep_tags=["natural", "waterway",
                                                   "landuse", "name"])
        log.info("Tier 1 water: %d features", len(water))
    except Exception as exc:
        log.warning("Tier 1 failed (%s). Falling back to Geofabrik PBF ...", exc)
        pbf = _download_geofabrik_pbf()
        water = _pbf_natural(pbf, {"natural": ["water", "wetland"],
                                    "waterway": ["river", "canal", "stream"]})
        log.info("Tier 2 water: %d features", len(water))

    if save:
        _ensure_raw_dir()
        out = RAW_DIR / "osm_water.geojson"
        water.to_file(out, driver="GeoJSON")
        log.info("Saved -> %s", out)

    return water


def fetch_green_spaces(save: bool = True) -> gpd.GeoDataFrame:
    """
    Download parks and green spaces.

    Saved to: data/raw/osm_greenspace.geojson
    """
    log.info("Fetching green spaces ...")

    try:
        data = _post_overpass(QL_GREEN)
        green = _overpass_json_to_gdf(data,
                                       keep_tags=["leisure", "landuse", "name"],
                                       geom_filter="polygon")
        log.info("Tier 1 green spaces: %d features", len(green))
    except Exception as exc:
        log.warning("Tier 1 failed (%s). Falling back to Geofabrik PBF ...", exc)
        pbf = _download_geofabrik_pbf()
        green = _pbf_natural(pbf, {"leisure": ["park", "garden",
                                                "recreation_ground"],
                                    "landuse": ["grass", "forest",
                                                "meadow", "village_green"]})
        log.info("Tier 2 green spaces: %d features", len(green))

    if save:
        _ensure_raw_dir()
        out = RAW_DIR / "osm_greenspace.geojson"
        green.to_file(out, driver="GeoJSON")
        log.info("Saved -> %s", out)

    return green


def fetch_all_osm_layers() -> dict[str, gpd.GeoDataFrame]:
    """
    Download all four OSM layers. Returns a dict of GeoDataFrames.
    """
    layers: dict[str, gpd.GeoDataFrame] = {}
    layers["roads"]      = fetch_road_network()
    layers["buildings"]  = fetch_building_footprints()
    layers["water"]      = fetch_water_bodies()
    layers["greenspace"] = fetch_green_spaces()
    log.info("All OSM layers fetched successfully.")
    return layers


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s | %(levelname)-8s | %(message)s")
    layers = fetch_all_osm_layers()
    for name, gdf in layers.items():
        print(f"{name}: {len(gdf)} features | CRS: {gdf.crs}")
