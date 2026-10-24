#!/bin/bash
# Run by launchd daily (~/Library/LaunchAgents/com.vagrant.jobscraper.plist).
cd /Users/vagrant/Arbeit
echo "=== $(date '+%Y-%m-%d %H:%M:%S')"
.venv/bin/python scraper.py
