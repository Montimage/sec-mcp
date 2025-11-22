#!/bin/bash
# Helper script to run benchmark with virtual environment

# Check if virtual environment exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
    echo "Using virtual environment: .venv"
elif [ -d "venv" ]; then
    source venv/bin/activate
    echo "Using virtual environment: venv"
else
    echo "Warning: No virtual environment found. Using system Python."
fi

# Run the benchmark with all arguments passed to this script
python benchmark.py "$@"
