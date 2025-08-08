#!/usr/bin/env python3
"""
06-region-average.py

Calculate NO2 regional averages for Java provinces and identify high pollution kabupaten/kota.
Uses NetCDF files and Indonesian administrative shapefile to compute spatial averages.

Required packages: pip install xarray geopandas numpy rasterio shapely
"""

import os
import sys
import json
import xarray as xr
import geopandas as gpd
import numpy as np
import pandas as pd
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

def load_netcdf_data(date_str):
    """Load NO2 data from linear interpolated NetCDF file for the given date."""
    nc_file = f"nc/NO2_Indonesia_Daily_{date_str}_linear_interp.nc"
    
    if not os.path.exists(nc_file):
        raise FileNotFoundError(f"❌ NetCDF file not found: {nc_file}")
        
    print(f"📂 Loading NetCDF data: {nc_file}")
    try:
        ds = xr.open_dataset(nc_file)
        if 'NO2' in ds.data_vars:
            return ds, nc_file
        else:
            ds.close()
            raise ValueError(f"❌ NO2 variable not found in {nc_file}")
    except Exception as e:
        raise Exception(f"❌ Error loading {nc_file}: {e}")

def load_administrative_shapefile():
    """Load Indonesian administrative GeoJSON and filter for Java provinces."""
    geojson_path = "indonesia_kabkota_38prov.geojson"
    
    if not os.path.exists(geojson_path):
        raise FileNotFoundError(f"❌ GeoJSON file not found: {geojson_path}")
    
    print(f"🗺️ Loading administrative GeoJSON: {geojson_path}")
    gdf = gpd.read_file(geojson_path)
    
    # Java provinces to extract (exact matches in uppercase)
    java_provinces = [
        "BANTEN",
        "JAWA BARAT", 
        "DKI JAKARTA",
        "JAWA TENGAH",
        "DI YOGYAKARTA",
        "JAWA TIMUR"
    ]
    
    province_column = "provinsi"
    kabupaten_column = "kabupaten"
    
    print(f"   ✅ Using columns '{province_column}' and '{kabupaten_column}' for administrative units")
    
    # Filter for Java provinces
    java_gdf = gdf[gdf[province_column].isin(java_provinces)].copy()
    
    if len(java_gdf) == 0:
        print("Available provinces:", sorted(gdf[province_column].unique()))
        raise ValueError("❌ No Java provinces found in GeoJSON file")
    
    print(f"   ✅ Found {len(java_gdf)} kabupaten/kota in Java provinces:")
    for prov in java_provinces:
        count = len(java_gdf[java_gdf[province_column] == prov])
        print(f"      - {prov}: {count} kabupaten/kota")
    
    return java_gdf, province_column, kabupaten_column

