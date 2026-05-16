#!/usr/bin/env python3
"""Streamlit app: ``autorift_scatter_demeaned_*.npz`` — speed scatter and/or velocity quiver (one layer).

``streamlit run "4. autorift_speed_scatter_app.py"``
Run from the lab folder after Part 2/3 have created the GeoTIFF/NPZ outputs.
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import base64
import math
import re

import matplotlib.colors as mcolors
import numpy as np
import plotly.express as px
import plotly.figure_factory as ff
import plotly.graph_objects as go
import rasterio
from PIL import Image
import streamlit as st

FEATURE_DIR = Path(__file__).resolve().parent
DEFAULT_BASEMAP_TIF = FEATURE_DIR / "B08_fox_2026-03-01.tif"


def _to_hex(color: str) -> str:
    """Normalize colors to ``#RRGGBB`` for Streamlit."""
    s = str(color).strip()
    if not s:
        return "#808080"
    if s.startswith("#"):
        if len(s) == 4:
            return "#" + "".join(c * 2 for c in s[1:])
        return s[:7] if len(s) >= 7 else "#808080"
    m = re.match(r"rgba?\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)", s, re.I)
    if m:
        r, g, b = (max(0, min(255, int(round(float(x))))) for x in m.groups())
        return f"#{r:02x}{g:02x}{b:02x}"
    try:
        return mcolors.to_hex(mcolors.to_rgb(s), keep_alpha=False)
    except ValueError:
        return "#808080"


COLOR_SCALES = [
    "Viridis",
    "Plasma",
    "Inferno",
    "Magma",
    "Cividis",
    "Turbo",
    "RdYlBu",
    "RdYlBu_r",
    "Spectral",
    "Spectral_r",
    "Blues",
    "Hot",
    "Gray",
]


def _load_npz(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None]:
    z = np.load(path, allow_pickle=False)
    need = {"easting_m", "northing_m", "speed_m_per_day"}
    if not need.issubset(set(z.files)):
        raise ValueError(f"NPZ must contain {need}; got {z.files}")
    east = np.asarray(z["easting_m"], dtype=float).ravel()
    north = np.asarray(z["northing_m"], dtype=float).ravel()
    spd = np.asarray(z["speed_m_per_day"], dtype=float).ravel()
    if east.size != north.size or east.size != spd.size:
        raise ValueError("easting_m, northing_m, speed_m_per_day must have the same length")
    vx = vy = None
    if "vx_m_per_day_demeaned" in z.files and "vy_m_per_day_demeaned" in z.files:
        vx = np.asarray(z["vx_m_per_day_demeaned"], dtype=float).ravel()
        vy = np.asarray(z["vy_m_per_day_demeaned"], dtype=float).ravel()
        if vx.size != east.size or vy.size != east.size:
            vx = vy = None
    return east, north, spd, vx, vy


def _load_npz_bytes(data: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray | None, np.ndarray | None]:
    z = np.load(io.BytesIO(data), allow_pickle=False)
    need = {"easting_m", "northing_m", "speed_m_per_day"}
    if not need.issubset(set(z.files)):
        raise ValueError(f"NPZ must contain {need}; got {z.files}")
    east = np.asarray(z["easting_m"], dtype=float).ravel()
    north = np.asarray(z["northing_m"], dtype=float).ravel()
    spd = np.asarray(z["speed_m_per_day"], dtype=float).ravel()
    vx = vy = None
    if "vx_m_per_day_demeaned" in z.files and "vy_m_per_day_demeaned" in z.files:
        vx = np.asarray(z["vx_m_per_day_demeaned"], dtype=float).ravel()
        vy = np.asarray(z["vy_m_per_day_demeaned"], dtype=float).ravel()
        if vx.size != east.size or vy.size != east.size:
            vx = vy = None
    return east, north, spd, vx, vy


def _plotly_colorscale(name: str, reverse: bool) -> str:
    if not reverse:
        return name
    if name.endswith("_r"):
        return name[:-2]
    return name + "_r"


def _sample_stops_from_template(template: str, n: int, reverse: bool) -> list[dict[str, str | float]]:
    tmpl = _plotly_colorscale(template, reverse)
    if n < 2:
        n = 2
    pos = np.linspace(0.0, 1.0, n).tolist()
    cols = px.colors.sample_colorscale(tmpl, [float(p) for p in pos])
    return [{"id": str(uuid.uuid4())[:10], "pos": float(p), "color": _to_hex(c)} for p, c in zip(pos, cols)]


