# Daiy Makefile
# Run `make help` to see available targets

.PHONY: help install run scrape scrape-full refresh-data discover-categories discover-fields view-data clean
.PHONY: pipeline pipeline-full pipeline-overnight
.PHONY: errors errors-all errors-type errors-request errors-export
.PHONY: render-errors render-errors-all render-errors-type render-errors-export

# Python command (uses venv if available)
PYTHON := $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else echo python3; fi)
# Render CLI binary (override with RENDER_CLI=raster3d if you prefer)
RENDER_CLI ?= render

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
	@echo "  run              Start the web app with gunicorn (production)"
	@echo "  run-dev          Start with Flask dev server (auto-reload)"
	@echo ""
	@echo "Scraping:"
	@echo "  scrape           Run incremental scrape (configured categories)"
	@echo "  scrape-full      Run full scrape (ignore existing data)"
	@echo ""
	@echo "Full Pipelines (discover + scrape):"
	@echo "  pipeline SUPER=<path>           Incremental pipeline for a super-category"
	@echo "  pipeline-full SUPER=<path>      Full pipeline for a super-category"
	@echo "  pipeline-overnight SUPER=<path> Overnight mode with longer delays (10-30s)"
	@echo ""
	@echo "Options (can be combined with any pipeline):"
	@echo "  MAX_PAGES=N                     Max pages per category (default: 5)"
	@echo "  OVERNIGHT=1                     Enable overnight mode (longer delays)"
	@echo ""
	@echo "Data Management:"
	@echo "  refresh-data     Run incremental scrape to database"
	@echo ""
	@echo "Discovery & Visualization:"
	@echo "  discover-categories  Discover categories from sitemap"
	@echo "  discover-fields CAT=<category>  Discover fields for a category"
	@echo "  view-data            Open scrape data viewer in browser"
	@echo ""
	@echo "Error Tracking & Monitoring:"
	@echo "  errors              View error summary (Render deployment)"
	@echo "  errors-all          List all errors with pagination"
	@echo "  errors-type TYPE=<type>  Filter by error type (llm_error, validation_error, etc.)"
	@echo "  errors-request ID=<request-id>  Trace errors for specific request"
	@echo "  errors-export FORMAT=json|jsonl  Export errors to file"
	@echo ""
	@echo "Interaction Logs (user input, LLM calls, recommendations):"
	@echo "  interactions            View all interactions from database"
	@echo "  interactions-request ID=<request-id>  View all events for a specific request"
	@echo "  interactions-type TYPE=<type>  Filter by event type (user_input, llm_call_phase_1, etc.)"
	@echo ""
	@echo "Render Error Logs (requires 'render' CLI):"
	@echo "  render-errors          View error summary from Render deployment"
	@echo "  render-errors-all      List all errors from Render"
	@echo "  render-errors-type TYPE=<type>  Filter by error type on Render"
	@echo "  render-errors-export OUTPUT=<file>  Export errors from Render to file"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean            Remove generated files and caches"
	@echo ""
	@echo "Examples:"
	@echo "  make refresh-data"
	@echo "  make discover-fields CAT=cassettes"
	@echo "  make pipeline SUPER=components/drivetrain MAX_PAGES=5"
	@echo "  make errors"
	@echo "  make errors-type TYPE=llm_error"
	@echo "  make errors-export FORMAT=json"
	@echo "  make interactions-request ID=abc123"
	@echo "  make render-errors"
	@echo "  make render-errors-export OUTPUT=render_errors.json"
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
	$(PYTHON) -m gunicorn --workers 1 --timeout 60 --bind 0.0.0.0:5000 web.app:app

run-dev:
	$(PYTHON) -m web.app

# =============================================================================
# Scraping
# =============================================================================

# Default max pages per category
MAX_PAGES ?= 5

scrape:
	$(PYTHON) -m scrape.cli --max-pages $(MAX_PAGES)

scrape-full:
	$(PYTHON) -m scrape.cli --mode full --max-pages $(MAX_PAGES)

# =============================================================================
# Full Pipelines (discover + scrape + export) - ideal for overnight runs
# =============================================================================

# Super-category path (e.g., components/drivetrain, accessories, apparel)
# No default - must be specified explicitly
SUPER ?=

# Overnight mode flag (set OVERNIGHT=1 to enable longer delays)
OVERNIGHT ?=
OVERNIGHT_FLAG := $(if $(OVERNIGHT),--overnight,)

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
	$(PYTHON) -m scrape.discover_categories --output data/discovered_categories.json
	@echo ""
	@echo "Step 2/3: Scraping (incremental mode)..."
	$(PYTHON) -m scrape.cli --discover-scrape $(SUPER) --max-pages $(MAX_PAGES) --skip-field-discovery $(OVERNIGHT_FLAG)
	@echo ""
	@echo "=== Pipeline Complete ==="
	@echo "Finished at: $$(date)"
	@echo "Database: $(DB_PATH)"

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
	$(PYTHON) -m scrape.discover_categories --output data/discovered_categories.json
	@echo ""
	@echo "Step 2/3: Scraping (full mode - ignoring existing data)..."
	$(PYTHON) -m scrape.cli --discover-scrape $(SUPER) --max-pages $(MAX_PAGES) --skip-field-discovery --mode full $(OVERNIGHT_FLAG)
	@echo ""
	@echo "=== Pipeline Complete ==="
	@echo "Finished at: $$(date)"
	@echo "Database: $(DB_PATH)"

