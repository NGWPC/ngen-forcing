# coastalforcing/process_data/glofs_sfincs.py
"""
GLOFS → SFINCS .bzs generator (robust/local-first)

Key features:
- Local-first: every dataset is materialized to disk before reading (with cache-hit logs).
- Multiple URL patterns tried for both the sample mesh and each hourly file.
- Clear diagnostics: prints mesh lon/lat bbox and first few transformed boundary points.
- Non-fatal outside-mesh behavior: writes NaNs instead of aborting, so time axis still appears.
- utm_epsg is passed in by the caller (no hard-coded CRS).

Usage from DataProcessor:
    from .glofs_sfincs import build_bzs_from_glofs_legacy

    build_bzs_from_glofs_legacy(
        model="leofs",                          # leofs, lsofs, lmhofs, loofs, ...
        bnd_file=path_to_sfincs_bnd,
        bzs_outfile=path_to_sfincs_bzs,
        start_dt=self.start_dt,
        end_dt=self.end_dt,
        time_step_hours=1,
        utm_epsg=f"EPSG:{self.target_epsg}",    # e.g., "EPSG:32617" for Lake Erie
        add_360_longitudes=True,
        downloads_dir=os.path.join(self.sim_dir, "glofs_nc")  # optional; defaults next to bzs_outfile
    )
"""

from __future__ import annotations

import os
import re
import time
import math
import shutil
import tempfile
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import numpy as np
import xarray as xr
import matplotlib.tri as tri
from pyproj import Transformer

# ----------------------------
# Helpers
# ----------------------------

def _parse_dt_utc_any(s) -> datetime:
    """Parse common ISO-ish strings into naive datetimes (UTC-like)."""
    if isinstance(s, datetime):
        return s.replace(tzinfo=None)
    s = str(s).strip()
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s.replace("T", " ")).replace(tzinfo=None)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    # last resort
    import pandas as pd
    return pd.to_datetime(s).to_pydatetime().replace(tzinfo=None)


def _safe_open_nc(local_path: str) -> xr.Dataset:
    """Open NetCDF locally, with a fallback to disable time decoding if needed."""
    drop_vars = ["siglay", "siglev", "siglay_center", "siglev_center"]
    try:
        return xr.open_dataset(local_path, engine="netcdf4", decode_times=True, drop_variables=drop_vars)
    except Exception as e:
        print(f"[GLOFS] retrying without time decoding due to: {e}")
        return xr.open_dataset(local_path, engine="netcdf4", decode_times=False, drop_variables=drop_vars)


def _ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def _cache_path(downloads_dir: str, url: str) -> str:
    """Local filename by URL basename."""
    return os.path.join(downloads_dir, os.path.basename(url))


def _download_stream(url: str, dest: str, timeout: int = 90) -> str:
    """Stream a remote file to disk."""
    import requests
    _ensure_dir(os.path.dirname(dest))
    print(f"[GLOFS] GET {url} -> {dest}")
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
    return dest


def _opendap_subset_to_local(url_with_query: str, dest: str, timeout: int = 90) -> str:
    """
    Read an OPeNDAP (dodsC) URL with section spec (or query naming) and write a local NetCDF.
    Uses xarray -> netcdf write.
    """
    # We use engine=netcdf4 to support dodsC; if server responds with HTML, xarray will error.
    print(f"[GLOFS] OPeNDAP (subset) try: {url_with_query}")
    ds = xr.open_dataset(url_with_query, engine="netcdf4")
    _ensure_dir(os.path.dirname(dest))
    ds.to_netcdf(dest)
    ds.close()
    print(f"[GLOFS] wrote subset NetCDF -> {dest}")
    return dest


