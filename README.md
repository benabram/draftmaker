# eBay Draft Maker

An automated system for creating eBay draft listings from UPC codes stored in Google Cloud Storage.

## Overview

The Draft Maker processes batches of UPC codes from text files in Google Cloud Storage buckets, fetches metadata and pricing information, retrieves album artwork, and creates draft eBay listings using the eBay Sell API.

## Architecture

The system consists of the following components:

1. **UPC Processor**: Reads and validates UPC codes from GCS text files
2. **Metadata Fetcher**: Retrieves album information from MusicBrainz and Discogs  
3. **Pricing Fetcher**: Gets pricing data from eBay's completed listings
4. **Image Fetcher**: Fetches album artwork from Cover Art Archive and Spotify
5. **Draft Composer**: Creates eBay draft listings using the Sell API
6. **Orchestrator**: Coordinates all components to process UPC batches

## Usage

### Processing UPCs from Google Cloud Storage

```bash
# Process UPCs from a GCS bucket
python main.py gs://your-bucket/upcs.txt

# Test mode (fetch data but don't create drafts)
python main.py gs://your-bucket/upcs.txt --test
```

### Processing UPCs from Local File (for testing)

```bash
# Process local file
python main.py data/sample_upcs.txt --local

# Test mode with local file
python main.py data/sample_upcs.txt --local --test
```

### Testing Single UPC

```bash
# Test a single UPC without creating a draft
python main.py gs://dummy/path --single 602527291079
```

## Input Format

The input text file should contain one UPC per line:

```
602527291079
093624946724
602498633090
828765612920
093624923244
```

- UPCs must be 12 or 13 digits
- Empty lines are ignored
- Invalid UPCs are logged and skipped

## Output

The system generates two output files in the `output/` directory:

1. **batch_results_YYYYMMDD_HHMMSS.json**: Complete processing results with all metadata
2. **batch_summary_YYYYMMDD_HHMMSS.csv**: Summary CSV with key information
