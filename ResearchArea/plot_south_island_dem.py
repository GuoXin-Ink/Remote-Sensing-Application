"""South Island overview (DEM) + Fox Glacier inset with satellite web tiles (right panel).

Uses Esri World Imagery via contextily (same family of XYZ tiles as common map apps).
Tiles arrive in Web Mercator (EPSG:3857); they are gdalwarped to WGS84 bounds identical
to ``FOX_REGION``. The right panel is drawn with :meth:`pygmt.Figure.grdimage` (not
``image``): GMT's ``image`` module places geographic GeoTIFFs with a *linear* lon/lat
plot, which does not match ``-JM`` used by ``basemap``; ``grdimage`` reprojects the
raster into the map projection and matches the frame.

``FOX_REGION`` must match the dashed rectangle drawn on the overview map (single source
of truth for connectors and panel B).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pygmt


def ensure_conda_env_runtime() -> None:
    """Make CLI tools and PROJ/GDAL data dirs resolve without ``conda activate`` (typical in Jupyter)."""
    bindir = Path(sys.executable).resolve().parent
    prefix = bindir.parent
    path = os.environ.get("PATH", "")
    bd = str(bindir)
    if bd not in path.split(os.pathsep):
        os.environ["PATH"] = bd + os.pathsep + path
    proj = prefix / "share" / "proj"
    if proj.is_dir():
        os.environ.setdefault("PROJ_DATA", str(proj))
        os.environ.setdefault("PROJ_LIB", str(proj))
    gdal_data = prefix / "share" / "gdal"
    if gdal_data.is_dir():
        os.environ.setdefault("GDAL_DATA", str(gdal_data))


ensure_conda_env_runtime()

ROOT = Path(__file__).resolve().parent

# --- Regional map (overview, DEM) -------------------------------------------
R_LEFT = [166.0, 174.5, -47.5, -40.3]
J_LEFT = "M15c"

# --- Fox Glacier inset (must match dashed box on overview: fx/fy below) -------
FOX_W, FOX_E, FOX_S, FOX_N = 170.0, 170.2, -43.62, -43.42
FOX_REGION = [FOX_W, FOX_E, FOX_S, FOX_N]
FOX_RAW_TIF = ROOT / "fox_basemap_raw.tif"
FOX_PLOT_TIF = ROOT / "fox_basemap_plot.tif"
TILE_ZOOM = 14

GAP_CM = 0.45
BOX_TR = (FOX_E, FOX_N)
BOX_BR = (FOX_E, FOX_S)

LABEL_PAD_X_FRAC = 0.015
LABEL_PAD_Y_FRAC = 0.017

FOX_GL_RNG_W, FOX_GL_RNG_E = 170.06, 170.167
FOX_GL_RNG_S, FOX_GL_RNG_N = -43.56, -43.48

LEFT_FONT_ANNOT = "10p"
LEFT_MAP_SCALE = "jBR+w200k+o0.65c/0.75c"
LEFT_ROSE = "jTL+w1.55c+l"
RIGHT_MAP_SCALE = "jBR+w2k+o0.65c/0.75c"
RIGHT_ROSE_WHITE = "jTL+w1.55c+l+p1p,white"

BASEMAP_CREDIT_FILL = "gray@25"
BASEMAP_CREDIT_CLEARANCE = "0.14c"
BASEMAP_CREDIT_BOX_PEN = "0.2p,#d8d8d0"

OUT_PNG = ROOT / "south_island_dem.png"
CPT_L = ROOT / "south_island_relief.cpt"
NC_L = ROOT / "south_island_intensity.nc"

LABEL_PANEL = "18p,Helvetica-Bold,black"


def panel_label_corner_lon_lat(region: list[float]) -> tuple[float, float]:
    """Lower-left style inset for panel letters A/B (fraction of span from SW corner)."""
    w, e, s, n = region[0], region[1], region[2], region[3]
    lon = w + LABEL_PAD_X_FRAC * (e - w)
    lat = s + LABEL_PAD_Y_FRAC * (n - s)
    return lon, lat


def _rstr(r: list[float]) -> str:
    return "/".join(map(str, r))


def map_dims_cm(region: list[float], projection: str) -> tuple[float, float]:
    out = subprocess.run(
        ["gmt", "mapproject", "-R" + _rstr(region), "-J" + projection, "-W"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return float(out[0]), float(out[1])


def mapproject_cm(lon: float, lat: float, region: list[float], projection: str) -> tuple[float, float]:
    out = subprocess.run(
        ["gmt", "mapproject", "-R" + _rstr(region), "-J" + projection],
        input=f"{lon} {lat}\n",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()
    return float(out[0]), float(out[1])


def mercator_J_matching_height(region: list[float], target_h_cm: float, tol: float = 0.02) -> tuple[str, float, float]:
    lo, hi = 1.0, 120.0
    mid = 15.0
    for _ in range(56):
        mid = (lo + hi) / 2
        w_cm, h_cm = map_dims_cm(region, f"M{mid}c")
        if abs(h_cm - target_h_cm) < tol:
            return f"M{mid}c", w_cm, h_cm
        if h_cm < target_h_cm:
            lo = mid
        else:
            hi = mid
    w_cm, h_cm = map_dims_cm(region, f"M{mid}c")
    return f"M{mid}c", w_cm, h_cm


def download_tile_basemap(region: list[float], path: Path, zoom: int = TILE_ZOOM) -> None:
    """Write an EPSG:3857 GeoTIFF covering ``region`` [W,E,S,N] from XYZ tiles."""
    import contextily as cx

    w, e, s, n = region[0], region[1], region[2], region[3]
    cx.bounds2raster(
        w,
        s,
        e,
        n,
        str(path),
        ll=True,
        zoom=zoom,
        source=cx.providers.Esri.WorldImagery,
    )


def warp_tiles_to_wgs84_plot_grid(src: Path, dst: Path, region: list[float]) -> None:
    """Reproject Web Mercator GeoTIFF to WGS84 exactly matching ``region``.

    The warp removes the Web-Mercator vs ``-JM`` (ellipsoidal Mercator) mismatch for
    *georeferenced* display. ``grdimage`` then projects the lon/lat grid into ``-JM``;
    ``image`` would not and is unsuitable here.
    """
    w, e, s, n = region[0], region[1], region[2], region[3]
    subprocess.run(
        [
            "gdalwarp",
            "-overwrite",
            "-t_srs",
            "EPSG:4326",
            "-te",
            str(w),
            str(s),
            str(e),
            str(n),
            "-r",
            "cubic",
            "-co",
            "COMPRESS=LZW",
            str(src),
            str(dst),
        ],
        check=True,
    )


grid_l = pygmt.datasets.load_earth_relief(resolution="30s", region=R_LEFT)
land_l = grid_l.where(grid_l >= 0)
zv = land_l.values[np.isfinite(land_l.values)]
if zv.size == 0:
    raise RuntimeError("No land pixels (overview)")
zmin, zmax = float(np.nanmin(zv)), float(np.nanmax(zv))
pygmt.makecpt(
    cmap="#ffffff,#fafafa,#f5f5f5,#ebebeb,#e2e2e2,#d8d8d8",
    series=[zmin, zmax, max((zmax - zmin) / 256, 1e-6)],
    continuous=True,
    output=str(CPT_L),
)
shade_l = pygmt.grdgradient(grid=grid_l, azimuth=315, normalize="t")
shade_l.to_netcdf(NC_L)

download_tile_basemap(FOX_REGION, FOX_RAW_TIF)
warp_tiles_to_wgs84_plot_grid(FOX_RAW_TIF, FOX_PLOT_TIF, FOX_REGION)

w1, h1 = map_dims_cm(R_LEFT, J_LEFT)
J_RIGHT, w2, h2 = mercator_J_matching_height(FOX_REGION, h1)

W = w1 + GAP_CM + w2
H = h1
y_shift_cm = 0.0

sx1, sy1 = mapproject_cm(*BOX_TR, R_LEFT, J_LEFT)
sx2, sy2 = mapproject_cm(*BOX_BR, R_LEFT, J_LEFT)
lon_w, lat_s, lat_n = FOX_REGION[0], FOX_REGION[2], FOX_REGION[3]
ex1, ey1 = mapproject_cm(lon_w, lat_n, FOX_REGION, J_RIGHT)
ex2, ey2 = mapproject_cm(lon_w, lat_s, FOX_REGION, J_RIGHT)
xg1 = w1 + GAP_CM + ex1
xg2 = w1 + GAP_CM + ex2
yg1 = y_shift_cm + ey1
yg2 = y_shift_cm + ey2

fig = pygmt.Figure()

fig.grdimage(grid=land_l, cmap=str(CPT_L), shading=shade_l, region=R_LEFT, projection=J_LEFT)
fig.coast(region=R_LEFT, projection=J_LEFT, water="#87CEEB", shorelines="0.1p,#888888")

fx = [FOX_W, FOX_E, FOX_E, FOX_W, FOX_W]
fy = [FOX_S, FOX_S, FOX_N, FOX_N, FOX_S]
fig.plot(x=fx, y=fy, pen="1.5p,black")
fig.text(x=170.10, y=-43.3, text="Fox Glacier", font="12p,Helvetica-Bold,black", justify="CB")

fig.plot(x=[172.6307], y=[-43.5321], style="c0.22c", pen="0.35p,black", fill="white")
fig.text(x=172.6307, y=-43.70, text="Christchurch", font="12p,Helvetica-Bold,black", justify="CT")

fig.text(x=167.75, y=-45.0, text="Southern Alps", font="17p,Helvetica-Bold,black", angle=52, justify="CM")
fig.text(x=168.85, y=-41.85, text="New Zealand", font="18p,Helvetica-Bold,black", justify="CM")
fig.text(x=168.85, y=-42.38, text="South Island", font="16p,Helvetica-Bold,black", justify="CM")
fig.text(x=172.6, y=-46.0, text="Pacific Ocean", font="15p,Helvetica-Bold,#003366", justify="CM")

with pygmt.config(MAP_FRAME_TYPE="plain", FONT_ANNOT_PRIMARY=LEFT_FONT_ANNOT):
    fig.basemap(
        region=R_LEFT,
        projection=J_LEFT,
        frame=["af"],
        map_scale=LEFT_MAP_SCALE,
        rose=LEFT_ROSE,
    )

lon_a, lat_a = panel_label_corner_lon_lat(R_LEFT)
fig.text(x=lon_a, y=lat_a, text="A", font=LABEL_PANEL, justify="LB")

with fig.shift_origin(xshift=f"{w1 + GAP_CM}c", yshift=f"{y_shift_cm}c"):
    fig.grdimage(grid=str(FOX_PLOT_TIF), region=FOX_REGION, projection=J_RIGHT)

    gx = [FOX_GL_RNG_W, FOX_GL_RNG_E, FOX_GL_RNG_E, FOX_GL_RNG_W, FOX_GL_RNG_W]
    gy = [FOX_GL_RNG_S, FOX_GL_RNG_S, FOX_GL_RNG_N, FOX_GL_RNG_N, FOX_GL_RNG_S]
    fig.plot(x=gx, y=gy, pen="1.5p,yellow", region=FOX_REGION, projection=J_RIGHT)
    fig.text(
        x=0.5 * (FOX_GL_RNG_W + FOX_GL_RNG_E) - 0.02,
        y=0.5 * (FOX_GL_RNG_S + FOX_GL_RNG_N) - 0.03,
        text="Fox Glacier",
        font="14p,Helvetica-Bold,yellow",
        justify="CM",
        region=FOX_REGION,
        projection=J_RIGHT,
    )

    with pygmt.config(
        MAP_FRAME_TYPE="plain",
        FONT_ANNOT_PRIMARY=LEFT_FONT_ANNOT,
        MAP_TICK_LENGTH_PRIMARY="0p",
        MAP_TICK_LENGTH_SECONDARY="0p",
    ):
        fig.basemap(
            region=FOX_REGION,
            projection=J_RIGHT,
            frame=["wsne"],
            map_scale=RIGHT_MAP_SCALE,
        )
    with pygmt.config(
        FONT_ANNOT_PRIMARY="10p,Helvetica,white",
        FONT_LABEL="10p,Helvetica-Bold,white",
        FONT_TITLE="10p,Helvetica,white",
        MAP_DEFAULT_PEN="1p,white",
        MAP_TICK_PEN_PRIMARY="0.5p,white",
        MAP_TICK_PEN_SECONDARY="0.5p,white",
        MAP_TITLE_OFFSET="0p",
    ):
        fig.basemap(region=FOX_REGION, projection=J_RIGHT, frame=["n"], rose=RIGHT_ROSE_WHITE)

    lon_b, lat_b = panel_label_corner_lon_lat(FOX_REGION)
    fig.text(x=lon_b, y=lat_b, text="B", font=LABEL_PANEL, justify="LB")
    fig.text(
        x=0.5 * (FOX_REGION[0] + FOX_REGION[1]),
        y=FOX_REGION[2] + 0.013 * (FOX_REGION[3] - FOX_REGION[2]),
        text="Basemap: Esri",
        font="16p,Helvetica,black",
        justify="CB",
        fill=BASEMAP_CREDIT_FILL,
        clearance=BASEMAP_CREDIT_CLEARANCE,
        pen=BASEMAP_CREDIT_BOX_PEN,
    )

fig.plot(
    region=[0, W, 0, H],
    projection=f"X{W}c/{H}c",
    x=[sx1, xg1, np.nan, sx2, xg2],
    y=[sy1, yg1, np.nan, sy2, yg2],
    pen="0.4p,black",
)

fig.savefig(OUT_PNG, dpi=300)

try:
    from IPython import get_ipython

    if get_ipython() is not None:
        fig.show()
except Exception:
    pass

print(OUT_PNG)
