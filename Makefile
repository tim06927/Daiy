# Daiy Makefile
# Run `make help` to see available targets

.PHONY: help install run scrape scrape-full export refresh-data discover-categories discover-fields clean
.PHONY: pipeline pipeline-full pipeline-drivetrain pipeline-drivetrain-full pipeline-accessories pipeline-accessories-full

# Default target
help:
	@echo "Daiy - Bike Component Recommender"
	@echo ""
	@echo "Usage: make <target>"
	@echo ""
	@echo "Setup:"
	@echo "  install          Install Python dependencies"
	@echo "  setup            Create .env from example (if not exists)"
	@echo ""
	@echo "Web App:"
	@echo "  run              Start the Flask web app"
	@echo ""
	@echo "Scraping:"
	@echo "  scrape           Run incremental scrape (configured categories)"
	@echo "  scrape-full      Run full scrape (ignore existing data)"
	@echo "  scrape-drivetrain  Scrape all drivetrain subcategories"
	@echo "  scrape-accessories Scrape all accessories subcategories"
	@echo ""
	@echo "Full Pipelines (discover + scrape + export):"
	@echo "  pipeline SUPER=<path>           Incremental pipeline for a super-category"
	@echo "  pipeline-full SUPER=<path>      Full pipeline for a super-category"
	@echo "  pipeline-drivetrain             Incremental: components/drivetrain"
	@echo "  pipeline-drivetrain-full        Full: components/drivetrain"
	@echo "  pipeline-accessories            Incremental: accessories"
	@echo "  pipeline-accessories-full       Full: accessories"
	@echo ""
	@echo "Data Management:"
	@echo "  export           Export database to CSV"
	@echo "  refresh-data     Scrape + export + show git diff"
	@echo ""
	@echo "Discovery:"
	@echo "  discover-categories  Discover categories from sitemap"
	@echo "  discover-fields CAT=<category>  Discover fields for a category"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean            Remove generated files and caches"
	@echo ""
	@echo "Examples:"
	@echo "  make refresh-data"
	@echo "  make discover-fields CAT=cassettes"
	@echo "  make scrape-drivetrain MAX_PAGES=3"
	@echo ""
	@echo "Background/Overnight Pipelines:"
	@echo "  make pipeline-drivetrain-full MAX_PAGES=50 &"
	@echo "  nohup make pipeline SUPER=components/drivetrain MAX_PAGES=100 > logs/pipeline.log 2>&1 &"
	@echo "  make pipeline-accessories-full MAX_PAGES=20 2>&1 | tee logs/accessories.log"

# =============================================================================
# Setup
# =============================================================================

install:
	pip install -r requirements.txt

setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example - please edit with your API keys"; \
	else \
		echo ".env already exists"; \
	fi

# =============================================================================
# Web App
# =============================================================================

run:
	python web/app.py

# =============================================================================
# Scraping
# =============================================================================

# Default max pages per category
MAX_PAGES ?= 5

scrape:
	python -m scrape.cli --max-pages $(MAX_PAGES)

scrape-full:
	python -m scrape.cli --mode full --max-pages $(MAX_PAGES)

scrape-drivetrain:
	python -m scrape.cli --discover-scrape components/drivetrain --max-pages $(MAX_PAGES) --skip-field-discovery

scrape-accessories:
	python -m scrape.cli --discover-scrape accessories --max-pages $(MAX_PAGES) --skip-field-discovery

# =============================================================================
# Full Pipelines (discover + scrape + export) - ideal for overnight runs
# =============================================================================

# Super-category path (e.g., components/drivetrain, accessories)
SUPER ?= components/drivetrain

# Timestamp for logs
TIMESTAMP := $(shell date +%Y%m%d_%H%M%S)

# Generic incremental pipeline
pipeline:
	@echo "=== Starting Incremental Pipeline for $(SUPER) ==="
	@echo "Started at: $$(date)"
	@echo ""
	@echo "Step 1/3: Discovering categories..."
	python -m scrape.discover_categories --output data/discovered_categories.json
	@echo ""
	@echo "Step 2/3: Scraping (incremental mode)..."
	python -m scrape.cli --discover-scrape $(SUPER) --max-pages $(MAX_PAGES) --skip-field-discovery
	@echo ""
	@echo "Step 3/3: Exporting to CSV..."
	python -c "from scrape.csv_utils import export_db_to_csv; export_db_to_csv('$(DB_PATH)', '$(CSV_PATH)')"
	@echo ""
	@echo "=== Pipeline Complete ==="
	@echo "Finished at: $$(date)"
	@echo "Database: $(DB_PATH)"
	@echo "CSV: $(CSV_PATH)"

# Generic full pipeline (re-scrape everything)
pipeline-full:
	@echo "=== Starting Full Pipeline for $(SUPER) ==="
	@echo "Started at: $$(date)"
	@echo ""
	@echo "Step 1/3: Discovering categories..."
	python -m scrape.discover_categories --output data/discovered_categories.json
	@echo ""
	@echo "Step 2/3: Scraping (full mode - ignoring existing data)..."
	python -m scrape.cli --discover-scrape $(SUPER) --max-pages $(MAX_PAGES) --skip-field-discovery --mode full
	@echo ""
	@echo "Step 3/3: Exporting to CSV..."
	python -c "from scrape.csv_utils import export_db_to_csv; export_db_to_csv('$(DB_PATH)', '$(CSV_PATH)')"
	@echo ""
	@echo "=== Pipeline Complete ==="
	@echo "Finished at: $$(date)"
	@echo "Database: $(DB_PATH)"
	@echo "CSV: $(CSV_PATH)"

# Convenience shortcuts for common super-categories
pipeline-drivetrain:
	$(MAKE) pipeline SUPER=components/drivetrain MAX_PAGES=$(MAX_PAGES)

pipeline-drivetrain-full:
	$(MAKE) pipeline-full SUPER=components/drivetrain MAX_PAGES=$(MAX_PAGES)

pipeline-accessories:
	$(MAKE) pipeline SUPER=accessories MAX_PAGES=$(MAX_PAGES)

pipeline-accessories-full:
	$(MAKE) pipeline-full SUPER=accessories MAX_PAGES=$(MAX_PAGES)

# =============================================================================
# Data Management
# =============================================================================

# CSV output path
CSV_PATH ?= data/bc_products_sample.csv
DB_PATH ?= data/products.db

export:
	python -c "from scrape.csv_utils import export_db_to_csv; export_db_to_csv('$(DB_PATH)', '$(CSV_PATH)')"

refresh-data: scrape export
	@echo ""
	@echo "=== Data Refresh Complete ==="
	@echo "Database: $(DB_PATH)"
	@echo "CSV: $(CSV_PATH)"
	@echo ""
	@echo "Git status:"
	@git diff --stat $(CSV_PATH) 2>/dev/null || echo "  (file not tracked or no changes)"
	@echo ""
	@echo "To commit: git add $(CSV_PATH) && git commit -m 'Update product data' && git push"

# =============================================================================
# Discovery
# =============================================================================

# Category for field discovery
CAT ?= chains
SAMPLE_SIZE ?= 15

discover-categories:
	python -m scrape.discover_categories --output data/discovered_categories.json

discover-fields:
	python -m scrape.discover_fields $(CAT) --sample-size $(SAMPLE_SIZE)

# =============================================================================
# Maintenance
# =============================================================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -f data/discovered_categories.json 2>/dev/null || true
	@echo "Cleaned up cache files"

clean-db:
	rm -f $(DB_PATH)
	@echo "Removed database: $(DB_PATH)"
