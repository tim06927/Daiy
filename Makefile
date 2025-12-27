# Daiy Makefile
# Run `make help` to see available targets

.PHONY: help install run scrape scrape-full export refresh-data discover-categories discover-fields clean
.PHONY: pipeline pipeline-full pipeline-overnight

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
	@echo ""
	@echo "Full Pipelines (discover + scrape + export):"
	@echo "  pipeline SUPER=<path>           Incremental pipeline for a super-category"
	@echo "  pipeline-full SUPER=<path>      Full pipeline for a super-category"
	@echo "  pipeline-overnight SUPER=<path> Overnight mode with longer delays (10-30s)"
	@echo ""
	@echo "Options (can be combined with any pipeline):"
	@echo "  MAX_PAGES=N                     Max pages per category (default: 5)"
	@echo "  OVERNIGHT=1                     Enable overnight mode (longer delays)"
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
	@echo "  make pipeline SUPER=components/drivetrain MAX_PAGES=5"
	@echo "  make pipeline SUPER=accessories MAX_PAGES=10 OVERNIGHT=1"
	@echo ""
	@echo "Background/Overnight Pipelines (recommended for large scrapes):"
	@echo "  mkdir -p logs"
	@echo "  nohup make pipeline-overnight SUPER=components MAX_PAGES=100 > logs/pipeline.log 2>&1 &"
	@echo "  make pipeline-full SUPER=accessories MAX_PAGES=50 OVERNIGHT=1 2>&1 | tee logs/overnight.log"

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

# =============================================================================
# Full Pipelines (discover + scrape + export) - ideal for overnight runs
# =============================================================================

# Super-category path (e.g., components/drivetrain, accessories, apparel)
# No default - must be specified explicitly
SUPER ?=

# Overnight mode flag (set OVERNIGHT=1 to enable longer delays)
OVERNIGHT ?=
OVERNIGHT_FLAG := $(if $(OVERNIGHT),--overnight,)

# Timestamp for logs
TIMESTAMP := $(shell date +%Y%m%d_%H%M%S)

# Generic incremental pipeline
pipeline:
	@if [ -z "$(SUPER)" ]; then \
		echo "Error: SUPER parameter required"; \
		echo "Usage: make pipeline SUPER=<category-path>"; \
		echo "Examples:"; \
		echo "  make pipeline SUPER=components/drivetrain"; \
		echo "  make pipeline SUPER=accessories"; \
		echo "  make pipeline SUPER=apparel"; \
		exit 1; \
	fi
	@echo "=== Starting Incremental Pipeline for $(SUPER) ==="
	@if [ -n "$(OVERNIGHT)" ]; then echo "Mode: OVERNIGHT (10-30s delays between requests)"; fi
	@echo "Started at: $$(date)"
	@echo ""
	@echo "Step 1/3: Discovering categories..."
	python -m scrape.discover_categories --output data/discovered_categories.json
	@echo ""
	@echo "Step 2/3: Scraping (incremental mode)..."
	python -m scrape.cli --discover-scrape $(SUPER) --max-pages $(MAX_PAGES) --skip-field-discovery $(OVERNIGHT_FLAG)
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
	@if [ -z "$(SUPER)" ]; then \
		echo "Error: SUPER parameter required"; \
		echo "Usage: make pipeline-full SUPER=<category-path>"; \
		echo "Examples:"; \
		echo "  make pipeline-full SUPER=components/drivetrain"; \
		echo "  make pipeline-full SUPER=accessories"; \
		echo "  make pipeline-full SUPER=apparel"; \
		exit 1; \
	fi
	@echo "=== Starting Full Pipeline for $(SUPER) ==="
	@if [ -n "$(OVERNIGHT)" ]; then echo "Mode: OVERNIGHT (10-30s delays between requests)"; fi
	@echo "Started at: $$(date)"
	@echo ""
	@echo "Step 1/3: Discovering categories..."
	python -m scrape.discover_categories --output data/discovered_categories.json
	@echo ""
	@echo "Step 2/3: Scraping (full mode - ignoring existing data)..."
	python -m scrape.cli --discover-scrape $(SUPER) --max-pages $(MAX_PAGES) --skip-field-discovery --mode full $(OVERNIGHT_FLAG)
	@echo ""
	@echo "Step 3/3: Exporting to CSV..."
	python -c "from scrape.csv_utils import export_db_to_csv; export_db_to_csv('$(DB_PATH)', '$(CSV_PATH)')"
	@echo ""
	@echo "=== Pipeline Complete ==="
	@echo "Finished at: $$(date)"
	@echo "Database: $(DB_PATH)"
	@echo "CSV: $(CSV_PATH)"

# Overnight pipeline - convenience shortcut for pipeline with overnight mode
pipeline-overnight:
	$(MAKE) pipeline SUPER=$(SUPER) MAX_PAGES=$(MAX_PAGES) OVERNIGHT=1

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
