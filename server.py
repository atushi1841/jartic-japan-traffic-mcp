"""MCP server for JARTIC Japan traffic volume API.

Wraps the JARTIC (日本道路交通情報センター) WFS traffic data API to provide
real-time traffic volume data from ~2,600 observation points across Japan's
national highways (直轄国道).

Data source: 国土交通省 xROAD 常時観測交通量（国管理道路）
- 5-minute intervals (様式1/3) for recent data (past 1 month)
- 1-hour intervals (様式2/4) for historical data (past 3 months)
- Fixed installation counters (常設トラカン) and CCTV AI counters (CCTVトラカン)

Layer names:
  - t_travospublic_measure_5m      (様式1: 常設トラカン 5分間)
  - t_travospublic_measure_1h      (様式2: 常設トラカン 1時間)
  - t_travospublic_measure_5m_img  (様式3: CCTVトラカン 5分間)
  - t_travospublic_measure_1h_img  (様式4: CCTVトラカン 1時間)
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta, timezone

from fastmcp import FastMCP

JST = timezone(timedelta(hours=9))
API_URL = "https://api.jartic-open-traffic.org/geoserver"

# Layer constants (様式1-4 from JARTIC API spec)
LAYER_5M_FIXED = "t_travospublic_measure_5m"       # 常設トラカン 5分
LAYER_1H_FIXED = "t_travospublic_measure_1h"       # 常設トラカン 1時間
LAYER_5M_CCTV = "t_travospublic_measure_5m_img"    # CCTVトラカン 5分
LAYER_1H_CCTV = "t_travospublic_measure_1h_img"    # CCTVトラカン 1時間

LAYER_MAP = {
    "5m_fixed": LAYER_5M_FIXED,
    "1h_fixed": LAYER_1H_FIXED,
    "5m_cctv": LAYER_5M_CCTV,
    "1h_cctv": LAYER_1H_CCTV,
}

mcp = FastMCP("jartic-japan-traffic")


def _build_cql_filter(
    layer: str,
    time_code_from: int,
    time_code_to: int,
    bbox: tuple[float, float, float, float],
    road_type: str = "3",
) -> str:
    """Build CQL filter string for JARTIC WFS API.

    Args:
        layer: WFS layer name (様式1-4)
        time_code_from: Start time code YYYYMMDDHHmm as integer
        time_code_to: End time code YYYYMMDDHHmm as integer
        bbox: (min_lon, min_lat, max_lon, max_lat) in WGS84
        road_type: Road type code ("1"=高速, "3"=一般国道, default="3")
    Returns:
        CQL filter string
    """
    min_x, min_y, max_x, max_y = bbox
    return (
        f'道路種別 = {road_type} AND '
        f'時間コード >= {time_code_from} AND '
        f'時間コード <= {time_code_to} AND '
        f"BBOX(ジオメトリ,{min_x},{min_y},{max_x},{max_y},'EPSG:4326')"
    )


def _fetch_traffic(
    layer: str,
    time_code_from: int,
    time_code_to: int,
    bbox: tuple[float, float, float, float],
    limit: int = 100,
    road_type: str = "3",
) -> Dict[str, Any]:
    """Fetch traffic data from JARTIC WFS API.

    Args:
        layer: WFS layer name
        time_code_from: Start time code
        time_code_to: End time code
        bbox: (min_lon, min_lat, max_lon, max_lat)
        limit: Max features to return
        road_type: Road type filter

    Returns:
        Dict with features and metadata
    """
    cql = _build_cql_filter(layer, time_code_from, time_code_to, bbox, road_type)
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": layer,
        "srsName": "EPSG:4326",
        "outputFormat": "application/json",
        "exceptions": "application/json",
        "count": str(limit),
        "cql_filter": cql,
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
        features = data.get("features", [])
        return {
            "layer": layer,
            "count": len(features),
            "total_features": data.get("totalFeatures", len(features)),
            "bbox": bbox,
            "time_range": [time_code_from, time_code_to],
            "features": features,
        }
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace") if hasattr(e, "read") else ""
        return {"error": f"HTTP {e.code}", "message": body[:500], "layer": layer}
    except Exception as e:
        return {"error": type(e).__name__, "message": str(e), "layer": layer}


def _parse_properties(props: Dict[str, Any]) -> Dict[str, Any]:
    """Parse JARTIC traffic data properties into clean structure."""
    return {
        "station_code": props.get("常時観測点コード"),
        "district_code": props.get("地方整備局等番号"),
        "observation_date": props.get("観測年月日"),
        "time_slot": props.get("時間帯"),
        "time_code": props.get("時間コード"),
        "measurement_type": props.get("収集時間フラグ（5分間／1時間）"),
        "road_type": props.get("道路種別"),
        "upbound": {
            "small": props.get("上り・小型交通量", 0),
            "large": props.get("上り・大型交通量", 0),
            "unknown": props.get("上り・車種判別不能交通量", 0),
            "total": (props.get("上り・小型交通量") or 0) +
                     (props.get("上り・大型交通量") or 0) +
                     (props.get("上り・車種判別不能交通量") or 0),
            "outage": props.get("上り・停電") == "1",
            "loop_error": props.get("上り・ループ異常") == "1",
            "ultrasonic_error": props.get("上り・超音波異常") == "1",
            "missing": props.get("上り・欠測") == "1",
        },
        "downbound": {
            "small": props.get("下り・小型交通量", 0),
            "large": props.get("下り・大型交通量", 0),
            "unknown": props.get("下り・車種判別不能交通量", 0),
            "total": (props.get("下り・小型交通量") or 0) +
                     (props.get("下り・大型交通量") or 0) +
                     (props.get("下り・車種判別不能交通量") or 0),
            "outage": props.get("下り・停電") == "1",
            "loop_error": props.get("下り・ループ異常") == "1",
            "ultrasonic_error": props.get("下り・超音波異常") == "1",
            "missing": props.get("下り・欠測") == "1",
        },
        "geometry": props.get("ジオメトリ"),
    }


@mcp.tool()
async def get_traffic(
    layer: str = "1h_fixed",
    lat_min: float = 35.5,
    lon_min: float = 139.5,
    lat_max: float = 35.8,
    lon_max: float = 140.0,
    hours_back: int = 24,
    limit: int = 50,
) -> Dict[str, Any]:
    """Query JARTIC traffic volume data for a bounding box.

    Returns traffic counts (小型/大型/判別不能) by direction (上り/下り)
    from ~2,600 observation points across Japan's national highways.

    Args:
        layer: Data type - "5m_fixed" (様式1), "1h_fixed" (様式2, default),
               "5m_cctv" (様式3), "1h_cctv" (様式4)
        lat_min: Southern latitude bound (default 35.5 = Tokyo area)
        lon_min: Western longitude bound (default 139.5 = Tokyo area)
        lat_max: Northern latitude bound (default 35.8)
        lon_max: Eastern longitude bound (default 140.0)
        hours_back: How many hours back to query (default 24)
        limit: Max features to return (default 50)

    Returns:
        Traffic data with station details, vehicle counts, and status flags
    """
    now_jst = datetime.now(JST)
    time_from = now_jst - timedelta(hours=hours_back)

    # Convert to time codes (YYYYMMDDHHmm)
    tc_from = int(time_from.strftime("%Y%m%d%H%M"))
    tc_to = int(now_jst.strftime("%Y%m%d%H%M"))

    layer_name = LAYER_MAP.get(layer, LAYER_1H_FIXED)
    bbox = (lon_min, lat_min, lon_max, lat_max)

    result = _fetch_traffic(layer_name, tc_from, tc_to, bbox, limit)

    if "error" in result:
        return result

    # Parse features
    parsed = []
    for feature in result.get("features", [])[:limit]:
        props = feature.get("properties", {})
        geometry = feature.get("geometry", {})
        coords = geometry.get("coordinates", [[]])
        point = coords[0] if coords else []

        parsed.append({
            **_parse_properties(props),
            "longitude": point[0] if len(point) >= 1 else None,
            "latitude": point[1] if len(point) >= 2 else None,
            "geometry_type": geometry.get("type"),
        })

    return {
        **result,
        "parsed_features": parsed,
        "query_time": now_jst.isoformat(),
    }


@mcp.tool()
async def get_traffic_station(
    station_code: int,
    hours_back: int = 24,
    limit: int = 100,
) -> Dict[str, Any]:
    """Query traffic data for a specific observation station.

    Args:
        station_code: 常時観測点コード (e.g., 3110010 for Tokyo area)
        hours_back: How many hours back (default 24)
        limit: Max records (default 100)

    Returns:
        Time series of traffic counts for the station
    """
    now_jst = datetime.now(JST)
    time_from = now_jst - timedelta(hours=hours_back)
    tc_from = int(time_from.strftime("%Y%m%d%H%M"))
    tc_to = int(now_jst.strftime("%Y%m%d%H%M"))

    # Query with station code filter
    cql = (
        f'道路種別 = 3 AND '
        f'時間コード >= {tc_from} AND '
        f'時間コード <= {tc_to} AND '
        f'常時観測点コード = {station_code}'
    )
    params = {
        "service": "WFS", "version": "2.0.0", "request": "GetFeature",
        "typeNames": LAYER_1H_FIXED, "srsName": "EPSG:4326",
        "outputFormat": "application/json", "exceptions": "application/json",
        "count": str(limit), "cql_filter": cql,
    }
    url = API_URL + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
        features = data.get("features", [])

        parsed = []
        for feature in features[:limit]:
            props = feature.get("properties", {})
            geometry = feature.get("geometry", {})
            coords = geometry.get("coordinates", [[]])
            point = coords[0] if coords else []
            parsed.append({
                **_parse_properties(props),
                "longitude": point[0] if len(point) >= 1 else None,
                "latitude": point[1] if len(point) >= 2 else None,
            })

        return {
            "station_code": station_code,
            "count": len(parsed),
            "total_features": data.get("totalFeatures", len(parsed)),
            "query_time": now_jst.isoformat(),
            "features": parsed,
        }
    except Exception as e:
        return {"error": type(e).__name__, "message": str(e), "station_code": station_code}


@mcp.tool()
async def get_layer_info() -> Dict[str, Any]:
    """Get information about available JARTIC traffic data layers.

    Returns:
        Layer metadata including names, descriptions, and data availability
    """
    return {
        "layers": {
            "5m_fixed": {
                "name": LAYER_5M_FIXED,
                "description": "常設トラカン 5分間交通量 (様式1)",
                "interval": "5 minutes",
                "retention": "Past 1 month",
                "latency": "~20 minutes after observation",
            },
            "1h_fixed": {
                "name": LAYER_1H_FIXED,
                "description": "常設トラカン 1時間交通量 (様式2)",
                "interval": "1 hour",
                "retention": "Past 3 months",
                "latency": "~20 minutes after each hour",
            },
            "5m_cctv": {
                "name": LAYER_5M_CCTV,
                "description": "CCTVトラカン 5分間交通量 (様式3)",
                "interval": "5 minutes",
                "retention": "Past 1 month",
                "latency": "~20 minutes after observation",
            },
            "1h_cctv": {
                "name": LAYER_1H_CCTV,
                "description": "CCTVトラカン 1時間交通量 (様式4)",
                "interval": "1 hour",
                "retention": "Past 3 months",
                "latency": "~20 minutes after each hour",
            },
        },
        "road_types": {
            "1": "高速自動車国道",
            "3": "一般国道 (default)",
        },
        "source": "国土交通省 xROAD 常時観測交通量（国管理道路）",
        "api_url": API_URL,
        "documentation": "https://www.jartic-open-traffic.org/",
    }


if __name__ == "__main__":
    mcp.run()
