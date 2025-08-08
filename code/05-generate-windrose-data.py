#!/usr/bin/env python3
"""
05-generate-windrose-data.py

Process a NetCDF wind data file (like GFS data) to generate a JSON file 
containing binned wind speed and direction data, suitable for creating a 
wind rose chart.

Required packages: pip install xarray numpy pandas
"""

import xarray as xr
import numpy as np
import json
import sys
import os
from datetime import datetime

def calculate_wind_data(ds):
    """Extracts and calculates wind speed and direction from the dataset for a specific region."""
    print("🌬️  Calculating wind speed and direction for Java region...")
    
    # Select the first forecast time and the 1000 hPa pressure level
    if 'pressure_level' in ds.dims:
        ds_surface = ds.sel(pressure_level=1000)
    else:
        ds_surface = ds
        
    if 'forecast_reference_time' in ds.dims:
        ds_surface = ds_surface.isel(forecast_reference_time=0)
    if 'forecast_period' in ds.dims:
        ds_surface = ds_surface.isel(forecast_period=0)

    # Get coordinates and data
    lats = ds_surface['latitude'].values
    lons = ds_surface['longitude'].values
    u_wind_full = ds_surface['u'].values
    v_wind_full = ds_surface['v'].values
    
    # Define bounding box for Java
    lat_min, lat_max = -9, -5
    lon_min, lon_max = 104.5, 115
    
    # Find indices for the bounding box
    lat_indices = np.where((lats >= lat_min) & (lats <= lat_max))[0]
    lon_indices = np.where((lons >= lon_min) & (lons <= lon_max))[0]
    
    if len(lat_indices) == 0 or len(lon_indices) == 0:
        raise ValueError("❌ No data found within the specified bounding box.")

    # Slice the data arrays to the bounding box
    # Correctly handle cases where dimensions might be reversed (lat, lon) or (lon, lat)
    if ds_surface['u'].dims == ('latitude', 'longitude'):
        u_wind_regional = u_wind_full[lat_indices.min():lat_indices.max()+1, lon_indices.min():lon_indices.max()+1]
        v_wind_regional = v_wind_full[lat_indices.min():lat_indices.max()+1, lon_indices.min():lon_indices.max()+1]
    elif ds_surface['u'].dims == ('longitude', 'latitude'):
        u_wind_regional = u_wind_full[lon_indices.min():lon_indices.max()+1, lat_indices.min():lat_indices.max()+1]
        v_wind_regional = v_wind_full[lon_indices.min():lon_indices.max()+1, lat_indices.min():lat_indices.max()+1]
    else:
        raise ValueError(f"Unsupported dimension order: {ds_surface['u'].dims}")

    # Flatten the regional data
    u_wind = u_wind_regional.flatten()
    v_wind = v_wind_regional.flatten()

    # Remove NaN values to avoid errors in calculations
    valid_indices = ~np.isnan(u_wind) & ~np.isnan(v_wind)
    u_wind = u_wind[valid_indices]
    v_wind = v_wind[valid_indices]

    # Calculate wind speed (m/s)
    wind_speed = np.sqrt(u_wind**2 + v_wind**2)
    
    # Calculate wind direction (degrees)
    # Converts from meteorological angle (where wind comes from)
    wind_dir = (np.arctan2(u_wind, v_wind) * 180 / np.pi + 360) % 360
    
    print(f"   ✅ Calculated speed and direction for {len(wind_speed)} data points within the region.")
    return wind_speed, wind_dir

