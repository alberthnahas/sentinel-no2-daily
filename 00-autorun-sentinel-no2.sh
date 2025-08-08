#!/bin/bash
# 00-autorun-sentinel-no2.sh
# Automated workflow for Sentinel NO2 and wind data analysis (01-06)
# Usage: bash 00-autorun-sentinel-no2.sh

set -e

# Activate virtual environment
echo "Activating virtual environment..."
source tropomi_analyzer/bin/activate

today=$(date +%Y%m%d)
today_dash=$(date +%Y-%m-%d)

# 01 - Sentinel NO2 download and processing
if [ -f "01-sentinel-no2-final.py" ]; then
    echo "\n[01] Running 01-sentinel-no2-final.py..."
    python3 01-sentinel-no2-final.py || { echo "❌ 01-sentinel-no2-final.py failed"; deactivate; exit 1; }
else
    echo "❌ 01-sentinel-no2-final.py not found!"; deactivate; exit 1
fi

# 02 - Download wind data
echo "\n[02] Running 02-get-wind.py..."
if [ -f "02-get-wind.py" ]; then
    python3 02-get-wind.py || { echo "❌ 02-get-wind.py failed"; deactivate; exit 1; }
else
    echo "❌ 02-get-wind.py not found!"; deactivate; exit 1
fi

# 03 - Visualize NO2 and wind
echo "\n[03] Running 03-visualize-no2.py..."
if [ -f "03-visualize-no2.py" ]; then
    python3 03-visualize-no2.py || { echo "❌ 03-visualize-no2.py failed"; deactivate; exit 1; }
else
    echo "❌ 03-visualize-no2.py not found!"; deactivate; exit 1
fi

# 04 - Analisis cepat ID (requires PNG input)
png_input="png/NO2_Indonesia_Daily_${today}_linear_interp.png"
echo "\n[04] Running 04-analisis-cepat-id.py..."
if [ -f "04-analisis-cepat-id.py" ]; then
    if [ -f "$png_input" ]; then
        python3 04-analisis-cepat-id.py || { echo "❌ 04-analisis-cepat-id.py failed"; deactivate; exit 1; }
    else
        echo "❌ Required PNG input not found: $png_input"; deactivate; exit 1
    fi
else
    echo "❌ 04-analisis-cepat-id.py not found!"; deactivate; exit 1
fi

# 05 - Generate windrose data (requires wind netcdf)
wind_nc="nc/wind_${today}.nc"
echo "\n[05] Running 05-generate-windrose-data.py..."
if [ -f "05-generate-windrose-data.py" ]; then
    if [ -f "$wind_nc" ]; then
        python3 05-generate-windrose-data.py "$wind_nc" || { echo "❌ 05-generate-windrose-data.py failed"; deactivate; exit 1; }
    else
        echo "❌ Required wind NetCDF not found: $wind_nc"; deactivate; exit 1
    fi
else
    echo "❌ 05-generate-windrose-data.py not found!"; deactivate; exit 1
fi

# 06 - Region average (requires NO2 NetCDF)
no2_nc="nc/NO2_Indonesia_Daily_${today}_linear_interp.nc"
echo "\n[06] Running 06-region-average.py..."
if [ -f "06-region-average.py" ]; then
    if [ -f "$no2_nc" ]; then
        python3 06-region-average.py "$today" || { echo "❌ 06-region-average.py failed"; deactivate; exit 1; }
    else
        echo "❌ Required NO2 NetCDF not found: $no2_nc"; deactivate; exit 1
    fi
else
    echo "❌ 06-region-average.py not found!"; deactivate; exit 1
fi

echo "\nAll steps completed successfully!"

# --- Automated file transfer to webserver ---
maindir="/home/alberthnahas/Documents/SENTINEL-NO2"
webuser="akunirk"
webhost="202.90.198.142"
webbase="/var/www/html/tempatirk/SENTINEL-NO2"
webpass="IRK2024"

for folder in txt json png; do
    src="$maindir/$folder/*"
    dest="$webuser@$webhost:$webbase/$folder"
    echo "\nTransferring $folder files to webserver..."
    sshpass -p "$webpass" scp -rpv $src $dest
    if [ $? -ne 0 ]; then
        echo "❌ Transfer failed for $folder files" >&2
    else
        echo "✅ $folder files transferred."
    fi
done

# --- Automated rclone upload for nc files ---
echo "\nUploading NetCDF files in nc/ to Google Drive..."
NC_DIR="$maindir/nc"
PATTERN="*.nc"
TARGET="gdrive:SENTINEL-5P_NO2_nc_files"

# Optionally, skip files already uploaded (add logic if needed)
SKIPPED_FILES=()

for FILE in "$NC_DIR"/$PATTERN; do
    if [ -f "$FILE" ]; then
        FILENAME=$(basename "$FILE")
        SHOULD_SKIP=false
        for SKIPPED in "${SKIPPED_FILES[@]}"; do
            if [ "$FILENAME" == "$SKIPPED" ]; then
                SHOULD_SKIP=true
                break
            fi
        done
        if [ "$SHOULD_SKIP" == true ]; then
            echo "Skipping already uploaded file: $FILENAME"
            continue
        fi
        echo "Uploading $FILE to $TARGET..."
        rclone copy "$FILE" "$TARGET"
        if [ $? -ne 0 ]; then
            echo "Upload failed for $FILE" >&2
        else
            echo "✅ Uploaded: $FILENAME"
        fi
    fi
done

echo "All file transfers finished."

# Deactivate virtual environment
deactivate
echo "Virtual environment deactivated."
