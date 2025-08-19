#!/bin/bash
# 07-autorun-sentinel-no2-date.sh
# Automated workflow for Sentinel NO2 and wind data analysis for a specific date (01-06)
# Usage: bash 07-autorun-sentinel-no2-date.sh yyyymmdd
start_time=$(date +%s)

set -e

# Check if a date is provided
if [ -z "$1" ]; then
    echo "Usage: $0 yyyymmdd"
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source tropomi_analyzer/bin/activate

input_date=$1
# Validate date format (basic check)
if ! [[ "$input_date" =~ ^[0-9]{8}$ ]]; then
    echo "Error: Invalid date format. Please use yyyymmdd."
    deactivate
    exit 1
fi

# No need for today_dash, python scripts can handle yyyymmdd
# today_dash=$(date -d "$input_date" +%Y-%m-%d) 

# 01 - Sentinel NO2 download and processing for a specific date
if [ -f "xx-sentinel-no2-date.py" ]; then
    echo "[01] Running xx-sentinel-no2-date.py for $input_date..."
    python3 xx-sentinel-no2-date.py "$input_date" || { echo "❌ xx-sentinel-no2-date.py failed"; deactivate; exit 1; }
else
    echo "❌ xx-sentinel-no2-date.py not found!"; deactivate; exit 1
fi

# 02 - Download wind data for a specific date
echo "[02] Running yy-get-wind-date.py for $input_date..."
if [ -f "yy-get-wind-date.py" ]; then
    python3 yy-get-wind-date.py "$input_date" || { echo "❌ yy-get-wind-date.py failed"; deactivate; exit 1; }
else
    echo "❌ yy-get-wind-date.py not found!"; deactivate; exit 1
fi

