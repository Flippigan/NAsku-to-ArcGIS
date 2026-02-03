"""
nasku_to_gdb.py - Update existing geodatabase records with Nasku CSV data

Usage:
    python nasku_to_gdb.py <nasku_csv_path>

Example:
    python nasku_to_gdb.py "Badger_INV_12_2024-01-29_2026-01-29.csv"
"""

import arcpy
import pandas as pd
import re
from datetime import datetime
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

# Path to your geodatabase
GDB_PATH = r"c:\Users\N4824058\OneDrive - The Boldt Company\Documents\ArcGIS\Projects\MyProject\MyProject.gdb"

# Name of your piles feature class (set to None to auto-detect)
FEATURE_CLASS = None  # Will list available feature classes if None

# Update as-built coordinates from Nasku?
# Set to False if Nasku uses a different coordinate system than your GDB
UPDATE_COORDINATES = False

# =============================================================================
# TRANSFORMATION FUNCTIONS
# =============================================================================

def parse_nasku_timestamp(ts_string: str) -> datetime | None:
    """Parse Nasku timestamp, stripping bracketed timezone.

    Input:  '2026-01-16T13:07:21.722-06:00[America/Chicago]'
    Output: datetime object
    """
    if pd.isna(ts_string) or not ts_string:
        return None
    clean_ts = re.sub(r'\[.*\]$', '', str(ts_string))
    try:
        return pd.to_datetime(clean_ts)
    except:
        return None


