# This script requires the following packages: pip install openeo xarray numpy netCDF4 scipy geopandas shapely

import openeo
import xarray as xr
import numpy as np
import os
import time
from datetime import datetime, timedelta
import netCDF4
from scipy.interpolate import griddata
from shapely.geometry import box
import geopandas as gpd

# --- Core Functions ---

def generate_grid_boxes(total_extent, divisions):
    """Divide a total extent into a grid of smaller bounding boxes."""
    lon_min, lon_max = total_extent["west"], total_extent["east"]
    lat_min, lat_max = total_extent["south"], total_extent["north"]
    x_div, y_div = divisions["x"], divisions["y"]
    lon_step = (lon_max - lon_min) / x_div
    lat_step = (lat_max - lat_min) / y_div
    boxes = {}
    for i in range(x_div):
        for j in range(y_div):
            box_name = f"box_{i+1}_{j+1}"
            west = lon_min + i * lon_step
            east = lon_min + (i + 1) * lon_step
            south = lat_min + j * lat_step
            north = lat_min + (j + 1) * lat_step
            boxes[box_name] = {"west": west, "east": east, "south": south, "north": north}
    return boxes

def process_box(connection, start_date, end_date, box_name, spatial_extent):
    """Process a single box: download, reproject, and save."""
    print(f"🔄 Processing {box_name}...")
    output_filename = os.path.join("nc", f"NO2_{box_name}_{start_date.replace('-', '')}.nc")
    if os.path.exists(output_filename):
        os.remove(output_filename)

    cube = connection.load_collection(
        "SENTINEL_5P_L2",
        spatial_extent=spatial_extent,
        temporal_extent=[start_date, end_date],
        bands=["NO2"]
    ).filter_spatial(gpd.GeoSeries([box(spatial_extent["west"], spatial_extent["south"], spatial_extent["east"], spatial_extent["north"])]).__geo_interface__['features'][0]['geometry'])
    
    cube = cube.reduce_dimension("t", reducer="mean").resample_spatial(projection="EPSG:4326", resolution=0.01)
    
    job = connection.create_job(cube.save_result(format="NetCDF"))
    job.start_and_wait()
    job.get_results().download_file(output_filename)
    print(f"   ✅ Finished: {output_filename}")
    return output_filename

def merge_boxes(date_str, box_files):
    """Merge all box NetCDF files into one Indonesia file."""
    print(f"\n🔗 Merging {len(box_files)} downloaded files...")
    datasets = []
    for file in box_files:
        if os.path.exists(file):
            try:
                ds = xr.open_dataset(file)
                # Round coordinates to fix floating point errors at tile seams
                ds = ds.assign_coords(
                    x=np.round(ds.x, 5),
                    y=np.round(ds.y, 5)
                )
                if "NO2" in ds and ds["NO2"].size > 0:
                    datasets.append(ds)
                else:
                    ds.close()
            except Exception:
                pass # Ignore corrupted files

    if not datasets:
        return None

    merged_ds = xr.combine_by_coords(datasets)
    merged_filename = os.path.join("nc", f"NO2_Indonesia_Daily_{date_str.replace('-', '')}_merged.nc")
    if os.path.exists(merged_filename):
        os.remove(merged_filename)
    merged_ds.to_netcdf(merged_filename)
    print(f"   ✅ Merged data saved as {merged_filename}")
    for ds in datasets: ds.close()
    return merged_filename

def create_netcdf_manually(filename, dataset, date_str):
    """Creates a NetCDF file from scratch using the netCDF4 library."""
    print(f"   -> Building NetCDF file from scratch: {filename}")
    time_dt = datetime.strptime(date_str, "%Y-%m-%d")
    epoch = datetime(1970, 1, 1)
    days_since_epoch = (time_dt - epoch).days

    with netCDF4.Dataset(filename, 'w', format='NETCDF4') as nc:
        nc.createDimension('time', 1)
        nc.createDimension('y', len(dataset.y))
        nc.createDimension('x', len(dataset.x))

        time_var = nc.createVariable('time', 'i4', ('time',)); time_var.units = 'days since 1970-01-01'; time_var.calendar = 'gregorian'; time_var[:] = [days_since_epoch]
        y_var = nc.createVariable('y', 'f4', ('y',)); y_var.units = 'degrees_north'; y_var[:] = dataset.y.values
        x_var = nc.createVariable('x', 'f4', ('x',)); x_var.units = 'degrees_east'; x_var[:] = dataset.x.values

        for var_name in dataset.data_vars:
            var = dataset[var_name]
            nc_var = nc.createVariable(var_name, 'f4', ('time', 'y', 'x',)); setattr(nc_var, 'units', var.attrs.get('units', '')); setattr(nc_var, 'long_name', var.attrs.get('long_name', '')); nc_var[:] = var.values[np.newaxis, :, :]
    print(f"      ✅ Successfully built {filename}")

