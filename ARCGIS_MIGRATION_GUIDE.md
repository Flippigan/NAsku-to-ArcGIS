# Inverter Tracker Dashboard → ArcGIS Migration Guide

This document outlines an architecture where **external Python code** manages data and business logic, writes to a **geodatabase**, and **ArcGIS** serves purely as the visualization and alerting layer.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Geodatabase Options](#geodatabase-options)
3. [External Data Pipeline (Python)](#external-data-pipeline-python)
4. [ArcGIS Visualization Tools](#arcgis-visualization-tools)
5. [Alerting & Notifications](#alerting--notifications)
6. [Data Models & Schema](#data-models--schema)
7. [Business Logic Reference](#business-logic-reference)
8. [Coordinate System Notes](#coordinate-system-notes)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXTERNAL CODE (Python)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────────┐    ┌────────────────────────┐    │
│  │ Nasku CSV    │───▶│ Data Processing  │───▶│ Business Logic         │    │
│  │ Ingestion    │    │ & Validation     │    │ (status, %, ETA, etc.) │    │
│  └──────────────┘    └──────────────────┘    └───────────┬────────────┘    │
│                                                          │                  │
│                                                          ▼                  │
│                               ┌───────────────────────────────────────┐    │
│                               │ Write to Geodatabase (arcpy / GDAL)   │    │
│                               └───────────────────────────────────────┘    │
│                                                          │                  │
│  ┌───────────────────────────────────────────────────────┼────────────┐    │
│  │                    ALERTING ENGINE                    │            │    │
│  │  • Boolean conditions (milestone crossed)             │            │    │
│  │  • Continuous thresholds (% > 90)                     │            │    │
│  │  • Outputs: Email, SMS, Webhook, Slack, Teams         │            │    │
│  └───────────────────────────────────────────────────────┘            │    │
└──────────────────────────────────────────────────────────┬────────────────┘
                                                           │
                                                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GEODATABASE                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐ │
│  │ Piles (points)  │  │ Inverters       │  │ Alert_Log                   │ │
│  │ • UPN           │  │ • Name          │  │ • Timestamp                 │ │
│  │ • Status        │  │ • Progress %    │  │ • InverterName              │ │
│  │ • Geometry      │  │ • ETA           │  │ • Threshold                 │ │
│  │ • Timestamps    │  │ • PileRate      │  │ • Message                   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘ │
└──────────────────────────────────────────────────────────┬─────────────────┘
                                                           │
                                                           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     ARCGIS (Visualization Only)                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Web Map      │  │ Dashboard    │  │ Experience   │  │ Field Maps   │   │
│  │              │  │              │  │ Builder      │  │              │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Code lives outside ArcGIS** - All business logic, calculations, and data transformations happen in Python
2. **Geodatabase is the interface** - Python writes computed results; ArcGIS reads and displays them
3. **Pre-computed values** - Progress percentages, ETAs, and statuses are calculated in Python and stored as fields (no Arcade expressions needed)
4. **Alerting is external** - Python monitors conditions and triggers notifications directly

---

## Geodatabase Options

### Option 1: File Geodatabase (Recommended for Small/Medium Projects)

**Best for:** Single-user or small team, local/network deployment, simpler setup

```python
import arcpy

# Create file geodatabase
arcpy.CreateFileGDB_management("/path/to/folder", "PileTracker.gdb")
gdb_path = "/path/to/folder/PileTracker.gdb"
```

**Pros:**
- No database server required
- Easy to copy/backup
- Works with ArcGIS Pro, Online (via publish), and Portal
- Free (no additional licensing)

**Cons:**
- Single editor at a time
- Limited concurrent read performance
- File-based (network latency if on shared drive)

### Option 2: Enterprise Geodatabase (PostgreSQL/SQL Server)

**Best for:** Multi-user editing, high concurrency, enterprise deployment

```python
# Connect to enterprise geodatabase
sde_connection = "/path/to/connection.sde"

# Or create connection file
arcpy.CreateDatabaseConnection_management(
    out_folder_path="/path/to/folder",
    out_name="pile_tracker.sde",
    database_platform="POSTGRESQL",
    instance="hostname",
    database="pile_tracker_db",
    username="gis_user",
    password="***"
)
```

**Pros:**
- Multi-user concurrent editing
- Versioning and replication
- Better performance at scale
- SQL access for reporting

**Cons:**
- Requires ArcGIS Server licensing
- Database administration overhead
- More complex setup

### Option 3: SQLite/GeoPackage (Lightweight Alternative)

**Best for:** Portability, open standards, non-Esri tool compatibility

```python
import sqlite3
from osgeo import ogr

# Create GeoPackage
driver = ogr.GetDriverByName("GPKG")
ds = driver.CreateDataSource("/path/to/PileTracker.gpkg")
```

**Pros:**
- Open standard (OGC GeoPackage)
- Works with QGIS, GDAL, and ArcGIS
- Single file, portable
- No arcpy license required for writing

**Cons:**
- Less native ArcGIS integration
- Limited spatial indexing compared to FGDB

---

## External Data Pipeline (Python)

### Core Architecture

```
nasku_csv → DataProcessor → BusinessLogic → GeodatabaseWriter → AlertEngine
```

### Required Libraries

```python
# Option A: With ArcGIS Pro license (arcpy)
import arcpy
import pandas as pd
from datetime import datetime, timedelta

# Option B: Without ArcGIS license (open source)
from osgeo import ogr, osr
import geopandas as gpd
import pandas as pd
```

### Data Processor Module

```python
"""
nasku_processor.py - Parses Nasku CSV and computes all derived fields
"""
import pandas as pd
from datetime import datetime
import re

def parse_nasku_csv(filepath: str) -> pd.DataFrame:
    """Load and parse Nasku CSV with all computed fields."""
    df = pd.read_csv(filepath)

    # Parse timestamps (strip bracketed timezone)
    df['driven_at'] = df['processedAt'].apply(parse_nasku_timestamp)

    # Compute pile installation status
    df['pile_installed'] = df.apply(
        lambda row: compute_pile_status(row['hammeringStatus'], row['hammeringFlag']),
        axis=1
    )

    # Convert times from milliseconds to seconds
    df['hammering_time_sec'] = df['hammeringTime'] / 1000.0
    df['positioning_time_sec'] = df['positioningTime'] / 1000.0

    # Extract inverter name from UPN (e.g., "INV12-A001" → "INV12")
    df['inverter_name'] = df['name'].apply(extract_inverter_name)

    # Boolean flag for filtering
    df['is_installed'] = df['pile_installed'] == 'Yes'

    return df


def parse_nasku_timestamp(ts_string: str) -> datetime | None:
    """Parse Nasku timestamp, stripping bracketed timezone."""
    if pd.isna(ts_string):
        return None
    # Remove bracketed timezone: "2026-01-16T13:07:21.722-06:00[America/Chicago]"
    clean_ts = re.sub(r'\[.*\]$', '', str(ts_string))
    return pd.to_datetime(clean_ts)


def compute_pile_status(hammering_status: str | None, hammering_flag: str | None) -> str:
    """Determine pile installation status."""
    if hammering_flag == "REFUSED":
        return "Refusal"
    if hammering_status in ("COMPLETED", "SUCCESS"):
        return "Yes"
    return "No"


def extract_inverter_name(upn: str) -> str:
    """Extract inverter identifier from UPN."""
    # Assumes format like "INV12-A001" → "INV12"
    match = re.match(r'^([A-Z]+\d+)', str(upn))
    return match.group(1) if match else "UNKNOWN"
```

### Business Logic Module

```python
"""
business_logic.py - All calculations performed in Python, not ArcGIS
"""
from datetime import datetime, timedelta
import pandas as pd

class InverterStats:
    """Computed statistics for a single inverter."""
    def __init__(self, name: str, piles_df: pd.DataFrame, total_expected: int):
        self.name = name
        self.total_expected = total_expected

        # Filter to this inverter's piles
        inv_piles = piles_df[piles_df['inverter_name'] == name]

        # Core counts
        self.installed_count = len(inv_piles[inv_piles['pile_installed'] == 'Yes'])
        self.refusal_count = len(inv_piles[inv_piles['pile_installed'] == 'Refusal'])
        self.not_installed_count = len(inv_piles[inv_piles['pile_installed'] == 'No'])
        self.total_in_data = len(inv_piles)

        # Progress percentage
        self.progress_pct = (self.installed_count / total_expected * 100) if total_expected > 0 else 0.0

        # Pile rate and ETA
        self.pile_rate = self._calculate_pile_rate(inv_piles)
        self.eta_date = self._calculate_eta()

    def _calculate_pile_rate(self, inv_piles: pd.DataFrame) -> float | None:
        """Calculate piles installed per day."""
        installed = inv_piles[inv_piles['pile_installed'] == 'Yes']
        if installed.empty:
            return None

        timestamps = installed['driven_at'].dropna()
        if timestamps.empty:
            return None

        earliest = timestamps.min()
        days_elapsed = (datetime.now(earliest.tzinfo) - earliest).total_seconds() / 86400

        if days_elapsed < 0.001:  # Less than ~1.4 minutes
            return None

        return self.installed_count / days_elapsed

    def _calculate_eta(self, default_rate: float = 50.0) -> datetime | None:
        """Estimate completion date."""
        remaining = self.total_expected - self.installed_count
        if remaining <= 0:
            return datetime.now()  # Already complete

        rate = self.pile_rate if self.pile_rate else default_rate
        days_to_complete = remaining / rate
        return datetime.now() + timedelta(days=days_to_complete)

    def to_dict(self) -> dict:
        """Convert to dictionary for geodatabase writing."""
        return {
            'inverter_name': self.name,
            'total_expected': self.total_expected,
            'installed_count': self.installed_count,
            'refusal_count': self.refusal_count,
            'progress_pct': round(self.progress_pct, 2),
            'pile_rate': round(self.pile_rate, 2) if self.pile_rate else None,
            'eta_date': self.eta_date,
            'last_updated': datetime.now()
        }
```

### Geodatabase Writer Module

```python
"""
gdb_writer.py - Writes processed data to geodatabase
"""
import arcpy
import pandas as pd
from typing import Optional

class GeodatabaseWriter:
    """Manages writing to file or enterprise geodatabase."""

    def __init__(self, gdb_path: str, spatial_reference_wkid: int = 2277):
        self.gdb_path = gdb_path
        self.sr = arcpy.SpatialReference(spatial_reference_wkid)
        self._ensure_schema()

    def _ensure_schema(self):
        """Create feature classes and tables if they don't exist."""
        arcpy.env.workspace = self.gdb_path

        # Piles feature class (points)
        if not arcpy.Exists("Piles"):
            arcpy.CreateFeatureclass_management(
                self.gdb_path, "Piles", "POINT",
                spatial_reference=self.sr,
                has_z="ENABLED"
            )
            # Add fields
            fields = [
                ("UPN", "TEXT", 50),
                ("InverterName", "TEXT", 20),
                ("PileInstalled", "TEXT", 10),  # "Yes", "No", "Refusal"
                ("IsInstalled", "SHORT"),        # 1 or 0 for filtering
                ("HammeringStatus", "TEXT", 50),
                ("HammeringFlag", "TEXT", 20),
                ("HammeringTimeSec", "DOUBLE"),
                ("PositioningTimeSec", "DOUBLE"),
                ("DrivenAt", "DATE"),
                ("Machine", "TEXT", 50),
                ("LastUpdated", "DATE")
            ]
            for name, dtype, *length in fields:
                if length:
                    arcpy.AddField_management("Piles", name, dtype, field_length=length[0])
                else:
                    arcpy.AddField_management("Piles", name, dtype)

        # Inverters table (non-spatial summary)
        if not arcpy.Exists("Inverters"):
            arcpy.CreateTable_management(self.gdb_path, "Inverters")
            fields = [
                ("InverterName", "TEXT", 20),
                ("TotalExpected", "LONG"),
                ("InstalledCount", "LONG"),
                ("RefusalCount", "LONG"),
                ("ProgressPct", "DOUBLE"),
                ("PileRate", "DOUBLE"),
                ("ETADate", "DATE"),
                ("LastUpdated", "DATE")
            ]
            for name, dtype, *length in fields:
                if length:
                    arcpy.AddField_management("Inverters", name, dtype, field_length=length[0])
                else:
                    arcpy.AddField_management("Inverters", name, dtype)

        # Alert log table
        if not arcpy.Exists("AlertLog"):
            arcpy.CreateTable_management(self.gdb_path, "AlertLog")
            arcpy.AddField_management("AlertLog", "AlertTime", "DATE")
            arcpy.AddField_management("AlertLog", "InverterName", "TEXT", field_length=20)
            arcpy.AddField_management("AlertLog", "AlertType", "TEXT", field_length=50)
            arcpy.AddField_management("AlertLog", "Threshold", "DOUBLE")
            arcpy.AddField_management("AlertLog", "CurrentValue", "DOUBLE")
            arcpy.AddField_management("AlertLog", "Message", "TEXT", field_length=500)

    def upsert_piles(self, piles_df: pd.DataFrame):
        """Insert or update pile records."""
        fc_path = f"{self.gdb_path}/Piles"

        # Get existing UPNs
        existing_upns = set()
        with arcpy.da.SearchCursor(fc_path, ["UPN"]) as cursor:
            for row in cursor:
                existing_upns.add(row[0])

        # Prepare field list
        fields = ["SHAPE@", "UPN", "InverterName", "PileInstalled", "IsInstalled",
                  "HammeringStatus", "HammeringFlag", "HammeringTimeSec",
                  "PositioningTimeSec", "DrivenAt", "Machine", "LastUpdated"]

        # Insert new records
        with arcpy.da.InsertCursor(fc_path, fields) as cursor:
            for _, row in piles_df.iterrows():
                if row['name'] not in existing_upns:
                    point = arcpy.Point(row['resultEasting'], row['resultNorthing'], row['resultAltitude'])
                    cursor.insertRow([
                        arcpy.PointGeometry(point, self.sr),
                        row['name'],
                        row['inverter_name'],
                        row['pile_installed'],
                        1 if row['is_installed'] else 0,
                        row.get('hammeringStatus'),
                        row.get('hammeringFlag'),
                        row.get('hammering_time_sec'),
                        row.get('positioning_time_sec'),
                        row.get('driven_at'),
                        row.get('machine'),
                        pd.Timestamp.now()
                    ])

        # Update existing records
        with arcpy.da.UpdateCursor(fc_path, fields) as cursor:
            for db_row in cursor:
                upn = db_row[1]
                if upn in piles_df['name'].values:
                    df_row = piles_df[piles_df['name'] == upn].iloc[0]
                    cursor.updateRow([
                        db_row[0],  # Keep existing geometry
                        upn,
                        df_row['inverter_name'],
                        df_row['pile_installed'],
                        1 if df_row['is_installed'] else 0,
                        df_row.get('hammeringStatus'),
                        df_row.get('hammeringFlag'),
                        df_row.get('hammering_time_sec'),
                        df_row.get('positioning_time_sec'),
                        df_row.get('driven_at'),
                        df_row.get('machine'),
                        pd.Timestamp.now()
                    ])

    def update_inverter_stats(self, stats: dict):
        """Update or insert inverter summary record."""
        table_path = f"{self.gdb_path}/Inverters"

        # Check if inverter exists
        exists = False
        with arcpy.da.SearchCursor(table_path, ["InverterName"],
                                   f"InverterName = '{stats['inverter_name']}'") as cursor:
            exists = any(True for _ in cursor)

        fields = ["InverterName", "TotalExpected", "InstalledCount", "RefusalCount",
                  "ProgressPct", "PileRate", "ETADate", "LastUpdated"]

        values = [stats['inverter_name'], stats['total_expected'], stats['installed_count'],
                  stats['refusal_count'], stats['progress_pct'], stats['pile_rate'],
                  stats['eta_date'], stats['last_updated']]

        if exists:
            with arcpy.da.UpdateCursor(table_path, fields,
                                       f"InverterName = '{stats['inverter_name']}'") as cursor:
                for row in cursor:
                    cursor.updateRow(values)
        else:
            with arcpy.da.InsertCursor(table_path, fields) as cursor:
                cursor.insertRow(values)

    def log_alert(self, inverter_name: str, alert_type: str, threshold: float,
                  current_value: float, message: str):
        """Write alert to log table."""
        table_path = f"{self.gdb_path}/AlertLog"
        fields = ["AlertTime", "InverterName", "AlertType", "Threshold", "CurrentValue", "Message"]

        with arcpy.da.InsertCursor(table_path, fields) as cursor:
            cursor.insertRow([pd.Timestamp.now(), inverter_name, alert_type,
                              threshold, current_value, message])
```

---

## ArcGIS Visualization Tools

ArcGIS offers several visualization options that consume the geodatabase without requiring business logic.

### 1. ArcGIS Pro (Desktop)

**Use for:** Data authoring, map design, publishing to Portal/Online

- Open geodatabase directly
- Create map layers with symbology
- Publish as web layers to Portal or ArcGIS Online

```
Workflow:
1. Add Piles feature class to map
2. Apply symbology based on PileInstalled field
3. Create Inverters summary table view
4. Design layout/report
5. Share → Web Layer → Publish
```

### 2. ArcGIS Online / Portal Web Maps

**Use for:** Web-based viewing, sharing with stakeholders

| Component | Description |
|-----------|-------------|
| **Web Map** | Interactive map consuming published layers |
| **Pop-ups** | Configured to show pile details on click |
| **Filters** | Filter by inverter, status, date range |
| **Smart Mapping** | Color ramps for continuous values |

**Symbology Configuration (No Arcade Needed):**

| PileInstalled | Color | Symbol |
|---------------|-------|--------|
| Yes | Green (#22c55e) | Solid circle |
| No | Red (#ef4444) | Hollow circle |
| Refusal | Yellow (#eab308) | Triangle |

### 3. ArcGIS Dashboards

**Use for:** Real-time monitoring displays, KPI tracking

| Widget | Data Source | Purpose |
|--------|-------------|---------|
| **Map** | Piles feature class | Spatial visualization |
| **Indicator** | Inverters.ProgressPct | Show completion % |
| **Gauge** | Inverters.ProgressPct | Visual progress meter |
| **List** | Inverters table | Summary per inverter |
| **Serial Chart** | Inverters table | Compare progress across inverters |
| **Pie Chart** | Piles (grouped) | Yes/No/Refusal breakdown |
| **Table** | AlertLog | Recent alerts |

**Dashboard Actions:**
- Click inverter in list → filter map to that inverter's piles
- Click pile on map → show details in sidebar

### 4. ArcGIS Experience Builder

**Use for:** Custom web applications, advanced interactivity

- Drag-and-drop app builder
- More layout flexibility than Dashboards
- Can embed custom widgets
- Supports multiple pages/views

### 5. ArcGIS Field Maps

**Use for:** Mobile field verification, offline viewing

- View pile locations in the field
- Verify installation status on-site
- Works offline with downloaded map areas

### 6. ArcGIS Instant Apps

**Use for:** Quick, purpose-built apps without coding

| Template | Use Case |
|----------|----------|
| **Media Map** | Simple map viewer with legend |
| **Sidebar** | Map with filterable list |
| **Nearby** | Find piles near current location |
| **Chart Viewer** | Map with integrated charts |

---

## Alerting & Notifications

### External Alerting (Recommended)

Keep alerting logic in Python for maximum flexibility and independence from ArcGIS licensing.

```python
"""
alert_engine.py - Monitors conditions and sends notifications
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List
import smtplib
import requests

@dataclass
class AlertCondition:
    """Defines a condition that triggers an alert."""
    name: str
    check_fn: Callable[[dict], bool]  # Returns True if alert should fire
    message_fn: Callable[[dict], str]  # Generates alert message
    cooldown_hours: float = 24.0      # Minimum hours between repeated alerts

class AlertEngine:
    """Monitors inverter stats and triggers alerts."""

    def __init__(self):
        self.conditions: List[AlertCondition] = []
        self.last_fired: dict[str, datetime] = {}  # condition_name:inverter → last fire time

    def add_milestone_alert(self, threshold: float):
        """Alert when progress crosses a threshold."""
        self.conditions.append(AlertCondition(
            name=f"milestone_{int(threshold)}",
            check_fn=lambda stats, prev, t=threshold: (
                prev.get('progress_pct', 0) < t <= stats['progress_pct']
            ),
            message_fn=lambda stats, t=threshold: (
                f"🎯 {stats['inverter_name']} reached {t}% completion! "
                f"({stats['installed_count']}/{stats['total_expected']} piles)"
            )
        ))

    def add_threshold_alert(self, field: str, operator: str, value: float, name: str):
        """Alert when a field crosses a threshold (continuous monitoring)."""
        ops = {
            '>': lambda a, b: a > b,
            '>=': lambda a, b: a >= b,
            '<': lambda a, b: a < b,
            '<=': lambda a, b: a <= b,
            '==': lambda a, b: a == b,
        }
        self.conditions.append(AlertCondition(
            name=name,
            check_fn=lambda stats, prev, f=field, o=ops[operator], v=value: (
                stats.get(f) is not None and o(stats[f], v)
            ),
            message_fn=lambda stats, f=field, op=operator, v=value: (
                f"⚠️ {stats['inverter_name']}: {f} is {stats[f]} ({op} {v})"
            )
        ))

    def check_and_alert(self, current_stats: dict, previous_stats: dict,
                        notifiers: List[Callable[[str], None]]) -> List[str]:
        """Check all conditions and send alerts. Returns list of fired alerts."""
        fired = []

        for condition in self.conditions:
            key = f"{condition.name}:{current_stats['inverter_name']}"

            # Check cooldown
            if key in self.last_fired:
                hours_since = (datetime.now() - self.last_fired[key]).total_seconds() / 3600
                if hours_since < condition.cooldown_hours:
                    continue

            # Check condition
            if condition.check_fn(current_stats, previous_stats):
                message = condition.message_fn(current_stats)

                # Send to all notifiers
                for notify in notifiers:
                    notify(message)

                self.last_fired[key] = datetime.now()
                fired.append(message)

        return fired


# Notifier implementations
def email_notifier(smtp_config: dict) -> Callable[[str], None]:
    """Create email notification function."""
    def send(message: str):
        with smtplib.SMTP(smtp_config['host'], smtp_config['port']) as server:
            server.starttls()
            server.login(smtp_config['user'], smtp_config['password'])
            server.sendmail(
                smtp_config['from'],
                smtp_config['to'],
                f"Subject: Pile Tracker Alert\n\n{message}"
            )
    return send


def slack_notifier(webhook_url: str) -> Callable[[str], None]:
    """Create Slack notification function."""
    def send(message: str):
        requests.post(webhook_url, json={"text": message})
    return send


def teams_notifier(webhook_url: str) -> Callable[[str], None]:
    """Create Microsoft Teams notification function."""
    def send(message: str):
        requests.post(webhook_url, json={"text": message})
    return send


def webhook_notifier(url: str) -> Callable[[str], None]:
    """Create generic webhook notification function."""
    def send(message: str):
        requests.post(url, json={
            "alert": message,
            "timestamp": datetime.now().isoformat()
        })
    return send
```

### Usage Example

```python
# Configure alert engine
engine = AlertEngine()

# Boolean conditions (milestone crossed)
engine.add_milestone_alert(50)
engine.add_milestone_alert(75)
engine.add_milestone_alert(90)

# Continuous conditions
engine.add_threshold_alert('pile_rate', '<', 30.0, 'low_production')
engine.add_threshold_alert('progress_pct', '>=', 100.0, 'complete')

# Configure notifiers
notifiers = [
    slack_notifier("https://hooks.slack.com/services/XXX/YYY/ZZZ"),
    email_notifier({
        'host': 'smtp.company.com',
        'port': 587,
        'user': 'alerts@company.com',
        'password': '***',
        'from': 'alerts@company.com',
        'to': ['team@company.com']
    })
]

# In your processing loop
for inverter_stats in all_stats:
    previous = get_previous_stats(inverter_stats['inverter_name'])
    alerts = engine.check_and_alert(inverter_stats, previous, notifiers)

    # Also log to geodatabase
    for alert_msg in alerts:
        gdb_writer.log_alert(
            inverter_stats['inverter_name'],
            'milestone' if '🎯' in alert_msg else 'threshold',
            0,  # threshold value
            inverter_stats['progress_pct'],
            alert_msg
        )
```

### ArcGIS-Native Alerting Options

If you need alerting within ArcGIS ecosystem:

| Tool | Use Case | Requires |
|------|----------|----------|
| **ArcGIS GeoEvent Server** | Real-time stream processing, complex event rules | ArcGIS Enterprise + GeoEvent license |
| **ArcGIS Workflow Manager** | Task-based alerts, approval workflows | ArcGIS Enterprise |
| **Dashboard Notifications** | Visual alerts on dashboard (no push notifications) | ArcGIS Online/Portal |
| **Survey123 Webhooks** | Trigger on form submission | Survey123 |

**GeoEvent Server** is the most powerful option for real-time alerting within ArcGIS, but adds significant licensing cost and complexity. For most use cases, external Python alerting is simpler and more flexible.

---

## Data Models & Schema

### Piles (Feature Class - Point Geometry)

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `OBJECTID` | OID | Auto | ArcGIS system field |
| `SHAPE` | Point ZM | Computed | Geometry from Easting/Northing/Altitude |
| `UPN` | String(50) | name | Unique Pile Number (primary key) |
| `InverterName` | String(20) | Computed | Extracted from UPN |
| `PileInstalled` | String(10) | Computed | "Yes", "No", or "Refusal" |
| `IsInstalled` | Short | Computed | 1 or 0 (for filtering/statistics) |
| `HammeringStatus` | String(50) | hammeringStatus | Raw status from Nasku |
| `HammeringFlag` | String(20) | hammeringFlag | Raw flag from Nasku |
| `HammeringTimeSec` | Double | Computed | hammeringTime / 1000 |
| `PositioningTimeSec` | Double | Computed | positioningTime / 1000 |
| `DrivenAt` | Date | processedAt | When pile was installed |
| `Machine` | String(50) | machine | Equipment identifier |
| `LastUpdated` | Date | Computed | When record was last modified |

### Inverters (Table - Non-Spatial)

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `OBJECTID` | OID | Auto | ArcGIS system field |
| `InverterName` | String(20) | Computed | Inverter identifier (primary key) |
| `TotalExpected` | Long | Config | Expected total pile count |
| `InstalledCount` | Long | Computed | Piles with PileInstalled="Yes" |
| `RefusalCount` | Long | Computed | Piles with PileInstalled="Refusal" |
| `ProgressPct` | Double | Computed | (InstalledCount/TotalExpected)*100 |
| `PileRate` | Double | Computed | Piles per day |
| `ETADate` | Date | Computed | Estimated completion date |
| `LastUpdated` | Date | Computed | When record was last modified |

### AlertLog (Table - Non-Spatial)

| Field | Type | Description |
|-------|------|-------------|
| `OBJECTID` | OID | ArcGIS system field |
| `AlertTime` | Date | When alert was triggered |
| `InverterName` | String(20) | Which inverter triggered |
| `AlertType` | String(50) | "milestone", "threshold", etc. |
| `Threshold` | Double | Threshold value that was crossed |
| `CurrentValue` | Double | Value when alert fired |
| `Message` | String(500) | Human-readable alert message |

---

## Business Logic Reference

All calculations are performed in Python before writing to geodatabase.

### Pile Installation Status

```
IF hammering_flag == "REFUSED" → "Refusal"
ELSE IF hammering_status IN ("COMPLETED", "SUCCESS") → "Yes"
ELSE → "No"
```

### Progress Percentage

```
progress_pct = (count WHERE pile_installed="Yes") / total_expected * 100
```

### Pile Rate

```
pile_rate = installed_count / days_since_first_installation
```

**Edge cases:** Returns null if no timestamps or < 1.4 minutes elapsed.

### ETA Calculation

```
remaining = total_expected - installed_count
eta = today + (remaining / pile_rate)
```

Falls back to default rate (50 piles/day) if pile_rate unavailable.

### Milestone Thresholds

Default: 50%, 75%, 90%

Alert triggers when progress crosses from below to at-or-above threshold.

---

## Coordinate System Notes

Nasku CSV contains projected coordinates (`resultEasting`, `resultNorthing`), not geographic lat/long.

### Identifying the Coordinate System

1. **Check value ranges:**
   - 100,000-900,000 → State Plane (feet or meters)
   - 166,000-834,000 → UTM (meters)
   - Millions → State Plane US feet

2. **Common systems for US solar projects:**

| System | WKID | Typical Location |
|--------|------|------------------|
| State Plane Texas Central | 2277 | Central Texas |
| State Plane California Zone 5 | 2229 | Southern California |
| UTM Zone 14N | 26914 | Texas, Oklahoma |

3. **Verify** by loading sample points and comparing to known site boundaries.

### Setting in Code

```python
# When creating GeodatabaseWriter
writer = GeodatabaseWriter(
    gdb_path="/path/to/PileTracker.gdb",
    spatial_reference_wkid=2277  # State Plane Texas Central
)
```

---

## Main Processing Script

```python
"""
main.py - Orchestrates the full data pipeline
"""
from nasku_processor import parse_nasku_csv
from business_logic import InverterStats
from gdb_writer import GeodatabaseWriter
from alert_engine import AlertEngine, slack_notifier

# Configuration
GDB_PATH = "/path/to/PileTracker.gdb"
SPATIAL_REF = 2277  # State Plane Texas Central
INVERTER_CONFIG = {
    "INV01": 2000,
    "INV02": 1500,
    "INV03": 1800,
    # ... expected pile counts per inverter
}

def process_nasku_update(csv_path: str):
    """Process new Nasku CSV and update geodatabase."""

    # 1. Parse CSV with all computed fields
    piles_df = parse_nasku_csv(csv_path)

    # 2. Initialize geodatabase writer
    writer = GeodatabaseWriter(GDB_PATH, SPATIAL_REF)

    # 3. Write pile records
    writer.upsert_piles(piles_df)

    # 4. Calculate and write inverter statistics
    engine = AlertEngine()
    engine.add_milestone_alert(50)
    engine.add_milestone_alert(75)
    engine.add_milestone_alert(90)

    notifiers = [slack_notifier("https://hooks.slack.com/...")]

    for inv_name, expected_count in INVERTER_CONFIG.items():
        stats = InverterStats(inv_name, piles_df, expected_count)

        # Get previous stats for comparison
        previous = get_previous_stats(inv_name)  # Implement this

        # Check alerts
        alerts = engine.check_and_alert(stats.to_dict(), previous, notifiers)
        for msg in alerts:
            writer.log_alert(inv_name, 'milestone', 0, stats.progress_pct, msg)

        # Update summary table
        writer.update_inverter_stats(stats.to_dict())

    print(f"Processed {len(piles_df)} piles, updated {len(INVERTER_CONFIG)} inverters")

if __name__ == "__main__":
    import sys
    process_nasku_update(sys.argv[1])
```

---

## Summary

| Concern | Location | Technology |
|---------|----------|------------|
| Data ingestion | External | Python (pandas) |
| Business logic | External | Python |
| Data storage | Geodatabase | File GDB / Enterprise GDB |
| Alerting | External | Python (email, Slack, webhooks) |
| Visualization | ArcGIS | Dashboards, Web Maps, Experience Builder |
| Field access | ArcGIS | Field Maps |

This architecture keeps ArcGIS as a pure visualization layer while maintaining full control over data processing and alerting in external, testable, version-controlled Python code.
