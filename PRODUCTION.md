# eBay Draft Maker - Production Deployment Guide

## Overview

This guide covers deployment and operation of the eBay Draft Maker application for single-user production use. The application processes UPC codes to create draft eBay listings with metadata, images, and pricing.

## Prerequisites

### Required API Keys

1. **Spotify API**
   - Client ID and Client Secret
   - Get from: https://developer.spotify.com/dashboard

2. **eBay API**
   - App ID (Client ID)
   - Cert ID (Client Secret)
   - Dev ID
   - User Refresh Token
   - Get from: https://developer.ebay.com/

3. **Optional: Google Cloud Storage**
   - Service account credentials (if using GCS for UPC files)

### System Requirements

- Python 3.11+
- 2GB RAM minimum
- 10GB disk space
- Docker (optional, for containerized deployment)

## Installation Options

### Option 1: Local Docker Container (Recommended)

Best for: Users who want isolation and easy management

```bash
# Clone the repository
git clone <repository-url>
cd draftmaker

# Configure API keys in config.ini
cp config.ini.example config.ini
nano config.ini

# Deploy as Docker container
chmod +x deploy.sh
./deploy.sh docker
```

**Managing the container:**
```bash
# View logs
docker logs -f ebay-draftmaker

# Stop container
docker stop ebay-draftmaker

# Start container
docker start ebay-draftmaker

# Remove container
docker rm ebay-draftmaker
```

### Option 2: Systemd Service (Linux)

Best for: Linux users who want automatic startup

```bash
# Install as systemd service
./deploy.sh systemd

# Check status
sudo systemctl status ebay-draftmaker

# View logs
journalctl -u ebay-draftmaker -f

# Stop service
sudo systemctl stop ebay-draftmaker

# Disable autostart
sudo systemctl disable ebay-draftmaker
```

### Option 3: Cron Job

Best for: Scheduled batch processing

```bash
# Install as cron job (runs daily at 2 AM)
./deploy.sh cron

# View crontab
crontab -l

# Edit schedule
crontab -e

# View logs
tail -f ~/.local/ebay-draftmaker/logs/cron.log
```

### Option 4: Manual Python Installation

Best for: Development and testing

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run manually
python main.py --upc-file data/upcs.txt
```

## Configuration

### config.ini Structure

```ini
[APIs]
musicbrainz_user_agent = YourApp/1.0 (your@email.com)
spotify_client_id = your_spotify_client_id
spotify_client_secret = your_spotify_client_secret
ebay_app_id = your_ebay_app_id
ebay_cert_id = your_ebay_cert_id
ebay_dev_id = your_ebay_dev_id
ebay_refresh_token = your_ebay_refresh_token
ebay_environment = production  # or sandbox for testing
ebay_site_id = 0  # 0 for US, 3 for UK, etc.

[Processing]
batch_size = 10
max_workers = 4
retry_attempts = 3
retry_delay = 1.0

[Pricing]
default_min_price = 5.00
default_max_price = 100.00
price_multiplier = 1.2
outlier_std_dev = 2

[Logging]
level = INFO
format = %(asctime)s - %(name)s - %(levelname)s - %(message)s
```

### Environment Variables

You can override config values with environment variables:

```bash
export SPOTIFY_CLIENT_ID=your_client_id
export SPOTIFY_CLIENT_SECRET=your_client_secret
export EBAY_APP_ID=your_app_id
export EBAY_CERT_ID=your_cert_id
export EBAY_DEV_ID=your_dev_id
export EBAY_REFRESH_TOKEN=your_refresh_token
```

## Usage

### Command Line Interface

```bash
# Process local UPC file
python main.py --upc-file data/upcs.txt

# Process from Google Cloud Storage
python main.py --gcs-path gs://your-bucket/upcs.txt

# Process with custom batch size
python main.py --upc-file data/upcs.txt --batch-size 20

# Dry run (don't create drafts)
python main.py --upc-file data/upcs.txt --dry-run

# Verbose output
python main.py --upc-file data/upcs.txt --verbose
```

### Input File Format

Create a text file with one UPC per line:

```
602537351169
828768352625
093624974680
```

### Output Files

The application generates:

1. **Draft Results** - `output/drafts_YYYYMMDD_HHMMSS.json`
   - Contains all draft listing IDs and metadata

2. **Error Log** - `logs/errors_YYYYMMDD_HHMMSS.log`
   - Details of any failed UPCs

3. **Processing Report** - `output/report_YYYYMMDD_HHMMSS.txt`
   - Summary of processing results

## Monitoring

### Log Files

- **Application logs**: `logs/app.log`
- **Error logs**: `logs/error.log`
- **API logs**: `logs/api.log`

### Health Checks

For Docker deployments:
```bash
# Check if container is running
docker ps | grep ebay-draftmaker

