# This script requires the following packages: pip install xarray matplotlib cartopy pillow

import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.colors import ListedColormap, BoundaryNorm
import numpy as np
from PIL import Image # Import Pillow for image handling
import cartopy.io.shapereader as shpreader
import warnings
from datetime import datetime

def load_wind_data_robust(wind_filename):
    """
    Robust wind data loading with multiple fallback approaches to handle xarray compatibility issues.
    """
    approaches = [
        ("standard", {}),
        ("decode_cf_false", {"decode_cf": False}),
        ("netcdf4_engine", {"engine": "netcdf4", "decode_cf": False}),
        ("scipy_engine", {"engine": "scipy"}) if "scipy" in xr.backends.list_engines() else None
    ]
    
    # Filter out None approaches
    approaches = [a for a in approaches if a is not None]
    
    for approach_name, kwargs in approaches:
        try:
            print(f"   🔄 Trying {approach_name} approach...")
            wind_ds = xr.open_dataset(wind_filename, **kwargs)
            
            # Handle different coordinate naming conventions
            if 'longitude' in wind_ds.coords:
                wind_lons = wind_ds['longitude']
                wind_lats = wind_ds['latitude']
            elif 'lon' in wind_ds.coords:
                wind_lons = wind_ds['lon']
                wind_lats = wind_ds['lat']
            else:
                # Try to find longitude-like coordinates
                lon_vars = [var for var in wind_ds.coords if 'lon' in var.lower()]
                lat_vars = [var for var in wind_ds.coords if 'lat' in var.lower()]
                if lon_vars and lat_vars:
                    wind_lons = wind_ds[lon_vars[0]]
                    wind_lats = wind_ds[lat_vars[0]]
                else:
                    raise ValueError("Cannot find longitude/latitude coordinates")
            
            # Extract u and v components - try different indexing approaches
            try:
                # Standard approach
                u_wind = wind_ds['u'].isel(forecast_period=0, forecast_reference_time=0, pressure_level=0)
                v_wind = wind_ds['v'].isel(forecast_period=0, forecast_reference_time=0, pressure_level=0)
            except (KeyError, ValueError):
                try:
                    # Alternative indexing
                    u_wind = wind_ds['u'].isel(**{dim: 0 for dim in wind_ds['u'].dims if dim not in ['latitude', 'longitude', 'lat', 'lon']})
                    v_wind = wind_ds['v'].isel(**{dim: 0 for dim in wind_ds['v'].dims if dim not in ['latitude', 'longitude', 'lat', 'lon']})
                except (KeyError, ValueError):
                    # Last resort - take first elements along all non-spatial dimensions
                    u_data = wind_ds['u']
                    v_data = wind_ds['v']
                    for dim in u_data.dims:
                        if dim not in ['latitude', 'longitude', 'lat', 'lon']:
                            u_data = u_data.isel({dim: 0})
                            v_data = v_data.isel({dim: 0})
                    u_wind = u_data
                    v_wind = v_data
            
            # Calculate wind speed
            wind_speed = np.sqrt(u_wind**2 + v_wind**2)
            
            wind_data = {
                'u': u_wind, 'v': v_wind, 
                'speed': wind_speed,
                'lons': wind_lons, 'lats': wind_lats
            }
            
            print(f"   ✅ Wind data loaded successfully using {approach_name} approach.")
            return wind_data
            
        except Exception as e:
            print(f"   ⚠️ {approach_name} approach failed: {str(e)}")
            if approach_name == approaches[-1][0]:  # Last approach
                print(f"   ❌ All approaches failed. Error details:")
                print(f"      {str(e)}")
                return None
            continue
    
    return None