def ms_to_min_sec(milliseconds: float) -> tuple[float, float]:
    """Convert milliseconds to (minutes, seconds).

    Input:  17870 (ms)
    Output: (0, 17.87)
    """
    if pd.isna(milliseconds):
        return (None, None)
    total_seconds = milliseconds / 1000.0
    minutes = int(total_seconds // 60)
    seconds = round(total_seconds % 60, 2)
    return (float(minutes), seconds)


def compute_pile_installed(hammering_status: str, hammering_flag: str) -> str:
    """Determine pile installation status.

    Logic:
      - REFUSED flag → "Refusal"
      - COMPLETED/SUCCESS status → "Yes"
      - Otherwise → "No"
    """
    if pd.isna(hammering_flag):
        hammering_flag = ""
    if pd.isna(hammering_status):
        hammering_status = ""

    if hammering_flag == "REFUSED":
        return "Refusal"
    if hammering_status in ("COMPLETED", "SUCCESS"):
        return "Yes"
    return "No"


# =============================================================================
# DATA LOADING
# =============================================================================

def load_nasku_csv(csv_path: str) -> pd.DataFrame:
    """Load Nasku CSV and transform fields for GDB update."""
    df = pd.read_csv(csv_path)

    print(f"  Columns found: {df.columns.tolist()}")

    # Parse timestamp
    df['Drive_Finished_At'] = df['processedAt'].apply(parse_nasku_timestamp)

    # Convert hammering time from ms to min/sec
    time_converted = df['hammeringTime'].apply(ms_to_min_sec)
    df['Drive_Time_MIN'] = time_converted.apply(lambda x: x[0])
    df['Drive_Time_SEC'] = time_converted.apply(lambda x: x[1])

    # Compute pile installed status
    df['Pile_Installed'] = df.apply(
        lambda row: compute_pile_installed(row['hammeringStatus'], row['hammeringFlag']),
        axis=1
    )

    # Rename columns to match GDB schema
    df = df.rename(columns={
        'name': 'UPN',
        'machine': 'Drive_Machine',
        'hammeringStatus': 'Hammering_Status',
        'hammeringFlag': 'Hammering_Flag',
        'resultEasting': 'As_Built_Easting',
        'resultNorthing': 'As_Built_Northing',
        'resultAltitude': 'As_Built_Top_Elev',
    })

    return df


# =============================================================================
# GEODATABASE UPDATE
# =============================================================================

def get_feature_class(gdb_path: str, fc_name: str | None) -> str:
    """Get or detect feature class name."""
    arcpy.env.workspace = gdb_path

    if fc_name:
        if arcpy.Exists(fc_name):
            return fc_name
        else:
            print(f"ERROR: Feature class '{fc_name}' not found")

    # List available feature classes
    fcs = arcpy.ListFeatureClasses()
    tables = arcpy.ListTables()

    print("\nAvailable feature classes:")
    for fc in fcs:
        count = arcpy.GetCount_management(fc)[0]
        print(f"  - {fc} ({count} records)")

    print("\nAvailable tables:")
    for t in tables:
        count = arcpy.GetCount_management(t)[0]
        print(f"  - {t} ({count} records)")

    print("\nSet FEATURE_CLASS in the script to the correct name.")
    return None


def update_geodatabase(df: pd.DataFrame, gdb_path: str, fc_name: str, update_coords: bool) -> dict:
    """Update existing geodatabase records by UPN."""

    fc_path = f"{gdb_path}/{fc_name}"

    # Fields to update
    update_fields = [
        "UPN",
        "Drive_Finished_At",
        "Drive_Machine",
        "Drive_Time_MIN",
        "Drive_Time_SEC",
        "Hammering_Status",
        "Hammering_Flag",
        "Pile_Installed",
    ]

    # Optionally include coordinates
    if update_coords:
        update_fields.extend([
            "As_Built_Easting",
            "As_Built_Northing",
            "As_Built_Top_Elev",
        ])

    # Build lookup dict from dataframe (UPN -> row data)
    nasku_data = {}
    for _, row in df.iterrows():
        upn = int(row['UPN'])
        data = {
            'Drive_Finished_At': row['Drive_Finished_At'],
            'Drive_Machine': row['Drive_Machine'],
            'Drive_Time_MIN': row['Drive_Time_MIN'],
            'Drive_Time_SEC': row['Drive_Time_SEC'],
            'Hammering_Status': row['Hammering_Status'],
            'Hammering_Flag': row['Hammering_Flag'],
            'Pile_Installed': row['Pile_Installed'],
        }
        if update_coords:
            data['As_Built_Easting'] = row['As_Built_Easting']
            data['As_Built_Northing'] = row['As_Built_Northing']
            data['As_Built_Top_Elev'] = row['As_Built_Top_Elev']
        nasku_data[upn] = data

    # Track results
    updated = 0
    not_found_in_gdb = set(nasku_data.keys())  # Start with all, remove as found
    errors = []

    print(f"Scanning {fc_path} for matching UPNs...")
    print(f"  Fields to update: {update_fields[1:]}")  # Skip UPN in display

    with arcpy.da.UpdateCursor(fc_path, update_fields) as cursor:
        for row in cursor:
            upn = row[0]
            if upn in nasku_data:
                data = nasku_data[upn]
                try:
                    new_row = [upn]
                    new_row.append(data['Drive_Finished_At'])
                    new_row.append(data['Drive_Machine'])
                    new_row.append(data['Drive_Time_MIN'])
                    new_row.append(data['Drive_Time_SEC'])
                    new_row.append(data['Hammering_Status'])
                    new_row.append(data['Hammering_Flag'])
                    new_row.append(data['Pile_Installed'])

                    if update_coords:
                        new_row.append(data['As_Built_Easting'])
                        new_row.append(data['As_Built_Northing'])
                        new_row.append(data['As_Built_Top_Elev'])

                    cursor.updateRow(new_row)
                    updated += 1
                    not_found_in_gdb.discard(upn)
                except Exception as e:
                    errors.append((upn, str(e)))

    return {
        'updated': updated,
        'not_found': list(not_found_in_gdb),
        'errors': errors,
        'total_in_csv': len(df),
    }


# =============================================================================
# MAIN
# =============================================================================

def main(csv_path: str):
    """Main entry point."""

    # Verify CSV exists
    if not Path(csv_path).exists():
        print(f"ERROR: CSV not found: {csv_path}")
        return

    print(f"Loading Nasku CSV: {csv_path}")
    df = load_nasku_csv(csv_path)
    print(f"  Loaded {len(df)} records")

    # Show sample of computed values
    print(f"\n  Sample transformations:")
    sample = df.head(2)
    for _, row in sample.iterrows():
        print(f"    UPN {row['UPN']}: {row['Drive_Time_MIN']}min {row['Drive_Time_SEC']}sec, "
              f"Pile_Installed={row['Pile_Installed']}")

    # Verify geodatabase
    print(f"\nConnecting to geodatabase...")
    print(f"  Path: {GDB_PATH}")

    if not arcpy.Exists(GDB_PATH):
        print(f"ERROR: Geodatabase not found at {GDB_PATH}")
        print("Update GDB_PATH at the top of this script.")
        return

    # Get feature class
    fc_name = get_feature_class(GDB_PATH, FEATURE_CLASS)
    if not fc_name:
        return

    # Coordinate update warning
    if UPDATE_COORDINATES:
        print(f"\n⚠️  Coordinate updates ENABLED - As_Built_Easting/Northing/Top_Elev will be overwritten")
    else:
        print(f"\n  Coordinate updates DISABLED (set UPDATE_COORDINATES=True to enable)")

    # Run update
    print(f"\nUpdating records...")
    results = update_geodatabase(df, GDB_PATH, fc_name, UPDATE_COORDINATES)

    # Report results
    print(f"\n{'='*50}")
    print(f"RESULTS")
    print(f"{'='*50}")
    print(f"CSV records:     {results['total_in_csv']}")
    print(f"Updated in GDB:  {results['updated']}")

    if results['not_found']:
        print(f"Not found in GDB: {len(results['not_found'])} UPNs")
        if len(results['not_found']) <= 10:
            print(f"  UPNs: {results['not_found']}")
        else:
            print(f"  First 10: {results['not_found'][:10]}...")

    if results['errors']:
        print(f"Errors: {len(results['errors'])}")
        for upn, err in results['errors'][:5]:
            print(f"  UPN {upn}: {err}")

    if results['updated'] == results['total_in_csv']:
        print(f"\n✓ All records updated successfully")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCurrent configuration:")
        print(f"  GDB_PATH: {GDB_PATH}")
        print(f"  FEATURE_CLASS: {FEATURE_CLASS or '(auto-detect)'}")
        print(f"  UPDATE_COORDINATES: {UPDATE_COORDINATES}")
        sys.exit(1)

    main(sys.argv[1])