def _normalize_stop_positions(stops: list[dict], *, min_sep: float = 0.002) -> list[dict]:
    s = sorted([{**x, "pos": float(x["pos"])} for x in stops], key=lambda x: x["pos"])
    s[0]["pos"] = 0.0
    s[-1]["pos"] = 1.0
    for i in range(1, len(s) - 1):
        lo = s[i - 1]["pos"] + min_sep
        hi = s[i + 1]["pos"] - min_sep
        s[i]["pos"] = float(min(max(s[i]["pos"], lo), hi))
    return s


def _stops_to_plotly_scale(stops: list[dict]) -> list[list]:
    s = _normalize_stop_positions(stops)
    return [[float(x["pos"]), str(x["color"])] for x in s]


def _ramp_preview_figure(plotly_scale: list[list]) -> go.Figure:
    n = 256
    xs = np.linspace(0, 1, n, dtype=float)
    z = np.linspace(0.0, 1.0, n, dtype=np.float64).reshape(1, -1)
    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=xs,
            y=[0.0],
            colorscale=plotly_scale,
            zmin=0,
            zmax=1,
            showscale=False,
            hoverinfo="skip",
        )
    )
    fig.update_layout(
        height=120,
        margin=dict(l=30, r=30, t=40, b=50),
        xaxis=dict(title="0 → 1 on color bar", range=[0, 1]),
        yaxis=dict(visible=False),
        title="Ramp preview",
        title_font_size=13,
    )
    return fig


_AXIS_BOX = dict(
    showline=True,
    linewidth=1.5,
    linecolor="rgba(0,0,0,0.65)",
    mirror=True,
    showgrid=True,
    gridcolor="rgba(0,0,0,0.1)",
    zeroline=False,
    tickfont=dict(color="#000000", size=15),
)


def _padded_extent(
    east: np.ndarray, north: np.ndarray, pad_rel: float = 0.005
) -> tuple[float, float, float, float]:
    mask = np.isfinite(east) & np.isfinite(north)
    ex = east[mask]
    ny = north[mask]
    e0, e1 = float(np.min(ex)), float(np.max(ex))
    n0, n1 = float(np.min(ny)), float(np.max(ny))
    se = max(e1 - e0, 1e-9)
    sn = max(n1 - n0, 1e-9)
    return e0 - pad_rel * se, e1 + pad_rel * se, n0 - pad_rel * sn, n1 + pad_rel * sn


def _basemap_png_uri(
    tif_path: Path,
    e0: float,
    e1: float,
    n0: float,
    n1: float,
    *,
    max_px: int = 1400,
) -> tuple[str, float, float, float, float] | None:
    if not tif_path.is_file():
        return None
    try:
        with rasterio.open(tif_path) as src:
            win = rasterio.windows.from_bounds(e0, n0, e1, n1, src.transform)
            win = win.round_offsets().intersection(rasterio.windows.Window(0, 0, src.width, src.height))
            if win.width < 1 or win.height < 1:
                return None
            arr = src.read(window=win)
            t = rasterio.windows.transform(win, src.transform)
            west, south, east, north = rasterio.transform.array_bounds(int(win.height), int(win.width), t)

            if arr.ndim == 3 and arr.shape[0] >= 3:
                r = arr[0].astype(np.float32)
                g = arr[1].astype(np.float32)
                b = arr[2].astype(np.float32)
            else:
                r = (arr[0] if arr.ndim == 3 else arr).astype(np.float32)
                g = b = r
            valid = np.isfinite(r) & (r > 0) & np.isfinite(g) & np.isfinite(b)
            if not np.any(valid):
                return None
            stack = np.stack([r, g, b], axis=-1)
            lo = float(np.percentile(stack[valid], 2))
            hi = float(np.percentile(stack[valid], 98))
            hi = max(hi, lo + 1e-6)
            u8 = np.clip((stack - lo) / (hi - lo) * 255.0, 0, 255).astype(np.uint8)
            im = Image.fromarray(u8, mode="RGB")
            im.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="PNG", optimize=True)
            uri = "data:image/png;base64," + base64.standard_b64encode(buf.getvalue()).decode("ascii")
            return uri, west, east, south, north
    except Exception:
        return None