# Check container health
docker inspect ebay-draftmaker --format='{{.State.Health.Status}}'
```

For systemd:
```bash
# Check service status
systemctl is-active ebay-draftmaker
```

## Troubleshooting

### Common Issues

1. **API Rate Limiting**
   - Symptom: 429 errors in logs
   - Solution: Reduce batch_size in config.ini

2. **Token Expiration**
   - Symptom: 401 Unauthorized errors
   - Solution: Refresh eBay token, update config.ini

3. **Memory Issues**
   - Symptom: Process killed or OOM errors
   - Solution: Reduce max_workers or batch_size

4. **Network Timeouts**
   - Symptom: Connection timeout errors
   - Solution: Increase retry_delay in config.ini

### Debug Mode

Enable debug logging:
```bash
# In config.ini
[Logging]
level = DEBUG

# Or via environment
export LOG_LEVEL=DEBUG
```

## Backup and Recovery

### Backup Important Files

```bash
# Create backup directory
mkdir -p ~/draftmaker-backup

# Backup configuration and tokens
cp config.ini ~/draftmaker-backup/
cp -r .tokens ~/draftmaker-backup/

# Backup output and logs
tar -czf ~/draftmaker-backup/output_$(date +%Y%m%d).tar.gz output/
tar -czf ~/draftmaker-backup/logs_$(date +%Y%m%d).tar.gz logs/
```

### Restore from Backup

```bash
# Restore configuration
cp ~/draftmaker-backup/config.ini .
cp -r ~/draftmaker-backup/.tokens .

# Restore data if needed
tar -xzf ~/draftmaker-backup/output_YYYYMMDD.tar.gz
```

## Security Best Practices

1. **Never commit secrets to version control**
   - Use .gitignore for config.ini and .tokens/

2. **Use environment variables for sensitive data**
   - Store secrets in a .env file (not in repo)

3. **Restrict file permissions**
   ```bash
   chmod 600 config.ini
   chmod 700 .tokens/
   ```

4. **Rotate API tokens regularly**
   - eBay tokens expire after 18 months
   - Spotify tokens auto-refresh

5. **Use HTTPS for all API calls**
   - Already enforced in the application

## Performance Tuning

### For Large Batches

```ini
[Processing]
batch_size = 20  # Increase for faster processing
max_workers = 8   # Increase for parallel processing
retry_attempts = 2  # Reduce for faster failure
```

### For Rate-Limited APIs

```ini
[Processing]
batch_size = 5    # Reduce to avoid rate limits
max_workers = 2   # Reduce concurrent requests
retry_delay = 2.0  # Increase delay between retries
```

## Maintenance

### Regular Tasks

1. **Weekly**
   - Check log files for errors
   - Monitor disk space usage

2. **Monthly**
   - Clean old log files: `find logs/ -name "*.log" -mtime +30 -delete`
   - Archive old outputs: `tar -czf output_archive.tar.gz output/`

3. **Quarterly**
   - Update dependencies: `pip install --upgrade -r requirements.txt`
   - Review API usage and costs

### Updating the Application

```bash
# Stop the service
docker stop ebay-draftmaker  # or: sudo systemctl stop ebay-draftmaker

# Pull latest changes
git pull origin main

# Rebuild and restart
./deploy.sh docker  # or your deployment method
```

## Support

### Getting Help

1. Check logs for error messages
2. Review this documentation
3. Check API provider status pages
4. Open an issue on GitHub

### Useful Resources

- [eBay Developer Documentation](https://developer.ebay.com/docs)
- [Spotify Web API](https://developer.spotify.com/documentation/web-api/)
- [MusicBrainz API](https://musicbrainz.org/doc/Development/XML_Web_Service/Version_2)
- [Discogs API](https://www.discogs.com/developers/)

## License

[Your License Here]

## Version History

- v1.0.0 - Initial release with full pipeline support
- v1.1.0 - Added batch processing from GCS
- v1.2.0 - Improved error handling and retry logic
