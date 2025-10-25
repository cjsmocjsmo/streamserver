# Makefile for Motion Detection Stream Server

.PHONY: help setup install run test clean lint format

help:  ## Show this help message
	@echo "Motion Detection Stream Server - Available Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup:  ## Setup the project (install dependencies and create directories)
	python3 setup.py

install:  ## Install Python dependencies (prefer apt over pip)
	@echo "Installing system packages via apt..."
	@command -v apt >/dev/null 2>&1 && { \
		sudo apt update && \
		sudo apt install -y python3-opencv python3-numpy python3-picamera2; \
	} || echo "APT not available, skipping system packages"
	@echo "Installing remaining packages via pip..."
	pip3 install -r requirements.txt

install-pip-only:  ## Install all dependencies via pip only
	pip3 install -r requirements.txt

run:  ## Run the motion detection server
	python3 streamserver_v2.py

run-old:  ## Run the original server
	python3 streamserver.py

test:  ## Run tests (placeholder for future tests)
	@echo "Tests will be added in future versions"
	@echo "Syntax check:"
	python3 -m py_compile streamserver_v2.py
	python3 -m py_compile config.py
	python3 -m py_compile database.py
	python3 -m py_compile motion_detector.py
	python3 -m py_compile video_recorder.py

lint:  ## Check code style with flake8
	@command -v flake8 >/dev/null 2>&1 || { echo "Installing flake8..."; pip3 install flake8; }
	flake8 *.py --max-line-length=100 --ignore=E501,W503

format:  ## Format code with black
	@command -v black >/dev/null 2>&1 || { echo "Installing black..."; pip3 install black; }
	black *.py --line-length=100

clean:  ## Clean up generated files
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type f -name "*.log" -delete

clean-recordings:  ## Clean up old recordings (BE CAREFUL!)
	@echo "This will delete ALL recordings and database!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read
	rm -rf recordings/
	mkdir recordings/

backup:  ## Backup recordings and database
	@timestamp=$$(date +"%Y%m%d_%H%M%S"); \
	echo "Creating backup: backup_$$timestamp.tar.gz"; \
	tar -czf backup_$$timestamp.tar.gz recordings/ logs/ *.db 2>/dev/null || true

status:  ## Show system status
	@echo "=== System Status ==="
	@echo "Python version: $$(python3 --version)"
	@echo "OpenCV available: $$(python3 -c 'import cv2; print(cv2.__version__)' 2>/dev/null || echo 'Not installed')"
	@echo "NumPy available: $$(python3 -c 'import numpy; print(numpy.__version__)' 2>/dev/null || echo 'Not installed')"
	@echo "Picamera2 available: $$(python3 -c 'from picamera2 import Picamera2; print("Yes")' 2>/dev/null || echo 'Not available')"
	@echo ""
	@echo "=== Directory Status ==="
	@echo "Recordings: $$(ls -la recordings/ 2>/dev/null | wc -l) files"
	@echo "Logs: $$(ls -la logs/ 2>/dev/null | wc -l) files"
	@echo "Database size: $$(du -h recordings/events.db 2>/dev/null || echo 'No database')"

info:  ## Show project information
	@echo "=== Motion Detection Stream Server ==="
	@echo "Version: 2.0.0"
	@echo "Architecture: Modular Python application"
	@echo "Features:"
	@echo "  - Real-time MJPEG streaming"
	@echo "  - OpenCV motion detection"
	@echo "  - Automatic video recording"
	@echo "  - SQLite event database"
	@echo "  - Web monitoring interface"
	@echo ""
	@echo "Files:"
	@echo "  streamserver_v2.py    - Main application (improved)"
	@echo "  streamserver.py       - Original version"
	@echo "  config.py            - Configuration management"
	@echo "  database.py          - Event database"
	@echo "  motion_detector.py   - Motion detection"
	@echo "  video_recorder.py    - Video recording"
	@echo ""
	@echo "Usage: make run"
	@echo "Web UI: http://localhost:8000"