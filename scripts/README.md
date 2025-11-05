# Database Setup Instructions

This directory contains scripts to set up PostgreSQL and import the bike catalog data.

## Prerequisites

1. Rebuild the dev container to ensure PostgreSQL is installed:
   - Press `F1` or `Ctrl+Shift+P`
   - Type "Dev Containers: Rebuild Container"
   - Select the option and wait for rebuild

2. Install Python dependencies:
   ```bash
   pip3 install -r requirements.txt
   ```

## Setup Steps

### 1. Initialize PostgreSQL Database

Run the setup script to create the database and user:

```bash
./scripts/setup_database.sh
```

This will:
- Start PostgreSQL service
- Create `bike_catalog` database
- Create `daiy_user` with password `daiy_pass`
- Grant necessary privileges

### 2. Import Bike Data

Run the Python script to import the Excel data:

```bash
python3 scripts/import_bike_data.py
```

This will:
- Read the Excel file from `data/sampleData/SampleBikeSpecs-2025-06-11.xlsx`
- Create a `bike_specs` table
- Import all bike specifications

## Database Connection Info

- **Database**: bike_catalog
- **User**: daiy_user
- **Password**: daiy_pass
- **Host**: localhost
- **Port**: 5432

## Connecting to the Database

### Using psql

```bash
psql -h localhost -U daiy_user -d bike_catalog
```

### Using Python

```python
import psycopg2

conn = psycopg2.connect(
    dbname='bike_catalog',
    user='daiy_user',
    password='daiy_pass',
    host='localhost',
    port='5432'
)
```

## Troubleshooting

### PostgreSQL not found

If you get "PostgreSQL is not installed", rebuild the dev container:
1. Make sure `.devcontainer/Dockerfile` includes PostgreSQL
2. Rebuild container: `F1` → "Dev Containers: Rebuild Container"

### Permission errors

If you get permission errors, ensure PostgreSQL is running:
```bash
sudo -u postgres /usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/postgresql/16/main status
```

### Import fails

Make sure the Excel file exists:
```bash
ls -la data/sampleData/SampleBikeSpecs-2025-06-11.xlsx
```

## Viewing the Data

After import, you can query the data:

```bash
psql -h localhost -U daiy_user -d bike_catalog -c "SELECT * FROM bike_specs LIMIT 10;"
```

Or get table info:

```bash
psql -h localhost -U daiy_user -d bike_catalog -c "\d bike_specs"
```
