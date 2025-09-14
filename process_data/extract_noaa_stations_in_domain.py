# extract_noaa_stations_in_domain_generalized.py
# Reads all parameters from a YAML config in one function, then passes them to a pure processing function.

import argparse
from pathlib import Path
from datetime import datetime
import os

import geopandas as gpd
import requests
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

try:
    import yaml  # PyYAML
except Exception as e:
    raise RuntimeError("PyYAML is required. Install with: pip install pyyaml") from e


# ---------------------------
# Helpers from original script
# ---------------------------

def fetch_stations(station_type: str) -> gpd.GeoDataFrame:
    """
    Fetch station metadata for a given type ('waterlevels' or 'currents') from NOAA MDAPI.
    Returns a GeoDataFrame in EPSG:4326 with 'id', 'name', 'lat', 'lng' columns.
    """
    url = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations.json"
    params = {"type": station_type, "format": "json"}
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    stations = pd.json_normalize(resp.json()["stations"])
    stations_gdf = gpd.GeoDataFrame(
        stations,
        geometry=gpd.points_from_xy(stations.lng, stations.lat),
        crs="EPSG:4326",
        copy=False
    )
    return stations_gdf


def get_station_navd_offset(station_id: str) -> float:
    """
    Returns the NAVD88 - MSL offset (meters) for a given station.
    If anything fails, returns 0.0 (original fallback).
    """
    url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    params = {
        "station": station_id,
        "product": "datums",
        "units": "metric",
        "format": "json"
    }
    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json().get("datums", [])
        msl = navd = None
        for item in data:
            if item.get("n") == "MSL":
                msl = float(item["v"])
            if item.get("n") == "NAVD":
                navd = float(item["v"])
        if msl is not None and navd is not None:
            return navd - msl
    except Exception as e:
        print(f"Failed to get NAVD88 offset for {station_id}: {e}")
    return 0.0


# ---------------------------
# Processing function (all logic lives here)
# ---------------------------

def run_noaa_stations_from_params(
    *,
    geojson_path: str,
    utm_epsg: int,
    start_time: str,
    end_time: str,
    interval_minutes: int,
    output_dir: str,
    obs_filename: str,
    out_filename: str,
    station_types: list,
    plot_domain_facecolor: str = "lightblue",
    plot_figsize: tuple = (10, 8),
    plot_dpi: int = 150,
    label_offset_deg: float = 0.01,
) -> None:
    """
    Does the full workflow using only the parameters passed in.
    """

    outdir = Path(output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    # ---- domain polygon (EPSG:4326) ----
    gdf = gpd.read_file(geojson_path).to_crs(epsg=4326)
    polygon = gdf.unary_union.buffer(0)

    # ---- fetch stations by type, clip to polygon ----
    station_dfs = {}
    for stype in station_types:
        df = fetch_stations(stype)
        station_dfs[stype] = df[df.within(polygon)]
        print(f"Found {len(station_dfs[stype])} {stype} station(s)")

    # ---- plot map ----
    fig, ax = plt.subplots(figsize=tuple(plot_figsize))
    gdf.plot(ax=ax, edgecolor='black', facecolor=plot_domain_facecolor)

    color_map = {"waterlevels": "red", "currents": "blue"}
    for stype in station_types:
        color = color_map.get(stype, "gray")
        if not station_dfs[stype].empty:
            station_dfs[stype].plot(ax=ax, color=color, markersize=40, label=stype.title())

    for df in station_dfs.values():
        for _, row in df.iterrows():
            ax.text(row.geometry.x + label_offset_deg, row.geometry.y, row.get("id", ""), fontsize=8)

    ax.legend()
    ax.set_title("Model Domain and NOAA Stations")
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(outdir / "ModelDomain_NOAAStations.png", dpi=int(plot_dpi))
    plt.close()

    # ---- write sfincs.obs (UTM) ----
    with open(outdir / obs_filename, "w", encoding="utf-8") as f:
        for df in station_dfs.values():
            if df.empty:
                continue
            df_utm = df.to_crs(epsg=int(utm_epsg))
            for _, row in df_utm.iterrows():
                x, y = row.geometry.x, row.geometry.y
                name = row.get("name", "")
                sid = row.get("id", "")
                f.write(f"{x:.2f} {y:.2f} \"{name} ({sid})\"\n")

    # ---- time series pulling for WATER LEVEL stations only (as original) ----
    start_dt = datetime.strptime(start_time, "%Y-%m-%dT%H-%M-%SZ")
    end_dt   = datetime.strptime(end_time,   "%Y-%m-%dT%H-%M-%SZ")
    all_times = pd.date_range(start=start_dt, end=end_dt, freq=f"{int(interval_minutes)}min")
    series = {}

    water_stations = station_dfs.get("waterlevels", pd.DataFrame())
    station_ids = water_stations["id"].tolist() if not water_stations.empty else []

    for station_id in station_ids:
        begin_date = start_dt.strftime("%Y%m%d")
        end_date   = end_dt.strftime("%Y%m%d")

        query = {
            "begin_date": begin_date,
            "end_date": end_date,
            "station": station_id,
            "product": "water_level",
            "datum": "MSL",
            "units": "metric",
            "time_zone": "gmt",
            "format": "json",
            "interval": str(int(interval_minutes))
        }
        try:
            r = requests.get("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter", params=query)
            r.raise_for_status()
            data = r.json().get("data", [])
            times = [datetime.strptime(d["t"], "%Y-%m-%d %H:%M") for d in data]
            values = [float(d["v"]) if "v" in d else np.nan for d in data]
            navd_offset = get_station_navd_offset(station_id)  # NAVD - MSL
            adj_values = [v - navd_offset if not np.isnan(v) else np.nan for v in values]
            series[station_id] = pd.Series(adj_values, index=times)
        except Exception as e:
            print(f"Failed to fetch data for {station_id}: {e}")
            series[station_id] = pd.Series(dtype=float)

    # ---- assemble dataframe on requested cadence & write noaa.out ----
    df = pd.DataFrame(index=all_times)
    for sid, s in series.items():
        df[sid] = s.reindex(all_times)
    df.insert(0, "time_s", [(t - start_dt).total_seconds() for t in df.index])
    df.to_csv(outdir / out_filename, sep=" ", float_format="%.4f", index=False)

    # ---- per-station plots ----
    time_hr = df["time_s"] / 3600.0
    for sid in series:
        plt.figure(figsize=(8, 4))
        plt.plot(time_hr, df[sid], label=sid)
        plt.xlabel(f"Time since {start_time} (hours)")
        plt.ylabel("Water Level (m NAVD88)")
        plt.title(f"Station {sid}")
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(outdir / f"station_{sid}.png", dpi=int(plot_dpi))
        plt.close()


# ---------------------------
# Config reader (no processing; only loads and passes)
# ---------------------------

def read_config_and_run(config_path: str) -> None:
    """
    Reads the YAML config and forwards parameters to the processing function.
    No processing/validation happens here.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    # Forward ALL keys as kwargs.
    # The processing function is responsible for defaults/validation/typing.
    run_noaa_stations_from_params(**cfg)


# ---------------------------
# CLI entry
# ---------------------------

def main():
    parser = argparse.ArgumentParser(description="Extract NOAA stations & time series using a YAML config.")
    parser.add_argument("--config", required=True, help="Path to YAML config file.")
    args = parser.parse_args()
    read_config_and_run(args.config)


if __name__ == "__main__":
    main()

