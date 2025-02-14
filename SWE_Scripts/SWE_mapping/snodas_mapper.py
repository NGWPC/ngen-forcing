import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import numpy as np
import geopandas as gpd
from shapely.vectorized import contains
import argparse
import fsspec
#import time
from swe_minmax import get_minmax

def load_and_process_data(netcdf_file, gpkg_file=None, plot_type='grid'):
    """Load and process SWE data from NetCDF and optional geopackage files"""
    #t0 = time.time()
    
    #Populate a dataset with information from a SNODAS NetCDF file
    with fsspec.open(netcdf_file, mode='rb') as f:
        ds = xr.open_dataset(f, chunks=None)
        ds = ds.compute()
    
    #print(f"NetCDF load time: {time.time() - t0:.2f}s")

    #t1 = time.time()
    
    gdf = read_geo(gpkg_file)
    
    # Combine all polygons from divides layer
    basin_geometry = gdf.union_all()
    # Store catchment boundaries
    bounds = basin_geometry.bounds
    
    #print(f"Geometry load time: {time.time() - t1:.2f}s")

    return ds, gdf, basin_geometry, bounds

def read_geo(gpkg_file):
    """Read divides layer from .gpkg file to GeoDataFrame, 
    converts to crs if needed"""
    gdf = gpd.read_file(gpkg_file, layer='divides')
    if not gdf.crs.is_geographic:
        gdf = gdf.to_crs('EPSG:4326')
    return(gdf)

def subset_to_basin(ds, basin_geometry):
    """Subset dataset to basin extent"""
    
    # Use bounds to mask dataset
    bounds = basin_geometry.bounds
    lon_mask = (ds.lon >= bounds[0]) & (ds.lon <= bounds[2])
    lat_mask = (ds.lat >= bounds[1]) & (ds.lat <= bounds[3])
    ds_subset = ds.sel(lon=lon_mask, lat=lat_mask)
    
    # Apply scale factor
    ds_subset['Band1'] = ds_subset.Band1 / 1000
    
    # Create meshgrid 
    lons, lats = np.meshgrid(ds_subset.lon, ds_subset.lat)
    
    return ds_subset, lons, lats

def calculate_catchment_mean(ds, basin_geometry, gdf):
    """Calculate mean SWE for each catchment efficiently"""
    
    #Subset to basin
    ds_subset, lons, lats = subset_to_basin(ds, basin_geometry)
    
    # Calculate catchment means and store in GeoDataFrame
    mean_values = []
    for _, row in gdf.iterrows():
        mask = contains(row.geometry, lons, lats)
        catchment_data = ds_subset.Band1.where(mask)
        mean_swe = float(catchment_data.mean())
        mean_values.append(mean_swe)
        # Fill the grid cells within this catchment with its mean value
        ds_subset['Band1'] = xr.where(mask, mean_swe, ds_subset.Band1)
    
    # Add mean values to GeoDataFrame
    gdf['mean_swe'] = mean_values
    
    # Mask everything outside the basin
    basin_mask = contains(basin_geometry, lons, lats)
    ds_subset['Band1'] = ds_subset.Band1.where(basin_mask)
    
    return gdf, ds_subset

def plot_catchment_boundaries(ax, gdf, proj):
    """Add catchment boundaries to plot"""
    
    #Iterate over polygons in the dataframe, drawing boundaries
    for _, row in gdf.iterrows():
        ax.add_geometries([row.geometry], crs=proj,
                         facecolor='none',
                         edgecolor='black',
                         linewidth=0.5,
                         alpha=0.5)
    return ax

def plot_raw_swe(ax, ds, basin_geometry, gdf, proj):
    """Plot raw SWE values within basin boundary"""
    
    # Subset to basin
    ds_subset, lons, lats = subset_to_basin(ds, basin_geometry)
    
    # Mask to basin and valid values
    basin_mask = contains(basin_geometry, lons, lats)
    swe_data = ds_subset.Band1.astype(float).where(ds_subset.Band1 != -9999)
    swe_data = swe_data.where(basin_mask)
    
    # Determine range for colormap
    vmin, vmax = get_minmax(swe_data)
    
    # Create colormesh for plotting raw values
    im = ax.pcolormesh(ds_subset.lon, ds_subset.lat, swe_data,
                      transform=proj,
                      cmap='Blues',
                      vmin=vmin,
                      vmax=vmax,
                      shading='auto')
    
    # Add catchment boundaries
    ax = plot_catchment_boundaries(ax, gdf, proj)
    
    return ax, im, vmin, vmax

