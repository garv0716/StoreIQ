#!/bin/bash
# Run the full detection pipeline against all CAM files
# Output: data/events.jsonl
echo "Starting Store Intelligence detection pipeline..."
echo "Processing 5 camera feeds..."
python pipeline/detect.py
echo "Done. Events saved to data/events.jsonl"
echo "Now ingest into API with: python pipeline/ingest_events.py"
