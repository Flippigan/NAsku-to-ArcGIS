# Programmatic Access to ArcGIS Geodatabase

You can programmatically access your ArcGIS geodatabase using **ArcPy** (Esri's Python library for ArcGIS automation).

## Basic Access Methods

### 1. Access the geodatabase directly

```python
import arcpy

# Set the workspace to your geodatabase
gdb_path = r"c:\Users\N4824058\OneDrive - The Boldt Company\Documents\ArcGIS\Projects\MyProject\MyProject.gdb"
arcpy.env.workspace = gdb_path

# List all feature classes and tables
feature_classes = arcpy.ListFeatureClasses()
tables = arcpy.ListTables()
print(f"Feature Classes: {feature_classes}")
print(f"Tables: {tables}")
```

### 2. Access through the ArcGIS Project (.aprx)

```python
import arcpy

# Open the project
aprx_path = r"c:\Users\N4824058\OneDrive - The Boldt Company\Documents\ArcGIS\Projects\MyProject\MyProject.aprx"
aprx = arcpy.mp.ArcGISProject(aprx_path)

# Access maps and layers
for map_obj in aprx.listMaps():
    print(f"Map: {map_obj.name}")
    for layer in map_obj.listLayers():
        print(f"  Layer: {layer.name}")
        # Access the underlying data source
        if hasattr(layer, 'dataSource'):
            print(f"    Data Source: {layer.dataSource}")
```

### 3. Query a specific table

```python
import arcpy

gdb_path = r"c:\Users\N4824058\OneDrive - The Boldt Company\Documents\ArcGIS\Projects\MyProject\MyProject.gdb"
arcpy.env.workspace = gdb_path

# Read data from a table
table_name = "YourTableName"
fields = ["FIELD1", "FIELD2"]

with arcpy.da.SearchCursor(table_name, fields) as cursor:
    for row in cursor:
        print(row)
```

## Prerequisites

- **ArcGIS Pro** or **ArcGIS Desktop** installed
- **ArcPy** package available (comes with ArcGIS Pro installation)

## Geodatabase Path

Your geodatabase location:
```
c:\Users\N4824058\OneDrive - The Boldt Company\Documents\ArcGIS\Projects\MyProject\MyProject.gdb
```

## Project Files

- **Project File**: MyProject.aprx
- **Toolbox**: MyProject.atbx
- **Geodatabase**: MyProject.gdb