def _ensure_local_file(
    downloads_dir: str,
    raw_url: str,
    *,
    opendap_query: Optional[str] = None,
    alternates: Optional[List[str]] = None,
    allow_cached: bool = True,
) -> Optional[str]:
    """
    Ensure we have a usable local file for a given timestamp.
    Order:
      1) If cached (non-empty), return it.
      2) Try OPeNDAP subset (if opendap_query provided).
      3) Try raw_url direct download (fileServer style).
      4) Try each alternate URL (direct download).
    Returns the local path, or None if all attempts fail.
    """
    alternates = alternates or []
    dest = _cache_path(downloads_dir, raw_url)
    if allow_cached and os.path.exists(dest) and os.path.getsize(dest) > 0:
        print(f"[GLOFS] cache hit: {dest}")
        return dest

    last_err = None

    # 1) OPeNDAP subset (if provided query)
    if opendap_query:
        # The subset dest should be named by the base (consistent)
        try:
            return _opendap_subset_to_local(opendap_query, dest)
        except Exception as e:
            last_err = e
            print(f"[GLOFS] OPeNDAP subset failed: {e}")

    # 2) Raw direct download
    try:
        return _download_stream(raw_url, dest)
    except Exception as e:
        last_err = e
        print(f"[GLOFS] try url failed: {raw_url} → {e}")

    # 3) Alternates
    for alt in alternates:
        dest_alt = _cache_path(downloads_dir, alt)
        try:
            return _download_stream(alt, dest_alt)
        except Exception as e:
            last_err = e
            print(f"[GLOFS] try url failed: {alt} → {e}")

    print(f"[GLOFS] no local file after tries (last error: {last_err})")
    return None