def process_and_save_data(ds, date_str, method="original"):
    """Processes data and saves it using the manual NetCDF creation method."""
    if "NO2" in ds:
        ds["NO2"] = ds["NO2"] * 6.022e19
        ds["NO2"].attrs = {"units": "molecules/cm^2", "long_name": "Tropospheric vertical column of Nitrogen Dioxide"}

    base_filename = f"NO2_Indonesia_Daily_{date_str.replace('-','')}"
    final_filename = os.path.join("nc", f"{base_filename}_{method}.nc")
    print(f"\n🔄 Preparing final data for method: '{method}'...")
    if os.path.exists(final_filename): os.remove(final_filename)
    create_netcdf_manually(final_filename, ds, date_str)
    return final_filename

def main():
    """Main function to orchestrate the entire workflow."""
    start_time = time.time()
    
    # --- 1. Download and Merge ---
    connection = openeo.connect("openeo.dataspace.copernicus.eu").authenticate_oidc()
    date_str = datetime.now().strftime("%Y-%m-%d")
    grid_boxes = generate_grid_boxes({"west": 95.0, "east": 141.0, "south": -11.0, "north": 6.0}, {"x": 5, "y": 2})
    
    box_files = []
    for name, extent in grid_boxes.items():
        try:
            box_files.append(process_box(connection, date_str, date_str, name, extent))
        except Exception as e:
            print(f"   ❌ Failed to process {name}: {e}")

    if not box_files:
        print("\n❌ No data downloaded. Exiting."); return

    merged_file = merge_boxes(date_str, box_files)
    if not merged_file:
        print("\n❌ Merging failed. Exiting."); return

    # --- 2. Process, Interpolate, and Save ---
    print(f"\n🔄 Processing {merged_file}...")
    ds_full = xr.open_dataset(merged_file)
    ds = ds_full[['NO2']].copy(); ds_full.close()

    _, index = np.unique(ds['y'], return_index=True); ds = ds.isel(y=index).sortby('y')
    _, index = np.unique(ds['x'], return_index=True); ds = ds.isel(x=index).sortby('x')
    print("   ✅ Coordinates cleaned and sorted.")

    final_original_file = process_and_save_data(ds.copy(), date_str, method="original")

    stacked = ds.stack(points=('y', 'x')).dropna(dim='points')
    valid_points = np.vstack((stacked.y.values, stacked.x.values)).T
    valid_values = stacked.NO2.values
    grid_x, grid_y = np.meshgrid(ds.x.values, ds.y.values)

    print("\n🔄 Interpolating data with Scipy Griddata (linear)...")
    griddata_linear = griddata(valid_points, valid_values, (grid_y, grid_x), method='linear')
    linear_ds = xr.Dataset({"NO2": (('y', 'x'), griddata_linear)}, coords={"y": ds.y.values, "x": ds.x.values})
    final_linear_file = process_and_save_data(linear_ds, date_str, method="linear_interp")

    print("\n🔄 Interpolating data with Scipy Griddata (cubic)...")
    griddata_cubic = griddata(valid_points, valid_values, (grid_y, grid_x), method='cubic')
    cubic_ds = xr.Dataset({"NO2": (('y', 'x'), griddata_cubic)}, coords={"y": ds.y.values, "x": ds.x.values})
    final_cubic_file = process_and_save_data(cubic_ds, date_str, method="cubic_interp")

    ds.close()

    # --- 3. Conclusion ---
    end_time = time.time()
    minutes, seconds = divmod(end_time - start_time, 60)
    print(f"\n🎉 Complete workflow finished successfully in {int(minutes)} minutes and {int(seconds)} seconds.")
    print(f"   - Scientific (original) file: {final_original_file}")
    print(f"   - Linear interpolated file:   {final_linear_file}")
    print(f"   - Cubic interpolated file:    {final_cubic_file}")

if __name__ == "__main__":
    main()
