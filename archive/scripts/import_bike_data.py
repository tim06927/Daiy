#!/usr/bin/env python3
"""
Convert Excel bike data to PostgreSQL table
"""

import pandas as pd
import psycopg2
from psycopg2 import sql
import sys
import os

# Database connection parameters
DB_CONFIG = {
    'dbname': 'bike_catalog',
    'user': 'daiy_user',
    'password': 'daiy_pass',
    'host': 'localhost',
    'port': '5432'
}

def clean_column_name(col):
    """Clean column names for PostgreSQL"""
    return col.lower().replace(' ', '_').replace('(', '').replace(')', '').replace('/', '_')

def convert_excel_to_postgres():
    """Read Excel file and import to PostgreSQL"""
    
    excel_path = '/workspaces/Daiy/data/sampleData/SampleBikeSpecs-2025-06-11.xlsx'
    
    if not os.path.exists(excel_path):
        print(f"Error: File not found: {excel_path}")
        sys.exit(1)
    
    print(f"Reading Excel file: {excel_path}")
    df = pd.read_excel(excel_path)
    
    print(f"Found {len(df)} rows and {len(df.columns)} columns")
    print(f"Columns: {list(df.columns)}")
    
    # Clean column names
    df.columns = [clean_column_name(col) for col in df.columns]
    
    print(f"Cleaned columns: {list(df.columns)}")
    
    # Connect to database
    print("Connecting to database...")
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Drop table if exists
        print("Dropping existing table if it exists...")
        cur.execute("DROP TABLE IF EXISTS bike_specs CASCADE;")
        
        # Create table schema dynamically based on DataFrame
        print("Creating table schema...")
        
        # Start with basic CREATE TABLE
        create_table = "CREATE TABLE bike_specs (id SERIAL PRIMARY KEY, "
        
        # Add columns based on DataFrame dtypes
        column_defs = []
        for col in df.columns:
            dtype = df[col].dtype
            if dtype == 'int64':
                col_type = 'INTEGER'
            elif dtype == 'float64':
                col_type = 'NUMERIC'
            elif dtype == 'bool':
                col_type = 'BOOLEAN'
            else:
                col_type = 'TEXT'
            
            column_defs.append(f"{col} {col_type}")
        
        create_table += ", ".join(column_defs) + ");"
        
        print(f"Creating table with schema: {create_table}")
        cur.execute(create_table)
        
        # Insert data
        print("Inserting data...")
        for idx, row in df.iterrows():
            # Prepare values, converting NaN to None
            values = [None if pd.isna(val) else val for val in row]
            
            placeholders = ', '.join(['%s'] * len(values))
            columns = ', '.join(df.columns)
            
            insert_query = f"INSERT INTO bike_specs ({columns}) VALUES ({placeholders})"
            cur.execute(insert_query, values)
            
            if (idx + 1) % 100 == 0:
                print(f"Inserted {idx + 1} rows...")
        
        conn.commit()
        print(f"Successfully imported {len(df)} rows into bike_specs table!")
        
        # Show sample data
        cur.execute("SELECT * FROM bike_specs LIMIT 5;")
        print("\nSample data:")
        for row in cur.fetchall():
            print(row)
        
        # Show table info
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'bike_specs'
            ORDER BY ordinal_position;
        """)
        print("\nTable schema:")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]}")
        
    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    convert_excel_to_postgres()
