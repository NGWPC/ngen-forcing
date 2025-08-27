# coastalforcing/process_data/stofs_timeseries_legacy.py
"""
Legacy STOFS → SFINCS time-series utility.

Usage (from DataProcessor):
    from .stofs_timeseries_legacy import process_stofs_timeseries
    process_stofs_timeseries(
        bnd_file=/path/to/sfincs.bnd,
        grib_file=/path/to/stofs_2d_glo.tHHz.conus.east.cwl.grib2,
        bzs_output=/path/to/run/sfincs.bzs,
        utm_crs_epsg="EPSG:32614",            # match your domain's UTM EPSG
        variable_name="unknown",              # or set explicit variable if you know it
    )
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import xarray as xr
import pyproj
from scipy.interpolate import griddata, interp1d
import xarray as xr
import numpy as np

def _pick_stofs_var(ds: xr.Dataset) -> str:
    """
    Pick a likely STOFS water level variable from the dataset.
    Preference order by typical short/long names; otherwise, first 3D (step,y,x) or 2D (y,x).
    """
    # 1) Known/likely names (shortName/long_name often mapped to 'name' in cfgrib)
    preferred = [
        "waterLevel", "slev", "etss", "storm_surge", "Extra_Tropical_Storm_Surge_Combined_Surge_and_Tide_Surface",
        "surgert", "cwl", "heightAboveMeanSeaLevel", "h"  # broader fallbacks
    ]
    for cand in preferred:
        if cand in ds.variables:
            return cand

    # 2) Any data var with dims that look like STOFS grids/time
    candidates = []
    for v in ds.data_vars:
        dims = ds[v].dims
        if ("step" in dims or "time" in dims) and ("y" in dims and "x" in dims):
            candidates.append(v)
    if candidates:
        return candidates[0]

    # 3) Any (y,x) grid
    for v in ds.data_vars:
        dims = ds[v].dims
        if ("y" in dims and "x" in dims):
            return v

    # 4) Give up → caller will raise
    raise ValueError("Could not detect a suitable STOFS water-level variable in GRIB dataset.")


def _open_stofs_grib_detect_var(path: str) -> tuple[xr.Dataset, str]:
    """
    Try multiple cfgrib 'filter_by_keys' combos. If none work, open all messages and select a variable.
    Returns (dataset, variable_name).
    """
    tries = [
        {"typeOfLevel": "surface"},
        {"typeOfLevel": "meanSea"},
        {"typeOfLevel": "depthBelowSea"},
        # Some builds separate messages by shortName
        {"shortName": "etss"},
        {"shortName": "slev"},
        {"shortName": "cwl"},
        # As a last directed try: no filter (single message files)
        None,
    ]

    for fbk in tries:
        try:
            if fbk is None:
                ds = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})
            else:
                ds = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": "", "filter_by_keys": fbk})
            var_name = _pick_stofs_var(ds)
            return ds, var_name
        except Exception:
            pass  # try next

    # If all single-dataset attempts fail, open ALL messages and search
    try:
        dsets = xr.open_datasets(path, engine="cfgrib", backend_kwargs={"indexpath": ""})
        # Concatenate/merge if possible; else scan one by one
        for ds in dsets:
            try:
                var_name = _pick_stofs_var(ds)
                return ds, var_name
            except Exception:
                continue
        # If still not found, try to merge everything (may raise)
        merged = xr.merge(dsets, compat="no_conflicts", join="outer")
        var_name = _pick_stofs_var(merged)
        return merged, var_name
    except Exception as e:
        raise RuntimeError(f"No valid GRIB messages found for STOFS in {path}: {e}")


# ---------------------- helpers ----------------------
def _detect_stofs_variable(ds: xr.Dataset) -> Optional[str]:
    """
    Best-effort pick of a STOFS variable when the name is unknown.
    Preference order:
      1) Variables with dimension ('step','y','x') or ('time','y','x')
      2) Otherwise, first 3-D variable that broadcasts to a (y,x) grid
    Returns the variable name or None if nothing suitable found.
    """
    # Common dimension names in cfgrib STOFS files
    time_dims = ("step", "time")
    space_dims = ("y", "x")

    candidates = []
    for name, da in ds.data_vars.items():
        dims = tuple(da.dims)
        if len(dims) == 3:
            # strictly ('step','y','x') or ('time','y','x')
            if dims[0] in time_dims and dims[1:] == space_dims:
                candidates.append(name)

    if candidates:
        # Return the first one as "best" candidate
        return candidates[0]

    # fallback: any 3D with last two dims (y,x)
    for name, da in ds.data_vars.items():
        dims = tuple(da.dims)
        if len(dims) == 3 and dims[-2:] == space_dims:
            return name

    return None


def _build_stofs_latlon_grid(ds: xr.Dataset) -> Tuple[np.ndarray, np.ndarray]:
    """
    Rebuild Lambert-conformal grid → lat/lon using fixed constants
    (matches your original script logic).
    Returns (lon_grid, lat_grid) as 2D arrays with shapes (y, x).
    """
    # Lambert Conformal Conic used by STOFS CONUS tiles (from your original code)
    lambert_crs = pyproj.CRS.from_proj4(
        "+proj=lcc +lat_1=25 +lat_2=25 +lat_0=25 "
        "+lon_0=265 +x_0=0 +y_0=0 +R=6371200 +units=m +no_defs"
    )
    wgs84 = pyproj.CRS("EPSG:4326")
    to_latlon = pyproj.Transformer.from_crs(lambert_crs, wgs84, always_xy=True)
    to_lambert = pyproj.Transformer.from_crs(wgs84, lambert_crs, always_xy=True)

    # grid spacing and origin (constants you used)
    dx = 2539.703
    dy = 2539.703
    lon0 = 238.445999
    lat0 = 20.191999

    x0, y0 = to_lambert.transform(lon0, lat0)
    nx = ds.dims["x"]
    ny = ds.dims["y"]

    x = x0 + np.arange(nx) * dx
    y = y0 + np.arange(ny) * dy
    X, Y = np.meshgrid(x, y)

    lon_grid, lat_grid = to_latlon.transform(X, Y)
    return lon_grid, lat_grid


# ---------------------- main entry ----------------------
def process_stofs_timeseries(
    bnd_file: str,
    grib_file: str,
    bzs_output: str,
    utm_crs_epsg: str = "EPSG:32614",
    variable_name: str = "unknown",
) -> Tuple[int, int]:
    """
    Build SFINCS coastal water level time series (sfincs.bzs) at the boundary
    points using STOFS GRIB2 forcing.

    Steps (mirrors your original script):
      1) Read SFINCS boundary (x,y) in UTM
      2) Open STOFS GRIB (cfgrib); pick variable if 'unknown'
      3) Rebuild Lambert grid → lat/lon; interpolate values at boundary points
      4) Write raw time series (seconds_since_base + values) to sfincs_raw.bzs
      5) Resample/interpolate to 600 s and write final sfincs.bzs

    Returns:
      (n_time_steps_written, n_boundary_points)
    """
    # ---- Read SFINCS boundary in UTM ----
    if not os.path.isfile(bnd_file):
        raise FileNotFoundError(f"Boundary file not found: {bnd_file}")
    bnd_df = pd.read_csv(bnd_file, sep=r"\s+", header=None, names=["x", "y"])  # fixes FutureWarning
    if bnd_df.empty:
        raise RuntimeError(f"No boundary points in {bnd_file}")
    ds, variable_name = _open_stofs_grib_detect_var(grib_file)                 # robust open
    var = ds[variable_name]

    '''
    if var_name == "unknown":
        guessed = _detect_stofs_variable(ds)
        if guessed is None:
            raise RuntimeError(
                "Could not auto-detect a STOFS variable (dims like ('step','y','x')). "
                "Pass variable_name explicitly."
            )
        var_name = guessed
        print(f"[stofs] auto-selected variable: {var_name}")

    var = ds[var_name]  # dims expected like ('step','y','x') or ('time','y','x')
    '''

    # ---- Convert SFINCS boundary UTM → lat/lon ----
    utm_crs = pyproj.CRS(utm_crs_epsg)
    wgs84 = pyproj.CRS("EPSG:4326")
    to_latlon = pyproj.Transformer.from_crs(utm_crs, wgs84, always_xy=True)
    lon_bnd, lat_bnd = to_latlon.transform(bnd_df["x"].values, bnd_df["y"].values)

    # ---- Build STOFS grid lat/lon (from fixed LCC params) ----
    lon_grid, lat_grid = _build_stofs_latlon_grid(ds)

    # ---- Interpolate at boundary points for each time step ----
    times = ds["step"].values  # numpy datetime64[ns] deltas from base time
    time_seconds = (times / np.timedelta64(1, "s")).astype(np.int64)

    # Prepare interpolation points
    grid_points = np.column_stack((lat_grid.ravel(), lon_grid.ravel()))
    bnd_points = np.column_stack((lat_bnd, lon_bnd))

    output = []
    for t_idx in range(len(times)):
        data_t = var.isel(step=t_idx).values
        values = griddata(
            points=grid_points,
            values=data_t.ravel(),
            xi=bnd_points,
            method="linear",
            fill_value=np.nan,
        )
        output.append(values)
        # optional progress
        # print(f"[stofs] interpolated step {t_idx+1}/{len(times)}")

    output_array = np.asarray(output)  # shape: (T, Npoints)

    # ---- Write raw .bzs (seconds + values) ----
    raw_dir = os.path.dirname(os.path.abspath(bzs_output)) or "."
    raw_bzs_path = os.path.join(raw_dir, "sfincs_raw.bzs")
    with open(raw_bzs_path, "w") as f:
        for i, row in enumerate(output_array):
            t = int(time_seconds[i])
            vals = " ".join(f"{v:.4f}" if np.isfinite(v) else "0.0000" for v in row)
            f.write(f"{t} {vals}\n")

    # ---- Resample to 600 s using cubic (per-point) ----
    original_time = time_seconds.astype(float)
    if original_time.size < 2:
        # Not enough steps to resample — just copy raw to final
        os.replace(raw_bzs_path, bzs_output)
        print(f"[stofs] only one step; wrote {bzs_output}")
        return (len(original_time), output_array.shape[1])

    new_time = np.arange(original_time[0], original_time[-1] + 1, 600)  # 10-minute grid
    interp_cols = []
    for col in output_array.T:
        finite = np.isfinite(col)
        if finite.sum() > 1:
            f = interp1d(
                original_time[finite], col[finite],
                kind="cubic", fill_value="extrapolate", assume_sorted=True
            )
            interp_cols.append(f(new_time))
        else:
            interp_cols.append(np.full_like(new_time, 0.0, dtype=float))

    interp_array = np.stack(interp_cols, axis=1)  # (Tnew, Npoints)

    with open(bzs_output, "w") as f:
        for i, row in enumerate(interp_array):
            t = int(new_time[i])
            vals = " ".join(f"{v:.4f}" if np.isfinite(v) else "0.0000" for v in row)
            f.write(f"{t} {vals}\n")

    print(f"[stofs] wrote raw: {raw_bzs_path}")
    print(f"[stofs] wrote bzs: {bzs_output}")
    return (interp_array.shape[0], interp_array.shape[1])