def _apply_geo_scatter_layout(
    fig: go.Figure,
    east: np.ndarray,
    north: np.ndarray,
    *,
    base_h: int = 680,
    show_speed_colorbar: bool = True,
) -> None:
    mask = np.isfinite(east) & np.isfinite(north)
    ex = east[mask]
    ny = north[mask]
    cbar = (
        dict(
            thickness=12,
            len=0.82,
            outlinewidth=0,
            x=1.02,
            xref="paper",
            xpad=6,
            y=0.5,
            yanchor="middle",
            tickfont=dict(color="#000000", size=14),
            title=dict(text="m/day", side="right", font=dict(color="#000000", size=15)),
        )
        if show_speed_colorbar
        else None
    )
    if ex.size == 0:
        lo = dict(
            height=base_h,
            margin=dict(l=52, r=72, t=48, b=52),
            xaxis=dict(constrain="domain", title=dict(font=dict(color="#000000", size=17)), **_AXIS_BOX),
            yaxis=dict(
                constrain="domain",
                scaleanchor="x",
                scaleratio=1,
                title=dict(font=dict(color="#000000", size=17)),
                **_AXIS_BOX,
            ),
        )
        if cbar is not None:
            lo["coloraxis_colorbar"] = cbar
        fig.update_layout(**lo)
        return
    de = float(np.ptp(ex))
    dn = float(np.ptp(ny))
    if de < 1e-9:
        de = 1.0
    if dn < 1e-9:
        dn = 1.0
    ar = de / dn
    max_w, min_w = 1400, 440
    h = float(base_h)
    w = h * ar
    if w > max_w:
        w = float(max_w)
        h = max(400.0, w / ar)
    elif w < min_w:
        w = float(min_w)
        h = max(400.0, w / ar)
    wi, hi = int(round(w)), int(round(h))
    lo = dict(
        width=wi,
        height=hi,
        margin=dict(l=48, r=72, t=46, b=46),
        xaxis=dict(
            constrain="domain",
            title=dict(standoff=4, font=dict(color="#000000", size=17)),
            **_AXIS_BOX,
        ),
        yaxis=dict(
            constrain="domain",
            scaleanchor="x",
            scaleratio=1,
            title=dict(standoff=4, font=dict(color="#000000", size=17)),
            **_AXIS_BOX,
        ),
    )
    if cbar is not None:
        lo["coloraxis_colorbar"] = cbar
    fig.update_layout(**lo)
    e0, e1, n0, n1 = _padded_extent(ex, ny, 0.005)
    fig.update_xaxes(range=[e0, e1], autorange=False)
    fig.update_yaxes(range=[n0, n1], autorange=False)


def _quiver_has_finite_points(
    east: np.ndarray, north: np.ndarray, vx: np.ndarray | None, vy: np.ndarray | None
) -> bool:
    if vx is None or vy is None:
        return False
    m = np.isfinite(east) & np.isfinite(north) & np.isfinite(vx) & np.isfinite(vy)
    return bool(np.any(m))


def _make_quiver_figure(
    east: np.ndarray,
    north: np.ndarray,
    vx: np.ndarray,
    vy: np.ndarray,
    *,
    length_mult: float,
    scale: float,
    arrow_scale: float,
    angle_rad: float,
    line_width: float,
    line_color: str,
    max_arrows: int,
) -> go.Figure | None:
    m = np.isfinite(east) & np.isfinite(north) & np.isfinite(vx) & np.isfinite(vy)
    qe = east[m].astype(float)
    qn = north[m].astype(float)
    qu = vx[m].astype(float) * float(length_mult)
    qv = vy[m].astype(float) * float(length_mult)
    if qe.size == 0:
        return None
    if qe.size > max_arrows:
        rng = np.random.default_rng(0)
        pick = rng.choice(qe.size, size=max_arrows, replace=False)
        qe, qn, qu, qv = qe[pick], qn[pick], qu[pick], qv[pick]
    qfig = ff.create_quiver(
        qe,
        qn,
        qu,
        qv,
        scale=float(scale),
        arrow_scale=float(arrow_scale),
        angle=float(angle_rad),
        scaleratio=1.0,
        line=dict(width=float(line_width), color=line_color),
    )
    qfig.update_traces(showlegend=False)
    return qfig


