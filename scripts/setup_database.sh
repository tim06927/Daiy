#!/bin/bash
# Setup PostgreSQL database and import bike data

set -e

echo "Setting up PostgreSQL database..."

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "Error: PostgreSQL is not installed. Please rebuild the dev container."
    exit 1
fi

# Initialize PostgreSQL cluster if needed
if [ ! -d /var/lib/postgresql/16/main ]; then
    echo "Initializing PostgreSQL cluster..."
    sudo -u postgres /usr/lib/postgresql/16/bin/initdb -D /var/lib/postgresql/16/main
fi

# Start PostgreSQL if not running
echo "Starting PostgreSQL..."
sudo -u postgres /usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/postgresql/16/main -l /var/log/postgresql/postgresql.log start || true

# Wait for PostgreSQL to be ready
sleep 3

# Create database
echo "Creating database..."
sudo -u postgres psql -c "CREATE DATABASE bike_catalog;" || echo "Database may already exist"

# Create user
echo "Creating user..."
sudo -u postgres psql -c "CREATE USER daiy_user WITH PASSWORD 'daiy_pass';" || echo "User may already exist"

# Grant privileges
echo "Granting privileges..."
sudo -u postgres psql -d bike_catalog -c "GRANT ALL PRIVILEGES ON DATABASE bike_catalog TO daiy_user;"
sudo -u postgres psql -d bike_catalog -c "GRANT ALL ON SCHEMA public TO daiy_user;"

echo ""
echo "✓ Database setup complete!"
echo "  Database: bike_catalog"
echo "  User: daiy_user"
echo "  Password: daiy_pass"
echo "  Host: localhost"
echo "  Port: 5432"
