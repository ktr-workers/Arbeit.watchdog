#!/bin/bash
# Manual local run (the daily run is on GitHub Actions).
cd /Users/vagrant/Arbeit
echo "=== $(date '+%Y-%m-%d %H:%M:%S')"
.venv/bin/python -m watchdog.scraper