def plot_polygon_swe(ax, gdf, proj):
    """Plot catchments filled with their mean SWE values"""
    
    #Use vmin and vmax to explicitly define a colorbar
    vmin, vmax = get_minmax(gdf['mean_swe'])
    norm = plt.Normalize(vmin=vmin, vmax=vmax)
    cmap = plt.cm.Blues
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    
    # Plot filled polygons
    for _, row in gdf.iterrows():
        ax.add_geometries([row.geometry], crs=proj,
                         facecolor=cmap(norm(row['mean_swe'])),
                         edgecolor='none')
    
    # Add catchment boundaries
    ax = plot_catchment_boundaries(ax, gdf, proj)
    
    return ax, sm, vmin, vmax

def plot_swe_map(netcdf_file, gpkg_file, output_file_raw,
                 output_file_catchment, date_str):
    """Creates a base map, and calls functions to plot SWE data based
     on visualization type.
    
    Arguments:

    netcdf_file: Path to SNODAS NetCDF file.
    gpkg_file: Path to geopackage file.
    output_file_raw: Path where raw visualization output is saved.
    output_file_catchment: Path where catchment-averaged output is saved.
    """
    # Load raw data first
    ds, gdf, basin_geometry, bounds = load_and_process_data(netcdf_file,
                                                          gpkg_file, 
                                                          'raw')
    
    # Create raw plot
    #t3 = time.time()
    proj = ccrs.PlateCarree()
    fig, ax = plt.subplots(figsize=(15, 10), 
                          subplot_kw={'projection': proj})
    
    #Set the extent using dynamic vertical and horizontal buffers
    buff_v = abs(bounds[2]-bounds[0])*.01
    buff_h = abs(bounds[3]-bounds[1])*.01
    ext = [
        bounds[0] - buff_v,
        bounds[2] + buff_v,
        bounds[1] - buff_h,
        bounds[3] + buff_h
    ]
    ax.set_extent(ext, crs=proj)

    # Plot raw values
    ax, im, vmin, vmax = plot_raw_swe(ax, ds, basin_geometry, gdf, proj)
    
    # Plot basin outline
    ax.add_geometries([basin_geometry], crs=proj,
                     facecolor='none', edgecolor='red',
                     linewidth=1.5)
    
    # Plot colorbar based on settings in plot functions
    cbar = plt.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label(f'Snow Water Equivalent (m)', fontsize=10)
    
    plt.title(f'Raw SNODAS Snow Water Equivalent\n {date_str} - 06z')
    
    gl = ax.gridlines(draw_labels=True, linewidth=0.5, 
                      color='gray', alpha=0.5, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False
    #print(f"raw plot time: {time.time() - t3:.2f}s")

    # Saves the raw version to the correct path
    if output_file_raw:
        #t4 = time.time()
        plt.savefig(output_file_raw, dpi=300, bbox_inches='tight')
        plt.close()
        #print(f"raw output time: {time.time() - t4:.2f}s")

    # Calculate catchment means
    #t5 = time.time()
    gdf, ds_catchment = calculate_catchment_mean(ds, basin_geometry, gdf)

    # Create catchment plot
    fig, ax = plt.subplots(figsize=(15, 10), 
                          subplot_kw={'projection': proj})
    ax.set_extent(ext, crs=proj)

    # Plot lumped values
    ax, im, vmin, vmax = plot_polygon_swe(ax, gdf, proj)
    
    # Add basin outlines
    ax.add_geometries([basin_geometry], crs=proj,
                     facecolor='none', edgecolor='red',
                     linewidth=1.5)

    # Plot colorbar based on settings in plot functions
    cbar = plt.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label(f'Snow Water Equivalent (m)', fontsize=10)
    
    plt.title(f'Lumped SNODAS Snow Water Equivalent\n {date_str} - 06z')
    
    gl = ax.gridlines(draw_labels=True, linewidth=0.5, 
                      color='gray', alpha=0.5, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False
    
    #print(f"Lumped plotting time: {time.time() - t5:.2f}s")

    if output_file_catchment:
        #t6=time.time()
        plt.savefig(output_file_catchment, dpi=300, bbox_inches='tight')
        plt.close()
        #print(f"lumped output time: {time.time() - t6:.2f}s")

def get_options(args_list=None):
    """Read and pass in command-line arguments"""
    parser = argparse.ArgumentParser()
    parser.add_argument('date', type=str, 
                        help="Date of SNODAS data to map.")
    parser.add_argument('gpkg_file', type=str,
                        help="Path to geopackage file.")
    parser.add_argument('output_file_raw', type=str,
                        help="Path where raw visualization output is saved.")
    parser.add_argument('output_file_lumped', type=str,
                        help="Path where catchment-averaged output is saved.")
    return parser.parse_args(args_list)

def main(args_list=None):
    args = get_options(args_list)
    file_date = args.date.replace('-', '')
    netcdf_file = f"s3://ngwpc-forcing/snodas_nc/zz_ssmv11034tS__T0001TTNATS{file_date}05HP001.nc"
    plot_swe_map(netcdf_file, args.gpkg_file, args.output_file_raw, args.output_file_lumped, args.date)

if __name__ == "__main__":
    main()