def calculate_regional_data(ds, gdf, province_column, kabupaten_column):
    """Calculate NO2 data for provinces and identify high pollution kabupaten/kota."""
    print("\n🧮 Calculating regional data...")
    
    # Get NO2 data array
    no2_data = ds['NO2']
    
    # Get coordinate arrays
    if 'x' in ds.coords and 'y' in ds.coords:
        lons = ds.x.values
        lats = ds.y.values
    elif 'lon' in ds.coords and 'lat' in ds.coords:
        lons = ds.lon.values
        lats = ds.lat.values
    elif 'longitude' in ds.coords and 'latitude' in ds.coords:
        lons = ds.longitude.values
        lats = ds.latitude.values
    else:
        raise ValueError("❌ Could not find longitude/latitude coordinates in NetCDF")
    
    print(f"   📊 Data grid: {len(lats)} x {len(lons)} points")
    print(f"   📍 Lat range: {lats.min():.2f} to {lats.max():.2f}")
    print(f"   📍 Lon range: {lons.min():.2f} to {lons.max():.2f}")
    
    # Get 2D NO2 data
    if no2_data.ndim == 3:  # Has time dimension
        no2_2d = no2_data[0].values  # Use first time slice
    elif no2_data.ndim == 2:  # No time dimension
        no2_2d = no2_data.values
    else:
        raise ValueError(f"❌ Unexpected NO2 data dimensions: {no2_data.shape}")
    
    # Create affine transform
    from affine import Affine
    # Correct pixel size calculation: n points define (n-1) intervals
    pixel_width = (lons.max() - lons.min()) / (len(lons) - 1)
    pixel_height = (lats.max() - lats.min()) / (len(lats) - 1)
    
    # Alternative method: Use rasterio.transform.from_bounds for accurate geospatial transform
    # This is more reliable for satellite data with regular grids
    from rasterio.transform import from_bounds
    transform = from_bounds(lons.min(), lats.min(), lons.max(), lats.max(), 
                          len(lons), len(lats))
    
    # Java provinces list
    java_provinces = [
        "BANTEN",
        "JAWA BARAT", 
        "DKI JAKARTA",
        "JAWA TENGAH",
        "DI YOGYAKARTA",
        "JAWA TIMUR"
    ]
    
    province_results = {}
    high_pollution_areas = []
    
    # Process each province
    for province in java_provinces:
        print(f"\n   🏃 Processing province: {province}")
        
        # Get all kabupaten/kota for this province
        province_gdf = gdf[gdf[province_column] == province]
        
        province_values = []
        province_pixels = 0
        kabupaten_results = []
        
        # Process each kabupaten/kota
        for idx, row in province_gdf.iterrows():
            kabupaten_name = row[kabupaten_column]
            geometry = row.geometry
            
            from rasterio import features
            
            try:
                # FIXED METHOD: Point-in-polygon approach (matches QGIS behavior)
                # This method tests pixel centers directly instead of using geometry_mask
                from shapely.geometry import Point
                
                # Find approximate bounds to limit search area
                bounds = geometry.bounds
                lon_mask = (lons >= bounds[0]) & (lons <= bounds[2])
                lat_mask = (lats >= bounds[1]) & (lats <= bounds[3])
                
                lon_indices = np.where(lon_mask)[0]
                lat_indices = np.where(lat_mask)[0]
                
                # Test each pixel center to see if it's inside the polygon
                pixel_values = []
                
                for i in lat_indices:
                    for j in lon_indices:
                        point = Point(lons[j], lats[i])
                        if geometry.contains(point):
                            if not np.isnan(no2_2d[i, j]):
                                pixel_values.append(no2_2d[i, j])
                
                no2_masked = np.array(pixel_values)
                
                # Filter valid data
                valid_indices = ~np.isnan(no2_masked)
                no2_valid = no2_masked[valid_indices]
                
                if len(no2_valid) > 0:
                    # Filter out negative values for consistent processing
                    no2_positive = no2_valid[no2_valid >= 0]
                    
                    # Calculate statistics for kabupaten/kota using all valid data
                    avg_no2 = np.mean(no2_valid)
                    max_no2 = np.max(no2_valid)
                    pixel_count = len(no2_valid)
                    
                    # Set negative values to zero for display purposes
                    if avg_no2 < 0:
                        avg_no2 = 0.0
                    if max_no2 < 0:
                        max_no2 = 0.0
                    
                    # Add ONLY positive values to province totals for consistent averaging
                    province_values.extend(no2_positive)
                    province_pixels += len(no2_positive)  # Count only positive pixels
                    
                    kabupaten_results.append({
                        'name': kabupaten_name,
                        'average': float(avg_no2),
                        'maximum': float(max_no2),
                        'pixel_count': int(pixel_count)
                    })
                    
                    # Check for high pollution (>5×10¹⁵ molekul/cm²)
                    # Convert threshold: 5×10¹⁵ = 5×10¹⁵
                    high_pollution_threshold = 5e15
                    
                    if avg_no2 > high_pollution_threshold:
                        high_pollution_areas.append({
                            'kabupaten': kabupaten_name,
                            'province': province,
                            'average_no2': float(avg_no2),
                            'maximum_no2': float(max_no2),
                            'average_no2_formatted': float(avg_no2 / 1e15),  # Convert to ×10¹⁵
                            'maximum_no2_formatted': float(max_no2 / 1e15),
                            'pixel_count': int(pixel_count)
                        })
                        print(f"      🚨 HIGH POLLUTION: {kabupaten_name} - Avg: {avg_no2/1e15:.1f}×10¹⁵")
                
            except Exception as e:
                print(f"      ❌ Error processing {kabupaten_name}: {e}")
                continue
        
        # Calculate province average
        if len(province_values) > 0:
            # province_values already contains only positive values
            province_avg = np.mean(province_values)
            province_max = np.max(province_values)
            
            province_results[province] = {
                'average_no2': float(province_avg),
                'maximum_no2': float(province_max),
                'average_no2_formatted': float(province_avg / 1e15),  # Convert to ×10¹⁵
                'maximum_no2_formatted': float(province_max / 1e15),
                'pixel_count': int(province_pixels),
                'kabupaten_count': len(kabupaten_results),
                'kabupaten_data': kabupaten_results
            }
            
            print(f"      ✅ {province}: Avg {province_avg/1e15:.1f}×10¹⁵, Max {province_max/1e15:.1f}×10¹⁵, Pixels: {province_pixels}")
        else:
            print(f"      ⚠️ No valid data for {province}")
            province_results[province] = {
                'average_no2': 0.0,
                'maximum_no2': 0.0,
                'average_no2_formatted': 0.0,
                'maximum_no2_formatted': 0.0,
                'pixel_count': 0,
                'kabupaten_count': 0,
                'kabupaten_data': []
            }
    
    return province_results, high_pollution_areas