def bin_wind_data(wind_speed, wind_dir):
    """Bins wind data into direction and speed categories for a wind rose."""
    print("📊 Binning wind data...")
    
    # Define 16 direction bins (N, NNE, NE, etc.)
    dir_bins = np.arange(-11.25, 360, 22.5)
    dir_labels = [
        "Utara", "Utara-Timur Laut", "Timur Laut", "Timur-Timur Laut", 
        "Timur", "Timur-Tenggara", "Tenggara", "Selatan-Tenggara",
        "Selatan", "Selatan-Barat Daya", "Barat Daya", "Barat-Barat Daya", 
        "Barat", "Barat-Barat Laut", "Barat Laut", "Utara-Barat Laut"
    ]
    
    # Define speed bins (in m/s)
    speed_bins = [0, 2, 4, 6, 8, 10, 12, np.inf]
    speed_labels = ["0-2", "2-4", "4-6", "6-8", "8-10", "10-12", "12+"]
    
    # Create a table to hold the binned data
    # Rows: Directions, Columns: Speeds
    binned_data = np.zeros((len(dir_labels), len(speed_labels)), dtype=int)
    
    # Get the corresponding direction bin index for each data point
    dir_indices = np.digitize(wind_dir, bins=dir_bins) % 16
    
    # Get the corresponding speed bin index for each data point
    speed_indices = np.digitize(wind_speed, bins=speed_bins) - 1

    # Populate the binned_data table
    for i in range(len(wind_speed)):
        dir_idx = dir_indices[i]
        speed_idx = speed_indices[i]
        if 0 <= speed_idx < len(speed_labels):
            binned_data[dir_idx, speed_idx] += 1
            
    # Convert counts to percentages
    total_counts = np.sum(binned_data)
    if total_counts > 0:
        binned_percentage = (binned_data / total_counts) * 100
    else:
        binned_percentage = binned_data

    print("   ✅ Data binned successfully.")
    return dir_labels, speed_labels, binned_percentage.tolist()

def save_to_json(dir_labels, speed_labels, binned_data, output_filename):
    """Saves the binned wind data to a JSON file."""
    print(f"💾 Saving data to {output_filename}...")
    
    # Structure the data for easy consumption by charting libraries
    json_output = {
        "direction_labels": dir_labels,
        "speed_labels": speed_labels,
        "data": binned_data
    }
    
    with open(output_filename, 'w') as f:
        json.dump(json_output, f, indent=4)
        
    print(f"   ✅ JSON file created successfully.")

def main():
    """Main function to generate wind rose data."""
    print("🚀 Wind Rose Data Generator")
    print("=" * 60)
    
    if len(sys.argv) != 2:
        print("Usage: python 05-generate-windrose-data.py <input_netcdf_file>")
        print("Example: python 05-generate-windrose-data.py wind/wind_20250806.nc")
        sys.exit(1)
        
    input_file = sys.argv[1]
    
    # Extract date from filename (e.g., wind_20250806.nc -> 20250806)
    try:
        date_str = os.path.basename(input_file).split('_')[1].split('.')[0]
        datetime.strptime(date_str, '%Y%m%d') # Validate format
    except (IndexError, ValueError):
        print(f"❌ Error: Could not parse date from filename: {input_file}")
        print("   Filename must be in 'wind_YYYYMMDD.nc' format.")
        sys.exit(1)
    
    if not os.path.exists(input_file):
        print(f"❌ Error: Input file not found at {input_file}")
        sys.exit(1)
        
    # Create json directory if it doesn't exist
    os.makedirs("json", exist_ok=True)
    
    output_file = f"json/windrose_data_{date_str}.json"
    
    try:
        # Load data
        print(f"📂 Loading NetCDF data from: {input_file}")
        with xr.open_dataset(input_file) as ds:
            # Calculate speed and direction
            wind_speed, wind_dir = calculate_wind_data(ds)
            
            # Bin the data
            dir_labels, speed_labels, binned_data = bin_wind_data(wind_speed, wind_dir)
            
            # Save to JSON
            save_to_json(dir_labels, speed_labels, binned_data, output_file)
            
            print(f"\n🎉 Wind rose data generation complete!")
            print(f"📄 Output file: {output_file}")

    except Exception as e:
        print(f"❌ An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
