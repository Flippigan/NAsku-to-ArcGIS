# Nasku to ArcGIS Migration

Update your ArcGIS geodatabase with pile installation data from Nasku CSV exports.

## Overview

```
Nasku CSV Export                    ArcGIS Geodatabase
─────────────────                   ──────────────────
name              ──────────────►   UPN (match key)
processedAt       ──────────────►   Drive_Finished_At
machine           ──────────────►   Drive_Machine
hammeringTime     ── convert ───►   Drive_Time_MIN, Drive_Time_SEC
hammeringStatus   ──────────────►   Hammering_Status
hammeringFlag     ──────────────►   Hammering_Flag
(computed)        ──────────────►   Pile_Installed
```

## Prerequisites

- **ArcGIS Pro** installed (provides arcpy and Python environment)
- **pandas** installed in ArcGIS Pro's Python environment
- Access to your geodatabase (`.gdb`)
- Nasku CSV export file(s)

## Setup

### 1. Install pandas in ArcGIS Pro Python

Open **Python Command Prompt** (comes with ArcGIS Pro) and run:

```bash
conda activate arcgispro-py3
conda install pandas
```

Or from ArcGIS Pro:
1. Go to **Project** > **Python** > **Manage Environments**
2. Clone the default environment
3. Add pandas package

### 2. Configure the Script

Open `nasku_to_gdb.py` and update the configuration section (lines 21-29):

```python
# Path to your geodatabase
GDB_PATH = r"c:\Users\N4824058\OneDrive - The Boldt Company\Documents\ArcGIS\Projects\MyProject\MyProject.gdb"

# Name of your piles feature class (set to None to auto-detect first run)
FEATURE_CLASS = None  # e.g., "Piles" or "PileData"

# Update as-built coordinates from Nasku?
UPDATE_COORDINATES = False  # Keep False unless CRS matches
```

### 3. Find Your Feature Class Name (First Run)

Run the script without setting `FEATURE_CLASS` to see available options:

```bash
python nasku_to_gdb.py "Badger_INV_12_2024-01-29_2026-01-29.csv"
```

Output will show:
```
Available feature classes:
  - Piles (61904 records)
  - SiteFeatures (234 records)

Set FEATURE_CLASS in the script to the correct name.
```

Then update `FEATURE_CLASS = "Piles"` (or whatever your feature class is named).

## Usage

### Basic Usage

```bash
python nasku_to_gdb.py <path_to_nasku_csv>
```

### Examples

Single inverter update:
```bash
python nasku_to_gdb.py "Badger_INV_12_2024-01-29_2026-01-29.csv"
```

With full path:
```bash
python nasku_to_gdb.py "C:\Data\Nasku\Badger_INV_12_2024-01-29_2026-01-29.csv"
```

### Batch Processing Multiple Files

Create a batch file (`update_all.bat`):

```batch
@echo off
cd /d "C:\Path\To\Nasku\Exports"

python nasku_to_gdb.py "Badger_INV_01_2024-01-29_2026-01-29.csv"
python nasku_to_gdb.py "Badger_INV_02_2024-01-29_2026-01-29.csv"
python nasku_to_gdb.py "Badger_INV_03_2024-01-29_2026-01-29.csv"
REM ... add more as needed

echo Done!
pause
```

## Field Mappings

| Nasku CSV Field | GDB Field | Transformation |
|-----------------|-----------|----------------|
| `name` | `UPN` | Direct (integer match key) |
| `processedAt` | `Drive_Finished_At` | Strip timezone bracket |
| `machine` | `Drive_Machine` | Direct |
| `hammeringTime` | `Drive_Time_MIN` | milliseconds ÷ 60000 |
| `hammeringTime` | `Drive_Time_SEC` | (milliseconds ÷ 1000) mod 60 |
| `hammeringStatus` | `Hammering_Status` | Direct |
| `hammeringFlag` | `Hammering_Flag` | Direct |
| (computed) | `Pile_Installed` | See logic below |

### Pile_Installed Logic

```
IF hammeringFlag == "REFUSED"       → "Refusal"
ELSE IF hammeringStatus == "COMPLETED" or "SUCCESS" → "Yes"
ELSE                                → "No"
```

## Output

Successful run:
```
Loading Nasku CSV: Badger_INV_12_2024-01-29_2026-01-29.csv
  Columns found: ['name', 'processedAt', 'machine', ...]
  Loaded 1327 records

  Sample transformations:
    UPN 27117: 0.0min 17.87sec, Pile_Installed=Yes
    UPN 29852: 2.0min 45.18sec, Pile_Installed=Yes

Connecting to geodatabase...
  Path: c:\Users\...\MyProject.gdb

  Coordinate updates DISABLED (set UPDATE_COORDINATES=True to enable)

Updating records...
Scanning c:\Users\...\MyProject.gdb/Piles for matching UPNs...
  Fields to update: ['Drive_Finished_At', 'Drive_Machine', ...]

==================================================
RESULTS
==================================================
CSV records:     1327
Updated in GDB:  1327

✓ All records updated successfully
```

## Troubleshooting

### "Import arcpy could not be resolved"

This is normal in VS Code or standard Python. The script must be run from ArcGIS Pro's Python environment:

1. Open **Python Command Prompt** (Start Menu > ArcGIS > Python Command Prompt)
2. Navigate to script location: `cd "C:\Path\To\Script"`
3. Run: `python nasku_to_gdb.py "file.csv"`

### "Geodatabase not found"

- Verify `GDB_PATH` in the script matches your actual geodatabase location
- Use raw string (prefix with `r`): `r"c:\path\to\file.gdb"`
- Check OneDrive sync status if geodatabase is in OneDrive folder

### "UPNs not found in GDB"

The script only updates existing records. If UPNs from Nasku aren't found:

1. Verify the CSV `name` field contains UPN integers that match your GDB
2. Check if piles were loaded into the geodatabase
3. Look for leading zeros or formatting differences

### "pandas not found"

Install pandas in ArcGIS Pro's Python:

```bash
conda activate arcgispro-py3
conda install pandas
```

### Coordinate System Mismatch

Nasku coordinates may be in a different coordinate system than your GDB. Keep `UPDATE_COORDINATES = False` unless you've verified they match. Signs of mismatch:

- Nasku: ~689,000 / ~111,000 (possibly UTM)
- GDB: ~2,265,000 / ~374,000 (possibly State Plane)

## File Structure

```
NAsku to ArcGIS/
├── README.md                              # This file
├── nasku_to_gdb.py                        # Main update script
├── ARCGIS_MIGRATION_GUIDE.md              # Architecture reference
├── GeoDatabase_Access.md                  # GDB access patterns
├── Badger_INV_12_2024-01-29_2026-01-29.csv  # Sample Nasku export
└── Drive Log 1-10-2026.xls                # GDB schema reference
```

## Notes

- **Updates only**: Script does not insert new piles. All piles must exist in GDB first.
- **Safe by default**: Coordinate updates disabled to prevent CRS mismatches.
- **OneDrive caution**: Close ArcGIS Pro before running to avoid file locks. Ensure OneDrive sync is complete.
- **Backup**: Consider backing up your geodatabase before large updates.
