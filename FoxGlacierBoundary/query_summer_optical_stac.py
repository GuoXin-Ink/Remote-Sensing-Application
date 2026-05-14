#!/usr/bin/env python3
"""Search summer optical imagery (Sentinel-2 L2A, optional Landsat L2) over Fox Glacier OSM boundary.

Uses the **Microsoft Planetary Computer** public STAC API by default:
  - **No account is required** for catalog search and moderate use.
  - Optional ``PC_SDK_SUBSCRIPTION_KEY`` (free subscription) improves rate limits; set it in
    the environment or in a ``.env`` file next to this script.

Credentials are **never** hard-coded; use env vars or interactive prompts (see ``--prompt-key``).

Examples
--------
  python query_summer_optical_stac.py
  python query_summer_optical_stac.py --year 2023 --max-cloud 30 --limit 20
  PC_SDK_SUBSCRIPTION_KEY=... python query_summer_optical_stac.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parent
GEOJSON = ROOT / "fox_glacier_from_osm.geojson"

STAC_PC = "https://planetarycomputer.microsoft.com/api/stac/v1"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = ROOT / ".env"
    if env_path.is_file():
        load_dotenv(env_path)


def _iter_lonlat_pairs(coords: Any) -> Iterator[tuple[float, float]]:
    """Yield (lon, lat) from nested GeoJSON coordinate lists."""
    if isinstance(coords, (int, float)):
        return
    if isinstance(coords, list):
        if len(coords) >= 2 and all(isinstance(x, (int, float)) for x in coords[:2]):
            yield float(coords[0]), float(coords[1])
            return
        for part in coords:
            yield from _iter_lonlat_pairs(part)


def bbox_from_geojson(path: Path, buffer_deg: float) -> tuple[float, float, float, float]:
    """Return STAC bbox (minx, miny, maxx, maxy) in WGS84 lon/lat."""
    data = json.loads(path.read_text(encoding="utf-8"))
    feats = data.get("features") or []
    if not feats:
        raise ValueError("GeoJSON has no features")
    lons: list[float] = []
    lats: list[float] = []
    for feat in feats:
        geom = feat.get("geometry") or {}
        for lon, lat in _iter_lonlat_pairs(geom.get("coordinates")):
            lons.append(lon)
            lats.append(lat)
    if not lons:
        raise ValueError("No coordinates found in GeoJSON")
    minx, maxx = min(lons), max(lons)
    miny, maxy = min(lats), max(lats)
    return (
        minx - buffer_deg,
        miny - buffer_deg,
        maxx + buffer_deg,
        maxy + buffer_deg,
    )


def southern_summer_range(year: int) -> str:
    """Austral summer window: Dec 1 (year) .. Feb 28/29 (year+1) as STAC datetime string."""
    y2 = year + 1
    feb_last = 29 if (y2 % 4 == 0 and (y2 % 100 != 0 or y2 % 400 == 0)) else 28
    return f"{year}-12-01T00:00:00Z/{y2}-02-{feb_last}T23:59:59Z"


def _maybe_prompt_pc_key() -> None:
    if os.environ.get("PC_SDK_SUBSCRIPTION_KEY"):
        return
    if not sys.stdin.isatty():
        return
    print(
        "\nOptional: Planetary Computer subscription key (free) — improves rate limits.\n"
        "Press Enter to skip and continue anonymously.\n"
        "Or set PC_SDK_SUBSCRIPTION_KEY in your environment / .env file.\n"
    )
    try:
        key = input("PC_SDK_SUBSCRIPTION_KEY: ").strip()
    except EOFError:
        return
    if key:
        os.environ["PC_SDK_SUBSCRIPTION_KEY"] = key


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--geojson", type=Path, default=GEOJSON, help="Glacier boundary GeoJSON")
    parser.add_argument("--year", type=int, default=2024, help="Dec–Feb summer spans year -> year+1")
    parser.add_argument("--max-cloud", type=float, default=40.0, help="Max eo:cloud_cover (percent)")
    parser.add_argument("--limit", type=int, default=40, help="Max items per collection")
    parser.add_argument("--buffer-deg", type=float, default=0.02, help="BBox padding in degrees (~2 km)")
    parser.add_argument(
        "--collection",
        choices=("sentinel-2-l2a", "landsat-c2-l2", "both"),
        default="sentinel-2-l2a",
        help="STAC collection id on Planetary Computer",
    )
    parser.add_argument(
        "--prompt-key",
        action="store_true",
        help="If no PC_SDK_SUBSCRIPTION_KEY, interactively ask once (TTY only)",
    )
    args = parser.parse_args()

    _load_dotenv()
    if args.prompt_key:
        _maybe_prompt_pc_key()

    bbox = bbox_from_geojson(args.geojson, args.buffer_deg)
    dt = southern_summer_range(args.year)

    try:
        from pystac_client import Client
        import planetary_computer
    except ImportError as e:
        raise SystemExit(
            "Missing dependencies. Install with:\n"
            f"  pip install -r {ROOT / 'requirements.txt'}\n"
            f"Original error: {e}"
        ) from e

    catalog = Client.open(STAC_PC, modifier=planetary_computer.sign_inplace)

    collections: list[str]
    if args.collection == "both":
        collections = ["sentinel-2-l2a", "landsat-c2-l2"]
    else:
        collections = [args.collection]

    print(f"STAC: {STAC_PC}")
    print(f"BBox (minx, miny, maxx, maxy): {bbox}")
    print(f"Datetime (southern summer): {dt}")
    print(f"Collections: {collections}")
    print(f"PC_SDK_SUBSCRIPTION_KEY set: {bool(os.environ.get('PC_SDK_SUBSCRIPTION_KEY'))}")
    print()

    for coll in collections:
        search = catalog.search(
            collections=[coll],
            bbox=bbox,
            datetime=dt,
            query={"eo:cloud_cover": {"lt": args.max_cloud}},
            sortby=[{"field": "datetime", "direction": "asc"}],
            max_items=args.limit,
        )
        print(f"=== {coll} (up to {args.limit} items, cloud < {args.max_cloud}) ===")
        n = 0
        for item in search.items():
            n += 1
            props = item.properties
            cc = props.get("eo:cloud_cover", "n/a")
            dt0 = props.get("datetime", item.datetime)
            sid = item.id
            print(f"  {n:3d}  {dt0}  cloud={cc}  id={sid}")
        if n == 0:
            print("  (no items — try looser --max-cloud, wider --buffer-deg, or another --year)")
        print()


if __name__ == "__main__":
    main()
