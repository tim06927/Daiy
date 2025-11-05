#!/bin/bash
# Setup PostgreSQL database and import bike data

set -e

echo "Setting up PostgreSQL database..."

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ Error: PostgreSQL is not installed. Please rebuild the dev container."
    exit 1
fi

# Initialize PostgreSQL cluster if needed (Ubuntu-style)
if [ ! -d /var/lib/postgresql/16/main ]; then
    echo "Initializing PostgreSQL cluster..."
    sudo -u postgres /usr/lib/postgresql/16/bin/initdb -D /var/lib/postgresql/16/main
fi

# Start PostgreSQL if not running
echo "Starting PostgreSQL..."
if ! pgrep -x postgres > /dev/null; then
    sudo -u postgres /usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/postgresql/16/main -l /tmp/postgresql.log start
    echo "PostgreSQL started"
else
    echo "PostgreSQL is already running"
fi

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if sudo -u postgres psql -c "SELECT 1" &> /dev/null; then
        echo "✓ PostgreSQL is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Error: PostgreSQL failed to start. Check logs at /tmp/postgresql.log"
        exit 1
    fi
    sleep 1
done

# Create database
echo "Creating database..."
sudo -u postgres psql -c "CREATE DATABASE bike_catalog;" 2>/dev/null && echo "✓ Database created" || echo "ℹ Database already exists"

# Create user
echo "Creating user..."
sudo -u postgres psql -c "CREATE USER daiy_user WITH PASSWORD 'daiy_pass';" 2>/dev/null && echo "✓ User created" || echo "ℹ User already exists"

# Grant privileges
echo "Granting privileges..."
sudo -u postgres psql -d bike_catalog -c "GRANT ALL PRIVILEGES ON DATABASE bike_catalog TO daiy_user;"
sudo -u postgres psql -d bike_catalog -c "GRANT ALL ON SCHEMA public TO daiy_user;"
sudo -u postgres psql -d bike_catalog -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO daiy_user;"

echo ""
echo "✓ Database setup complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Database: bike_catalog"
echo "  User:     daiy_user"
echo "  Password: daiy_pass"
echo "  Host:     localhost"
echo "  Port:     5432"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Connection string:"
echo "  postgresql://daiy_user:daiy_pass@localhost:5432/bike_catalog"