def save_json_results(province_results, high_pollution_areas, date_str):
    """Save results to JSON file."""
    output_file = f"json/region_avg_{date_str}.json"
    
    print(f"\n💾 Saving results to: {output_file}")
    
    # Ensure json directory exists
    os.makedirs("json", exist_ok=True)
    
    # Prepare output data
    output_data = {
        'date': f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
        'date_str': date_str,
        'analysis_timestamp': datetime.now().isoformat(),
        'java_provinces': province_results,
        'high_pollution_areas': {
            'threshold_note': 'Areas with average NO2 > 5×10¹⁵ molekul/cm²',
            'threshold_value': 5.0,
            'threshold_unit': '×10¹⁵ molekul/cm²',
            'count': len(high_pollution_areas),
            'areas': high_pollution_areas
        },
        'summary': {
            'total_provinces': len(province_results),
            'total_high_pollution_areas': len(high_pollution_areas),
            'provinces_with_data': len([p for p in province_results.values() if p['pixel_count'] > 0])
        }
    }
    
    # Save JSON file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"   ✅ Results saved to {output_file}")
    return output_file

def main():
    """Main function."""
    print("🚀 TROPOMI NO2 Regional Average Calculator for Java")
    print("=" * 60)
    
    # Check command line argument
    if len(sys.argv) != 2:
        print("Usage: python 06-region-average.py YYYYMMDD")
        print("Example: python 06-region-average.py 20250806")
        sys.exit(1)
    
    date_str = sys.argv[1]
    
    # Validate date format
    try:
        datetime.strptime(date_str, '%Y%m%d')
    except ValueError:
        print("❌ Error: Date must be in YYYYMMDD format")
        print("Example: python 06-region-average.py 20250806")
        sys.exit(1)
    
    print(f"📅 Processing date: {date_str}")
    
    try:
        # Load NetCDF data
        ds, nc_file = load_netcdf_data(date_str)
        
        # Load administrative shapefile
        gdf, province_column, kabupaten_column = load_administrative_shapefile()
        
        # Calculate regional data
        province_results, high_pollution_areas = calculate_regional_data(ds, gdf, province_column, kabupaten_column)
        
        # Save results
        output_file = save_json_results(province_results, high_pollution_areas, date_str)
        
        # Print summary
        print(f"\n🎉 Processing completed successfully!")
        print(f"📊 Province Averages (×10¹⁵ molekul/cm²):")
        
        # Sort provinces by average NO2
        sorted_provinces = sorted(province_results.items(), 
                                key=lambda x: x[1]['average_no2'], reverse=True)
        
        for prov_name, data in sorted_provinces:
            if data['pixel_count'] > 0:
                print(f"   {prov_name}: Avg {data['average_no2_formatted']:.1f}, Max {data['maximum_no2_formatted']:.1f}")
        
        # Print high pollution areas
        if high_pollution_areas:
            print(f"\n🚨 High Pollution Areas (>{5.0}×10¹⁵ molekul/cm²):")
            for area in high_pollution_areas:
                print(f"   {area['kabupaten']}, {area['province']}: {area['average_no2_formatted']:.1f}×10¹⁵")
        else:
            print(f"\n✅ No areas exceed the high pollution threshold of 5.0×10¹⁵ molekul/cm²")

        print(f"\n📄 Output file: {output_file}")
        print(f"🔗 Use this file for dashboard integration and further analysis")
        
        # Close NetCDF file
        ds.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