# 03 - Visualize NO2 and wind for a specific date
echo "[03] Running 03-visualize-no2.py for $input_date..."
if [ -f "03-visualize-no2.py" ]; then
    today_str=$(date +%Y%m%d)
    today_nc="nc/NO2_Indonesia_Daily_${today_str}_linear_interp.nc"
    input_nc="nc/NO2_Indonesia_Daily_${input_date}_linear_interp.nc"
    today_wind_nc="nc/wind_${today_str}.nc"
    input_wind_nc="nc/wind_${input_date}.nc"
    # Check that required input files exist for the selected date
    if [ ! -f "$input_nc" ]; then
        echo "❌ Required NO2 NetCDF not found: $input_nc"; deactivate; exit 1
    fi
    if [ ! -f "$input_wind_nc" ]; then
        echo "❌ Required wind NetCDF not found: $input_wind_nc"; deactivate; exit 1
    fi
    # Prepare input symlinks/copies
    if [ -f "$today_nc" ]; then rm -f "$today_nc"; fi
    if [ -f "$today_wind_nc" ]; then rm -f "$today_wind_nc"; fi
    ln -s "../$input_nc" "$today_nc"
    ln -s "../$input_wind_nc" "$today_wind_nc"
    echo "[DEBUG] Symlink for NO2: $today_nc -> $(readlink $today_nc)"
    echo "[DEBUG] Symlink for wind: $today_wind_nc -> $(readlink $today_wind_nc)"
    ls -l nc/NO2_Indonesia_Daily_*_linear_interp.nc
    ls -l nc/wind_*.nc
    # Remove any existing PNG for this date to avoid confusion
    rm -f "png/NO2_Indonesia_Daily_${input_date}_linear_interp.png"
    echo "[DEBUG] Running: python3 03-visualize-no2.py $input_date"
    python3 03-visualize-no2.py "$input_date"
    status=$?
    if [ $status -ne 0 ]; then
        echo "❌ 03-visualize-no2.py failed with exit code $status"
        echo "--- Begin error log ---"
        cat nohup.out 2>/dev/null || echo "(no nohup.out log)"
        echo "--- End error log ---"
        deactivate
        exit 1
    fi
    # Map outputs back to selected date and clean up
    for ext in png json txt; do
        # Rename files with _${today_str}_
        for f in $(ls $ext/*_${today_str}_* 2>/dev/null); do
            newf=$(echo "$f" | sed "s/${today_str}/${input_date}/g")
            if [ "$f" != "$newf" ]; then
                if [ ! "$f" -ef "$newf" ]; then
                    mv "$f" "$newf"
                fi
            fi
        done
        # Rename files with ${today_str} before extension (no underscores)
        for f in $(ls $ext/*${today_str}.* 2>/dev/null); do
            newf=$(echo "$f" | sed "s/${today_str}/${input_date}/g")
            if [ "$f" != "$newf" ]; then
                if [ ! "$f" -ef "$newf" ]; then
                    mv "$f" "$newf"
                fi
            fi
        done
        # Remove any files with today's date (faked) after mapping
        rm -f $ext/*${today_str}*
    done
    # Remove input symlinks
    if [ -L "$today_nc" ]; then rm -f "$today_nc"; fi
    if [ -L "$today_wind_nc" ]; then rm -f "$today_wind_nc"; fi
else
    echo "❌ 03-visualize-no2.py not found!"; deactivate; exit 1
fi

# 04 - Quick Analysis (requires PNG input)
png_input="png/NO2_Indonesia_Daily_${input_date}_linear_interp.png"
today_str=$(date +%Y%m%d)
today_png="png/NO2_Indonesia_Daily_${today_str}_linear_interp.png"
echo "[04] Running 04-quick-analysis.py for $input_date..."
if [ -f "04-quick-analysis.py" ]; then
    if [ -f "$today_png" ]; then rm -f "$today_png"; fi
    if [ -f "$png_input" ]; then ln -s "../$png_input" "$today_png"; fi
    if [ -f "$today_png" ]; then
        python3 04-quick-analysis.py "$input_date" || { echo "❌ 04-quick-analysis.py failed"; deactivate; exit 1; }
        # Map outputs back to selected date and clean up
        for ext in png json txt; do
            # Rename files with _${today_str}_
            for f in $(ls $ext/*_${today_str}_* 2>/dev/null); do
                newf=$(echo "$f" | sed "s/${today_str}/${input_date}/g")
                if [ "$f" != "$newf" ]; then
                    if [ ! "$f" -ef "$newf" ]; then
                        mv "$f" "$newf"
                    fi
                fi
            done
            # Rename files with ${today_str} before extension (no underscores)
            for f in $(ls $ext/*${today_str}.* 2>/dev/null); do
                newf=$(echo "$f" | sed "s/${today_str}/${input_date}/g")
                if [ "$f" != "$newf" ]; then
                    if [ ! "$f" -ef "$newf" ]; then
                        mv "$f" "$newf"
                    fi
                fi
            done
            # Remove any files with today's date (faked) after mapping
            rm -f $ext/*${today_str}*
        done
        rm -f "$today_png"
    else
        echo "❌ Required PNG input not found: $png_input"; deactivate; exit 1
    fi
else
    echo "❌ 04-quick-analysis.py not found!"; deactivate; exit 1
fi

# 05 - Generate windrose data (requires wind netcdf)
wind_nc="nc/wind_${input_date}.nc"
echo "[05] Running 05-generate-windrose-data.py for $input_date..."
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
no2_nc="nc/NO2_Indonesia_Daily_${input_date}_linear_interp.nc"
echo "[06] Running 06-region-average.py for $input_date..."
if [ -f "06-region-average.py" ]; then
    if [ -f "$no2_nc" ]; then
        python3 06-region-average.py "$input_date" || { echo "❌ 06-region-average.py failed"; deactivate; exit 1; }
    else
        echo "❌ Required NO2 NetCDF not found: $no2_nc"; deactivate; exit 1
    fi
else
    echo "❌ 06-region-average.py not found!"; deactivate; exit 1
fi

echo "All steps completed successfully for date $input_date!"

# --- Automated file transfer to webserver ---
maindir="/home/alberthnahas/Documents/SENTINEL-NO2"
webuser="akunirk"
webhost="202.90.198.142"
webbase="/var/www/html/tempatirk/SENTINEL_NO2"
webpass="IRK2024"

for folder in txt json png; do
    src="$maindir/$folder/*"
    dest="$webuser@$webhost:$webbase/$folder"
    echo "Transferring $folder files to webserver..."
    sshpass -p "$webpass" scp -rpv $src $dest
    if [ $? -ne 0 ]; then
        echo "❌ Transfer failed for $folder files" >&2
    else
        echo "✅ $folder files transferred."
    fi
done

# --- Automated rclone upload for nc files ---
echo "Uploading NetCDF files in nc/ to Google Drive..."
NC_DIR="$maindir/nc"
TARGET="gdrive:SENTINEL-5P_NO2_nc_files"

# rclone copy will only copy new or updated files, effectively skipping existing ones.
echo "Uploading files from $NC_DIR to $TARGET..."
rclone copy "$NC_DIR" "$TARGET" --progress
echo "All file transfers finished."

# Cleanup temporary files if needed
rm json/*.json txt/*.txt png/*.png nc/*.nc
echo "Cleanup the json, txt, png, and nc directories."

# Print elapsed time
end_time=$(date +%s)
elapsed=$((end_time - start_time))
hours=$((elapsed / 3600))
minutes=$(( (elapsed % 3600) / 60 ))
seconds=$((elapsed % 60))
if [ $hours -gt 0 ]; then
    printf "Total runtime: %02dh %02dm %02ds (%d seconds)\n" $hours $minutes $seconds $elapsed
elif [ $minutes -gt 0 ]; then
    printf "Total runtime: %02dm %02ds (%d seconds)\n" $minutes $seconds $elapsed
else
    printf "Total runtime: %ds\n" $elapsed
fi

# Deactivate virtual environment
deactivate
echo "Virtual environment deactivated."
