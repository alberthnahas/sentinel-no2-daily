import cdsapi
from datetime import datetime, timedelta
import zipfile
import os
import glob
import shutil

# Get yesterday's date for the request, but use today's date for output filename
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
today_str = datetime.now().strftime('%Y%m%d')

dataset = "cams-global-atmospheric-composition-forecasts"
request = {
    "pressure_level": ["1000"],
    "date": [f"{yesterday}/{yesterday}"],
    "time": ["00:00"],
    "leadtime_hour": ["30"],
    "type": ["forecast"],
    "data_format": "netcdf_zip",
    "variable": [
        "u_component_of_wind",
        "v_component_of_wind"
    ],
    "area": [6, 95, -11, 141]
}

client = cdsapi.Client()
print(f"🔄 Downloading wind data for {yesterday} with 30-hour leadtime...")
zip_path = "download.zip"
client.retrieve(dataset, request).download(zip_path)
print("✅ Wind data download completed!")

# Unzip and move/rename the netcdf file
with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(".")

# Find the extracted netcdf file (assume only one .nc in the zip)
nc_files = glob.glob("*.nc")
if nc_files:
    nc_file = nc_files[0]
    out_path = os.path.join("nc", f"wind_{today_str}.nc")
    shutil.move(nc_file, out_path)
    print(f"✅ Saved: {out_path}")
else:
    print("❌ No netCDF file found in the zip archive!")

# Remove the zip file
os.remove(zip_path)
print("🗑️ Removed zip archive.")