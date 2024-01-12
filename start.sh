#!/bin/bash
exec ./nhsupsserver &
exec python3 -u nhs-nobreak-monitor.py