def _glofs_url_patterns(model: str, dt: datetime) -> Tuple[str, List[str]]:
    """
    Build URL patterns for a given time. Returns (primary_file_url, [alternates]).
    `primary_file_url` is the 'leofs.t00z.20250611.fields.n000.nc' style.
    Alternates include the 'nos.leofs.fields.n000.20250611.t00z.nc' style.
    """
    date_str = dt.strftime("%Y%m%d")
    hour = dt.hour
    cycle_hour = (hour // 6) * 6
    cycle = f"t{cycle_hour:02d}z"
    suffix = f"n{hour % 6:03d}"
    yyyy = f"{dt.year:04d}"
    mm = dt.strftime("%m")

    # Pattern A: "model.t00z.YYYYMMDD.fields.nxxx.nc"
    primary = (
        f"https://www.ncei.noaa.gov/data/operational-nowcast-and-forecast-hydrodynamic-model-systems-co-ops/access/"
        f"lake-erie-operational-forecast-system-leofs".replace("leofs", model) +  # keep generic path per model
        f"/{yyyy}/{mm}/{model}.{cycle}.{date_str}.fields.{suffix}.nc"
    )

    # Pattern B: "nos.model.fields.nxxx.YYYYMMDD.t00z.nc"
    alt = (
        f"https://www.ncei.noaa.gov/data/operational-nowcast-and-forecast-hydrodynamic-model-systems-co-ops/access/"
        f"lake-erie-operational-forecast-system-leofs".replace("leofs", model) +
        f"/{yyyy}/{mm}/nos.{model}.fields.{suffix}.{date_str}.{cycle}.nc"
    )

    # Pattern C/D: legacy THREDDS (OPeNDAP/fileServer)
    thredds_dods = (
        f"https://www.ncei.noaa.gov/thredds/dodsC/model-{model}/{yyyy}/{mm}/"
        f"{model}.{cycle}.{date_str}.fields.{suffix}.nc"
    )
    thredds_file = thredds_dods.replace("/thredds/dodsC/", "/thredds/fileServer/")

    return primary, [alt, thredds_file, thredds_dods]


def _glofs_sample_patterns(model: str, dt: datetime) -> Tuple[str, List[str], str]:
    """
    Build patterns for the sample (t00z, n000) file to get mesh.
    Returns (primary_file_url, alternates, opendap_subset_url_with_query).
    """
    date_str = dt.strftime("%Y%m%d")
    yyyy = f"{dt.year:04d}"
    mm = dt.strftime("%m")

    # Pattern A: "model.t00z.YYYYMMDD.fields.n000.nc"
    primary = (
        f"https://www.ncei.noaa.gov/data/operational-nowcast-and-forecast-hydrodynamic-model-systems-co-ops/access/"
        f"lake-erie-operational-forecast-system-leofs".replace("leofs", model) +
        f"/{yyyy}/{mm}/{model}.t00z.{date_str}.fields.n000.nc"
    )

    # Pattern B/C: legacy THREDDS
    thredds_dods = (
        f"https://www.ncei.noaa.gov/thredds/dodsC/model-{model}/{yyyy}/{mm}/"
        f"{model}.t00z.{date_str}.fields.n000.nc"
    )
    thredds_file = thredds_dods.replace("/thredds/dodsC/", "/thredds/fileServer/")

    # OPeNDAP subset (keep small): lon/lat/nv + a single time slice of zeta to verify structure
    opendap_subset = (
        f"{thredds_dods}"
        f"?lon[0:1:6105],lat[0:1:6105],nv[0:1:2][0:1:11508],zeta[0:1:0][0:1:6105],Times[0:1:0]"
    )

    return primary, [thredds_file, thredds_dods], opendap_subset


def _build_triangulation(ds: xr.Dataset) -> Tuple[tri.Triangulation, np.ndarray, np.ndarray]:
    """Return triangulation and lon/lat arrays (1D)."""
    lon = ds["lon"].values
    lat = ds["lat"].values
    nv = ds["nv"].values.T - 1  # 0-based
    triang = tri.Triangulation(lon, lat, nv)
    return triang, lon, lat


# ----------------------------
# Main extractor
# ----------------------------

def extract_glofs_timeseries(
    model: str,
    bnd_file: str,
    bzs_outfile: str,
    start_time: datetime,
    end_time: datetime,
    time_step: timedelta,
    utm_epsg: str,
    add_360_longitudes: bool = True,
    downloads_dir: Optional[str] = None,
) -> None:
    """
    Generate SFINCS .bzs from GLOFS.

    - model: 'leofs', 'lsofs', 'lmhofs', 'loofs', ...
    - bnd_file: SFINCS .bnd (x y ... in `utm_epsg`)
    - bzs_outfile: output .bzs
    - start_time/end_time: datetime (naive UTC-like)
    - time_step: timedelta (usually 1 hour)
    - utm_epsg: CRS of .bnd, e.g. "EPSG:32617"
    - add_360_longitudes: wrap negative lons to [0,360] if True
    - downloads_dir: local cache folder for NetCDFs (defaults to sibling 'glofs_nc' next to bzs)
    """
    # --- I/O setup ---
    if downloads_dir is None:
        downloads_dir = os.path.join(os.path.dirname(os.path.abspath(bzs_outfile)), "glofs_nc")
    _ensure_dir(downloads_dir)

    # --- Read boundary points (UTM) ---
    bnd_coords: List[Tuple[float, float]] = []
    with open(bnd_file, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            parts = s.split()
            if len(parts) >= 2:
                bnd_coords.append((float(parts[0]), float(parts[1])))
    if not bnd_coords:
        raise RuntimeError(f"No valid boundary points found in {bnd_file}")

    # --- Transform to WGS84 ---
    transformer = Transformer.from_crs(utm_epsg, "EPSG:4326", always_xy=True)
    xs, ys = zip(*bnd_coords)
    qlon, qlat = transformer.transform(xs, ys)
    qlon = np.asarray(qlon, dtype=float)
    qlat = np.asarray(qlat, dtype=float)
    if add_360_longitudes:
        qlon = np.where(qlon < 0, qlon + 360.0, qlon)

    print(f"[GLOFS] boundary points: {len(qlon)}")

    # --- Get sample mesh file locally (tries: OPeNDAP subset → fileServer/direct patterns) ---
    primary_s, alternates_s, opendap_subset_s = _glofs_sample_patterns(model, start_time)
    sample_local = _ensure_local_file(
        downloads_dir,
        primary_s,
        opendap_query=opendap_subset_s,
        alternates=alternates_s,
        allow_cached=True,
    )
    if not sample_local:
        raise RuntimeError("Could not obtain a sample GLOFS file for mesh triangulation.")

    ds0 = _safe_open_nc(sample_local)
    triang, lon1d, lat1d = _build_triangulation(ds0)
    finder = triang.get_trifinder()
    tri_idx = finder(qlon, qlat)

    # Diagnostics: mesh bbox + first few points
    mesh_lon_min, mesh_lon_max = float(np.nanmin(lon1d)), float(np.nanmax(lon1d))
    mesh_lat_min, mesh_lat_max = float(np.nanmin(lat1d)), float(np.nanmax(lat1d))
    print(
        f"[GLOFS] mesh from {os.path.basename(sample_local)} (nodes={len(lon1d)}, elems={len(triang.triangles)})"
    )
    print(f"[GLOFS] mesh lon/lat bbox: lon[{mesh_lon_min:.3f},{mesh_lon_max:.3f}], "
          f"lat[{mesh_lat_min:.3f},{mesh_lat_max:.3f}]")
    preview = [(round(qlon[i], 4), round(qlat[i], 4)) for i in range(min(3, len(qlon)))]
    print(f"[GLOFS] first 3 transformed points (lon,lat): {preview}")

    # Precompute interpolation data (barycentric) using sample triangulation
    interp_data: List[Optional[Tuple[np.ndarray, List[float]]]] = []
    for i, t_idx in enumerate(tri_idx):
        if t_idx == -1:
            interp_data.append(None)
            continue
        nodes = triang.triangles[t_idx]
        x = triang.x[nodes]
        y = triang.y[nodes]

        A = np.array([[x[1] - x[0], x[2] - x[0]],
                      [y[1] - y[0], y[2] - y[0]]], dtype=float)
        b = np.array([qlon[i] - x[0], qlat[i] - y[0]], dtype=float)
        try:
            l1, l2 = np.linalg.solve(A, b)
            w0 = 1.0 - l1 - l2
            weights = [w0, l1, l2]
            interp_data.append((nodes, weights))
        except np.linalg.LinAlgError:
            interp_data.append(None)

    node_list = sorted({n for item in interp_data if item for n in item[0]})
    node_index_map = {n: i for i, n in enumerate(node_list)}

    if all(item is None for item in interp_data):
        print(f"[GLOFS][warn] {len(qlon)}/{len(qlon)} boundary points fall outside mesh; "
              f"values will be NaN. Check utm_epsg and add_360_longitudes.")

    # --- Time loop ---
    lines: List[str] = []
    current_time = start_time
    while current_time <= end_time:
        primary, alternates = _glofs_url_patterns(model, current_time)
        # Also construct an OPeNDAP subset URL for this time (smaller fetch if dodsC works)
        # We reuse the same subset variable list; the slice for zeta/time is single-slice.
        odt = current_time
        datestr = odt.strftime("%Y%m%d")
        yyyy = f"{odt.year:04d}"
        mm = odt.strftime("%m")
        hour = odt.hour
        cycle_hour = (hour // 6) * 6
        cycle = f"t{cycle_hour:02d}z"
        suffix = f"n{hour % 6:03d}"
        opendap_subset = (
            f"https://www.ncei.noaa.gov/thredds/dodsC/model-{model}/{yyyy}/{mm}/"
            f"{model}.{cycle}.{datestr}.fields.{suffix}.nc"
            f"?lon[0:1:6105],lat[0:1:6105],nv[0:1:2][0:1:11508],zeta[0:1:0][0:1:6105],Times[0:1:0]"
        )

        local_path = _ensure_local_file(
            downloads_dir,
            primary,
            opendap_query=opendap_subset,
            alternates=alternates,
            allow_cached=True,
        )
        if not local_path:
            print(f"[GLOFS] no data for {current_time} (all sources failed)")
            # Still write a NaN row to preserve time axis consistency
            sec = int((current_time - start_time).total_seconds())
            lines.append(" ".join([str(sec)] + ["nan"] * len(qlon)))
            current_time += time_step
            continue

        try:
            ds = _safe_open_nc(local_path)
            # Expect shape time x node; we take time=0 slice
            zeta0 = ds["zeta"].isel(time=0)
            max_node = int(zeta0.sizes.get("node", ds.sizes.get("node", 0))) - 1
            valid_nodes = [n for n in node_list if 0 <= n <= max_node]

            sec = int((current_time - start_time).total_seconds())
            row = [str(sec)]

            if not valid_nodes or not node_list:
                # All outside mesh → NaNs
                row.extend(["nan"] * len(qlon))
                lines.append(" ".join(row))
                current_time += time_step
                continue

            # Pull only the nodes we need (fast)
            z_vals = zeta0.isel(node=valid_nodes).load().values

            # Map original node ids -> compact index
            idx_map_local = {n: i for i, n in enumerate(valid_nodes)}

            for interp in interp_data:
                if interp is None:
                    row.append("nan")
                else:
                    nodes, weights = interp
                    vals = []
                    for n in nodes:
                        j = idx_map_local.get(n, None)
                        if j is None:
                            vals.append(np.nan)
                        else:
                            vals.append(float(z_vals[j]))
                    # Weighted sum
                    if any(math.isnan(v) for v in vals):
                        row.append("nan")
                    else:
                        row.append(f"{np.dot(weights, vals):.4f}")

            lines.append(" ".join(row))
        except Exception as e:
            print(f"[GLOFS] failed to process {os.path.basename(local_path)}: {e}")
            # Write a NaN row to maintain time axis
            sec = int((current_time - start_time).total_seconds())
            lines.append(" ".join([str(sec)] + ["nan"] * len(qlon)))

        current_time += time_step

    # --- Write SFINCS .bzs ---
    _ensure_dir(os.path.dirname(os.path.abspath(bzs_outfile)))
    with open(bzs_outfile, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    print(f"[GLOFS] wrote {bzs_outfile}")


# ----------------------------
# Thin wrapper for your pipeline
# ----------------------------
def build_bzs_from_glofs_legacy(
    *,
    model: str,
    bnd_file: str,
    bzs_outfile: str,
    start_dt,
    end_dt,
    time_step_hours: int = 1,
    utm_epsg: str = "EPSG:32617",
    add_360_longitudes: bool = True,
    downloads_dir: Optional[str] = None,
    base_dir: Optional[str] = None,   # <— accepted for backward-compat (ignored)
) -> str:
    """
    Public entry point. Returns `bzs_outfile`.

    Parameters
    ----------
    model : str
        GLOFS short code: "leofs", "lsofs", "lmhofs", "loofs", ...
    bnd_file : str
        Path to SFINCS .bnd (x y ...).
    bzs_outfile : str
        Output .bzs path.
    start_dt, end_dt :
        Datetime or string (parsed). Naive OK; treated as UTC.
    time_step_hours : int
        Typically 1.
    utm_epsg : str
        CRS of .bnd coordinates, e.g. "EPSG:32617".
    add_360_longitudes : bool
        If True, wraps negative longitudes to [0,360].
    downloads_dir : Optional[str]
        Local cache folder for NetCDFs. If None, defaults to sibling "glofs_nc".
    base_dir : Optional[str]
        Ignored (kept for backward-compatibility with legacy caller).
    """
    start = _parse_dt_utc_any(start_dt)
    end = _parse_dt_utc_any(end_dt)

    extract_glofs_timeseries(
        model=model,
        bnd_file=bnd_file,
        bzs_outfile=bzs_outfile,
        start_time=start,
        end_time=end,
        time_step=timedelta(hours=int(time_step_hours)),
        utm_epsg=utm_epsg,
        add_360_longitudes=add_360_longitudes,
        downloads_dir=downloads_dir,
    )
    return bzs_outfile


