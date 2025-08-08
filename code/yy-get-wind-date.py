import cdsapi
import sys
from datetime import datetime

def validate_date(date_string):
    """Validate date format YYYY-MM-DD."""
    try:
        datetime.strptime(date_string, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def main():
    # Check for date argument
    if len(sys.argv) != 2:
        print("Usage: python yy-get-wind-date.py YYYY-MM-DD")
        print("Example: python yy-get-wind-date.py 2023-12-15")
        sys.exit(1)
    
    date_str = sys.argv[1]
    
    # Validate date format
    if not validate_date(date_str):
        print("❌ Error: Date must be in YYYY-MM-DD format")
        print("Example: python yy-get-wind-date.py 2023-12-15")
        sys.exit(1)
    
    print(f"📅 Processing wind data for date: {date_str}")

    dataset = "cams-global-atmospheric-composition-forecasts"
    request = {
        "pressure_level": ["1000"],
        "date": [f"{date_str}/{date_str}"],
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
    print(f"🔄 Downloading wind data for {date_str} with 30-hour leadtime...")
    client.retrieve(dataset, request).download()
    print("✅ Wind data download completed!")

if __name__ == "__main__":
    main()