def visualize_no2_custom(filename, wind_filename=None):
    """
    Visualizes the interpolated NO2 concentration with precise styling and custom shapefiles.
    Optionally adds wind arrows if wind data is provided.
    """
    print(f"🔄 Loading data from {filename}...")
    try:
        ds = xr.open_dataset(filename)
    except FileNotFoundError:
        print(f"❌ Error: File not found at {filename}")
        return

    # Extract data and metadata
    no2_data = ds['NO2'].isel(time=0)
    lons = ds['x']
    lats = ds['y']
    date_str = ds.time.dt.strftime("%Y-%m-%d").values[0]

    print("   ✅ NO2 data loaded.")
    
    # Load wind data if provided with robust error handling
    wind_data = None
    if wind_filename:
        try:
            wind_data = load_wind_data_robust(wind_filename)
            if wind_data is None:
                print(f"ℹ️ Failed to load wind data from {wind_filename}, continuing without wind arrows")
        except FileNotFoundError:
            print(f"ℹ️ Wind file {wind_filename} not found, continuing without wind arrows")

    print("   ✅ Creating custom visualization...")

    # --- Define Exact Colormap and Normalization ---
    colors = [
        '#FFFFFF',   # <2
        '#e6f3ff',   # 2-4
        '#80bfff',   # 4-6
        '#99ff99',   # 6-8
        '#00ff00',   # 8-10
        '#ffcc00',   # 10-15
        '#ff9900',   # 15-20
        '#ff3300',   # 20-25
        '#990000'    # >25
    ]
    boundaries = [0, 2, 4, 6, 8, 10, 15, 20, 25, 40] # Using 40 as a visual upper limit
    
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(boundaries, ncolors=cmap.N, clip=True)

    # Scale the data to match the colorbar units
    no2_scaled = no2_data / 1e15

    # --- Create Plot with tight layout ---
    fig = plt.figure(figsize=(14, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())
    
    # Set map extent: 5S to 9S, and use data's longitude extent
    ax.set_extent([104.5, 115, -9, -5], crs=ccrs.PlateCarree())

    # Set title with date on the right (smaller font, not bold)
    plt.title('TOTAL KOLOM NO₂ TROPOMI SENTINEL-5P', loc='left', fontsize=14)
    plt.title(date_str, loc='right', fontsize=14)

    mesh = ax.pcolormesh(
        lons, lats, no2_scaled,
        transform=ccrs.PlateCarree(),
        cmap=cmap,
        norm=norm,
        shading='auto'
    )

    # --- Add Features with Custom Shapefile ---
    # Add Indonesia provinces shapefile - try multiple possible locations
    shapefile_locations = [
        'Indonesia_38_Provinsi.shp',  # Current directory
        '/home/alberthnahas/Desktop/Indonesia_38_Provinsi.shp',  # Original location
        './Indonesia_38_Provinsi.shp',  # Explicit current directory
        '../Indonesia_38_Provinsi.shp',  # Parent directory
    ]
    
    shapefile_loaded = False
    for shapefile_path in shapefile_locations:
        try:
            provinces = shpreader.Reader(shapefile_path)
            
            for province in provinces.records():
                ax.add_geometries([province.geometry], ccrs.PlateCarree(),
                                facecolor='none', edgecolor='black', linewidth=0.8)
            print(f"✅ Indonesia provinces shapefile loaded from {shapefile_path}")
            shapefile_loaded = True
            break
        except (FileNotFoundError, Exception):
            continue
    
    if not shapefile_loaded:
        print("ℹ️ Indonesia shapefile not found in any expected location, using default boundaries")
        ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
        ax.add_feature(cfeature.BORDERS, linestyle=':')
    
    gl = ax.gridlines(draw_labels=True, linewidth=0.5, color='gray', alpha=0.5, linestyle='--')
    gl.top_labels = False
    gl.right_labels = False

    # --- Add Wind Arrows ---
    if wind_data:
        # Subsample wind data for denser visualization (every 2nd point instead of 4th)
        skip = 2
        u_sub = wind_data['u'][::skip, ::skip]
        v_sub = wind_data['v'][::skip, ::skip]
        speed_sub = wind_data['speed'][::skip, ::skip]
        lon_sub = wind_data['lons'][::skip]
        lat_sub = wind_data['lats'][::skip]
        
        # Create meshgrid for quiver plot
        lon_mesh, lat_mesh = np.meshgrid(lon_sub, lat_sub)
        
        # Convert xarray DataArrays to numpy arrays for easier indexing
        u_np = u_sub.values if hasattr(u_sub, 'values') else np.array(u_sub)
        v_np = v_sub.values if hasattr(v_sub, 'values') else np.array(v_sub)
        speed_np = speed_sub.values if hasattr(speed_sub, 'values') else np.array(speed_sub)
        
        # Filter to show only arrows within the map extent and with significant wind speed
        mask = ((lon_mesh >= 104.5) & (lon_mesh <= 115) & 
                (lat_mesh >= -9) & (lat_mesh <= -5) & 
                (speed_np >= 0.5))  # Lower threshold for more arrows
        
        # Plot shorter, denser wind arrows with colors
        quiver = ax.quiver(
            lon_mesh[mask], lat_mesh[mask], 
            u_np[mask], v_np[mask],
            speed_np[mask],
            transform=ccrs.PlateCarree(),
            cmap='viridis',  # Use viridis colormap instead of greys
            scale=150,  # Higher scale = shorter arrows
            width=0.002,  # Thinner arrows
            alpha=0.8,
            pivot='middle'
        )
        print("   ✅ Wind arrows added.")

    # --- Adjust figure spacing to minimize white space and make room for colorbar ---
    fig.subplots_adjust(left=0.05, right=0.95, top=0.95, bottom=0.18)

    # --- Add BMKG logo positioned exactly at bottom left corner ---
    try:
        logo = Image.open('logo_bmkg.png')
        
        # Get the position of the main map axes after subplots_adjust
        pos = ax.get_position()
        
        # Define logo size in figure coordinates (smaller logo for better placement)
        logo_width = 0.08  # Width as fraction of figure width
        logo_height = 0.08  # Height as fraction of figure height
        
        # Position logo exactly at bottom left corner of the map
        # [left, bottom, width, height] in figure coordinates
        ax_logo = fig.add_axes([
            pos.x0 - 0.01,  # Move further left from map edge
            pos.y0 + 0.01,  # Exact bottom edge of map  
            logo_width,
            logo_height
        ])
        
        ax_logo.imshow(logo)
        ax_logo.axis('off')  # Hide axes
        print("✅ BMKG logo added exactly at bottom left corner")
    except FileNotFoundError:
        print("ℹ️ BMKG logo not found, continuing without logo")
    
    # --- Add Colorbar (precise length control) ---
    # Get the position of the main map axes again (should be the same as main_ax_bbox)
    pos = ax.get_position()
    # Create a new axes for the colorbar, positioned below the main map axes
    # [left, bottom, width, height]
    cbar_ax = fig.add_axes([pos.x0, pos.y0 - 0.1, pos.width, 0.03]) # Adjust y0 and height as needed

    cbar = fig.colorbar(mesh, cax=cbar_ax, orientation='horizontal')
    cbar.set_label('Kolom NO₂ (×10¹⁵ molekul/cm²)', fontsize=12)
    
    tick_locs = [ (boundaries[i] + boundaries[i+1]) / 2 for i in range(len(boundaries)-1) ]
    tick_labels = ['<2', '2-4', '4-6', '6-8', '8-10', '10-15', '15-20', '20-25', '>25']
    cbar.set_ticks(tick_locs)
    cbar.set_ticklabels(tick_labels)

    # --- Add Wind Legend ---
    if wind_data:
        # Create wind legend in top right area
        # Add sample arrows showing different wind speeds
        legend_x = 0.82
        legend_y = 0.7
        legend_width = 0.12
        legend_height = 0.15
        
        # Create axes for wind legend
        ax_wind_legend = fig.add_axes([legend_x, legend_y, legend_width, legend_height])
        ax_wind_legend.set_xlim(0, 1)
        ax_wind_legend.set_ylim(0, 1)
        ax_wind_legend.axis('off')
        
        # Add title for wind legend
        ax_wind_legend.text(0.5, 0.9, 'Angin 1000hPa', ha='center', fontsize=10, fontweight='bold')
        
        # Add sample arrows for different wind speeds with colors
        speeds = [5, 10, 15]  # m/s
        colors = ['#440154', '#31688e', '#35b779']  # Colors from viridis colormap
        for i, (speed, color) in enumerate(zip(speeds, colors)):
            y_pos = 0.7 - i * 0.2
            # Draw colored arrow
            ax_wind_legend.arrow(0.1, y_pos, 0.3, 0, head_width=0.05, 
                               head_length=0.05, fc=color, ec=color)
            # Add speed label
            ax_wind_legend.text(0.5, y_pos, f'{speed}m/s', ha='left', va='center', fontsize=9)
        
        print("   ✅ Wind legend added.")

    # --- Save and Show ---
    output_filename = filename.replace('.nc', '.png')
    plt.savefig(output_filename, dpi=300, bbox_inches='tight', pad_inches=0.05)
    print(f"✅ Visualization saved as {output_filename}")

if __name__ == '__main__':
    # Generate filename with today's date
    today = datetime.now().strftime('%Y%m%d')
    netcdf_file = f'nc/NO2_Indonesia_Daily_{today}_linear_interp.nc'
    wind_file = f'nc/wind_{today}.nc'
    visualize_no2_custom(netcdf_file, wind_file)