def main() -> None:
    st.set_page_config(page_title="AutoRIFT speed scatter", layout="wide")
    st.title("AutoRIFT — speed scatter (interactive)")
    st.caption("NPZ: ``autorift_scatter_demeaned_*.npz``. Scatter or quiver (not both). Stretch = m/day at color bar ends; custom ramp = 0–1 along the bar.")

    found = sorted(
        FEATURE_DIR.glob("autorift_scatter_demeaned_*.npz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    default_path = str(found[0]) if found else ""

    st.sidebar.header("Data")
    use_upload = st.sidebar.checkbox("Upload .npz", value=False)
    if use_upload:
        up = st.sidebar.file_uploader("Choose NPZ", type=["npz"])
        if up is None:
            st.info("Upload an NPZ or turn off “Upload” and set a path.")
            return
        try:
            east, north, spd, vx, vy = _load_npz_bytes(up.getvalue())
        except ValueError as e:
            st.error(str(e))
            return
        title = up.name
    else:
        path_in = st.sidebar.text_input("Path to .npz", value=default_path)
        if not path_in.strip():
            st.warning("Set a path to an NPZ file.")
            return
        path = Path(path_in).expanduser()
        if not path.is_file():
            st.error(f"File not found: {path}")
            return
        try:
            east, north, spd, vx, vy = _load_npz(path)
        except ValueError as e:
            st.error(str(e))
            return
        title = path.name

    sfin = spd[np.isfinite(spd)]
    if sfin.size == 0:
        st.error("No finite speed values in this file.")
        return
    data_min = float(np.min(sfin))
    data_max = float(np.max(sfin))
    p2 = float(np.percentile(sfin, 2.0))
    p98 = float(np.percentile(sfin, 98.0))

    st.sidebar.header("Color stretch")
    ramp_mode = st.sidebar.radio(
        "Stretch mode",
        ["Manual min / max (m/day)", "Percentiles"],
        index=0,
    )

    wid = title.replace(" ", "_")[:80]
    if ramp_mode.startswith("Manual"):
        st.sidebar.caption(
            f"Range: **{data_min:.4g}** … **{data_max:.4g}** m/day  |  2–98%: **{p2:.4g}** … **{p98:.4g}**"
        )
        span = max(data_max - data_min, 1e-12)
        step = max(span / 2000.0, 1e-9)
        c1, c2 = st.sidebar.columns(2)
        with c1:
            if st.button("Min ← 2%ile", key=f"bmin_{wid}"):
                st.session_state[f"rvmin_{wid}"] = p2
        with c2:
            if st.button("Max ← 98%ile", key=f"bmax_{wid}"):
                st.session_state[f"rvmax_{wid}"] = p98

        vmin = st.sidebar.number_input(
            "Color min (m/day)",
            min_value=data_min - 100 * span,
            max_value=data_max + 100 * span,
            value=p2,
            step=step,
            format="%.6g",
            key=f"rvmin_{wid}",
        )
        vmax = st.sidebar.number_input(
            "Color max (m/day)",
            min_value=data_min - 100 * span,
            max_value=data_max + 100 * span,
            value=p98,
            step=step,
            format="%.6g",
            key=f"rvmax_{wid}",
        )
        if vmax <= vmin:
            vmax = vmin + max(abs(vmin) * 1e-6, 1e-9)
            st.sidebar.warning("Max must exceed min; adjusted max.")
    else:
        pmin = st.sidebar.slider("Color min (percentile)", 0.0, 50.0, 0.0, 0.5)
        pmax = st.sidebar.slider("Color max (percentile)", 50.0, 100.0, 96.0, 0.5)
        if pmax <= pmin:
            pmax = min(100.0, pmin + 1.0)
        vmin = float(np.percentile(sfin, pmin))
        vmax = float(np.percentile(sfin, pmax))
        if vmax <= vmin:
            vmax = vmin + 1e-6

    st.sidebar.header("Color ramp")
    use_custom_ramp = st.sidebar.checkbox("Multi-stop custom ramp", value=False)

    has_vel = vx is not None and vy is not None

    st.sidebar.header("Map layer")
    _opt_scatter = "Speed scatter (|v| colors)"
    _opt_quiver = "Velocity quiver (vx, vy arrows)"
    layer_options = [_opt_scatter, _opt_quiver] if has_vel else [_opt_scatter]
    plot_choice = st.sidebar.radio("Layer", layer_options, index=0)
    want_quiver = has_vel and plot_choice == _opt_quiver
    quiver_ok = _quiver_has_finite_points(east, north, vx, vy)
    if want_quiver and not quiver_ok:
        st.sidebar.warning("No finite vx/vy; using scatter.")
    if not has_vel:
        st.sidebar.caption("Quiver needs ``vx_m_per_day_demeaned`` / ``vy_m_per_day_demeaned`` in the NPZ.")

    with st.sidebar.expander("Quiver style", expanded=bool(want_quiver)):
        q_length = st.slider(
            "Length × demeaned (m/day)",
            1.0,
            300.0,
            120.0,
            1.0,
            disabled=not want_quiver,
        )
        q_scale = st.slider(
            "Plotly stem scale",
            0.02,
            1.5,
            1.0,
            0.02,
            disabled=not want_quiver,
        )
        q_arrow_scale = st.slider("Arrowhead (× barb)", 0.12, 0.5, 0.32, 0.02, disabled=not want_quiver)
        q_angle = st.slider("Head angle (deg)", 8.0, 40.0, 20.0, 1.0, disabled=not want_quiver)
        q_lw = st.slider("Line width (px)", 0.5, 5.0, 1.25, 0.25, disabled=not want_quiver)
        q_col = st.color_picker("Color", "#00ffff", disabled=not want_quiver)
        q_max = st.slider("Max arrows", 400, 120_000, 80_000, 500, disabled=not want_quiver)

    opacity = st.sidebar.slider("Marker opacity", 0.05, 1.0, 0.75, 0.05, disabled=want_quiver)
    msize = st.sidebar.slider("Marker size", 2, 80, 10, 1, disabled=want_quiver)

    st.sidebar.header("Basemap (optional)")
    use_basemap = st.sidebar.checkbox("Show raster basemap under plot", value=False)
    _bmp_def = str(DEFAULT_BASEMAP_TIF) if DEFAULT_BASEMAP_TIF.is_file() else ""
    basemap_path_in = st.sidebar.text_input(
        "Basemap GeoTIFF",
        value=_bmp_def,
        disabled=not use_basemap,
    )
    basemap_opacity = st.sidebar.slider(
        "Basemap opacity", 0.15, 1.0, 0.55, 0.05, disabled=not use_basemap
    )

    if use_custom_ramp:
        if "custom_ramp_stops" not in st.session_state:
            st.session_state.custom_ramp_stops = _sample_stops_from_template("Viridis", 11, False)

        with st.sidebar.expander("Ramp stops (0–1)", expanded=True):
            tmpl = st.selectbox("Template for (re)sampling colors", COLOR_SCALES, index=0)
            rev_tmpl = st.checkbox("Reverse template when sampling", value=False)
            n_new = st.slider("Stops count when resetting from template", 3, 28, 11)
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("Reset stops from template"):
                    st.session_state.custom_ramp_stops = _sample_stops_from_template(tmpl, n_new, rev_tmpl)
            with b2:
                if st.button("Re-color only (keep positions)"):
                    cur = sorted(st.session_state.custom_ramp_stops, key=lambda x: x["pos"])
                    pos = [float(x["pos"]) for x in cur]
                    cols = px.colors.sample_colorscale(_plotly_colorscale(tmpl, rev_tmpl), pos)
                    st.session_state.custom_ramp_stops = [
                        {"id": x["id"], "pos": float(p), "color": _to_hex(c)}
                        for x, p, c in zip(cur, pos, cols)
                    ]
            with b3:
                if st.button("Add stop at 0.5"):
                    cur = list(st.session_state.custom_ramp_stops)
                    mid_c = _to_hex(
                        px.colors.sample_colorscale(_stops_to_plotly_scale(_normalize_stop_positions(cur)), [0.5])[0]
                    )
                    cur.append({"id": str(uuid.uuid4())[:10], "pos": 0.5, "color": mid_c})
                    st.session_state.custom_ramp_stops = cur

            updated: list[dict] = []
            for i, stop in enumerate(list(st.session_state.custom_ramp_stops)):
                sid = str(stop["id"])
                st.caption(f"Stop {i + 1}")
                row1, row2, row3 = st.columns([4, 2, 1])
                with row1:
                    p = st.slider(
                        "Position",
                        0.0,
                        1.0,
                        float(stop["pos"]),
                        0.002,
                        key=f"rsp_{sid}",
                    )
                with row2:
                    c = st.color_picker("Color", _to_hex(str(stop["color"])), key=f"rsc_{sid}")
                with row3:
                    del_me = st.button("×", key=f"rsd_{sid}", help="Remove (≥3 stops)")
                if del_me and len(st.session_state.custom_ramp_stops) > 3:
                    st.session_state.custom_ramp_stops = [
                        x for x in st.session_state.custom_ramp_stops if str(x["id"]) != sid
                    ]
                    st.rerun()
                if del_me:
                    continue
                updated.append({"id": sid, "pos": float(p), "color": _to_hex(str(c))})

            st.session_state.custom_ramp_stops = _normalize_stop_positions(updated)
            plotly_scale = _stops_to_plotly_scale(st.session_state.custom_ramp_stops)
    else:
        cmap = st.sidebar.selectbox("Built-in colormap", COLOR_SCALES, index=0)
        reverse = st.sidebar.checkbox("Reverse colormap", value=False)
        plotly_scale = _plotly_colorscale(cmap, reverse)

    below = int(np.sum(np.isfinite(spd) & (spd < vmin)))
    above = int(np.sum(np.isfinite(spd) & (spd > vmax)))
    st.subheader(title)
    layer_txt = (
        "Quiver"
        if want_quiver and quiver_ok
        else ("Scatter (no vx/vy for quiver)" if want_quiver else ("Scatter" if has_vel else "Scatter (no vx/vy in NPZ)"))
    )
    st.write(
        f"**{east.size:,}** points  ·  stretch **{vmin:.4g}–{vmax:.4g}** m/day "
        f"(clip −{below} / +{above})  ·  **{layer_txt}**"
    )

    with st.container(border=True):
        use_quiver = bool(want_quiver and quiver_ok)
        fig: go.Figure | None = None
        if use_quiver:
            assert vx is not None and vy is not None
            fig = _make_quiver_figure(
                east,
                north,
                vx,
                vy,
                length_mult=q_length,
                scale=q_scale,
                arrow_scale=q_arrow_scale,
                angle_rad=math.radians(q_angle),
                line_width=q_lw,
                line_color=_to_hex(q_col),
                max_arrows=int(q_max),
            )
            if fig is None:
                st.warning("No arrows to plot; showing scatter.")
                use_quiver = False

        if not use_quiver:
            if use_custom_ramp:
                st.plotly_chart(_ramp_preview_figure(plotly_scale), use_container_width=True)
            fig = px.scatter(
                x=east,
                y=north,
                color=spd,
                color_continuous_scale=plotly_scale,
                range_color=[vmin, vmax],
                labels={"x": "Easting (m)", "y": "Northing (m)", "color": "Speed (m/day)"},
            )
            fig.update_traces(marker=dict(size=msize, opacity=opacity, line=dict(width=0)))

        assert fig is not None
        if use_basemap:
            if not basemap_path_in.strip():
                st.warning("Basemap: set a GeoTIFF path.")
            else:
                ext = _padded_extent(east, north, 0.005)
                bm = _basemap_png_uri(Path(basemap_path_in).expanduser(), *ext)
                if bm is not None:
                    uri, west, east_bm, south, north_bm = bm
                    fig.add_layout_image(
                        dict(
                            source=uri,
                            xref="x",
                            yref="y",
                            x=west,
                            y=south,
                            xanchor="left",
                            yanchor="bottom",
                            sizex=east_bm - west,
                            sizey=north_bm - south,
                            sizing="stretch",
                            layer="below",
                            opacity=float(basemap_opacity),
                        )
                    )
                else:
                    st.warning("Basemap: read failed or no overlap with extent.")
        _apply_geo_scatter_layout(fig, east, north, base_h=680, show_speed_colorbar=not use_quiver)
        if use_quiver:
            fig.update_layout(xaxis_title="Easting (m)", yaxis_title="Northing (m)")
        st.plotly_chart(fig, use_container_width=False)


if __name__ == "__main__":
    main()