# Overnight pipeline - convenience shortcut for pipeline with overnight mode
pipeline-overnight:
	$(MAKE) pipeline SUPER=$(SUPER) MAX_PAGES=$(MAX_PAGES) OVERNIGHT=1

# =============================================================================
# Data Management
# =============================================================================

# Database path
DB_PATH ?= data/products.db

refresh-data: scrape
	@echo ""
	@echo "=== Data Refresh Complete ==="
	@echo "Database: $(DB_PATH)"
	@echo ""
	@echo "View database stats:"
	@echo "  $(PYTHON) -m scrape.cli --stats"

# =============================================================================
# Discovery
# =============================================================================

# Category for field discovery
CAT ?= chains
SAMPLE_SIZE ?= 15

discover-categories:
	$(PYTHON) -m scrape.discover_categories --output data/discovered_categories.json --update-view

discover-fields:
	$(PYTHON) -m scrape.discover_fields $(CAT) --sample-size $(SAMPLE_SIZE)

view-data:
	$(PYTHON) -m scrape.view_data --open

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

# =============================================================================
# Error Tracking & Monitoring (for Render deployment)
# =============================================================================

errors:
	$(PYTHON) web/view_errors.py

errors-all:
	$(PYTHON) web/view_errors.py --all

errors-type:
	@if [ -z "$(TYPE)" ]; then \
		echo "Usage: make errors-type TYPE=<type>"; \
		echo "Error types: llm_error, validation_error, database_error, processing_error, unexpected_error"; \
	else \
		$(PYTHON) web/view_errors.py --type $(TYPE); \
	fi

errors-request:
	@if [ -z "$(ID)" ]; then \
		echo "Usage: make errors-request ID=<request-id>"; \
	else \
		$(PYTHON) web/view_errors.py --request $(ID); \
	fi

errors-export:
	@if [ -z "$(FORMAT)" ]; then \
		echo "Usage: make errors-export FORMAT=json|jsonl"; \
	else \
		$(PYTHON) web/view_errors.py --export $(FORMAT) --output errors_export.$(FORMAT); \
		echo "✓ Exported to errors_export.$(FORMAT)"; \
	fi

# =============================================================================
# Render Error Logs (requires render CLI)
# =============================================================================

render-errors:
	@echo "Connecting to Render..."
	RENDER_CLI=$(RENDER_CLI) $(PYTHON) scripts/get_render_errors.py

render-errors-all:
	@if [ -z "$(SERVICE)" ]; then \
		RENDER_CLI=$(RENDER_CLI) $(PYTHON) scripts/get_render_errors.py daiy-web-prod; \
	else \
		RENDER_CLI=$(RENDER_CLI) $(PYTHON) scripts/get_render_errors.py $(SERVICE); \
	fi

render-errors-type:
	@if [ -z "$(TYPE)" ]; then \
		echo "Usage: make render-errors-type TYPE=<type>"; \
		echo "Error types: llm_error, validation_error, database_error, processing_error, unexpected_error"; \
	else \
		$(RENDER_CLI) exec --service=daiy-web-prod "cd /app && python web/view_errors.py --type $(TYPE)"; \
	fi

render-errors-export:
	@if [ -z "$(OUTPUT)" ]; then \
		RENDER_CLI=$(RENDER_CLI) $(PYTHON) scripts/get_render_errors.py daiy-web-prod render_errors_export.json; \
		echo "✓ Exported to render_errors_export.json"; \
	else \
		RENDER_CLI=$(RENDER_CLI) $(PYTHON) scripts/get_render_errors.py daiy-web-prod $(OUTPUT); \
		echo "✓ Exported to $(OUTPUT)"; \
	fi

# =============================================================================
# Interaction Logs (user input, LLM calls, recommendations)
# =============================================================================

interactions:
	$(PYTHON) web/view_logs.py --db sqlite

interactions-request:
	@if [ -z "$(ID)" ]; then \
		echo "Usage: make interactions-request ID=<request-id>"; \
	else \
		$(PYTHON) web/view_logs.py --db sqlite --request $(ID); \
	fi

interactions-type:
	@if [ -z "$(TYPE)" ]; then \
		echo "Usage: make interactions-type TYPE=<type>"; \
		echo "Event types: user_input, clarification_required, llm_call_phase_1, llm_response_phase_1, llm_call_phase_3, llm_response_phase_3, recommendation_result, performance_metrics"; \
	else \
		$(PYTHON) web/view_logs.py --db sqlite --type $(TYPE); \
	fi
