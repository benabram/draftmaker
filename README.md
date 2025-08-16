# eBay Draft Maker

Automated eBay draft listing creator for music media (CDs, vinyl, cassettes) using UPC codes.

## 🎯 What It Does

This application takes UPC codes and automatically:
1. Fetches album metadata from MusicBrainz, Discogs, and Spotify
2. Retrieves album artwork from Cover Art Archive and Spotify
3. Analyzes eBay sold listings for pricing recommendations
4. Creates draft eBay listings with all the information

## 🚀 Quick Start

### Option 1: Google Cloud Run (Recommended)

Deploy to Google Cloud Run for serverless, on-demand processing:

```bash
# Clone repository
git clone <repository-url>
cd draftmaker

# Deploy to Cloud Run
chmod +x deploy-cloudrun.sh
./deploy-cloudrun.sh  # Choose option 1 for first-time setup
```

See [CLOUDRUN_SIMPLE.md](CLOUDRUN_SIMPLE.md) for detailed instructions.

### Option 2: Local Installation

Run locally with Python:

```bash
# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure API keys
cp config.ini.example config.ini
# Edit config.ini with your API credentials

# Run
python main.py --upc-file data/test_upcs.txt
```

### Option 3: Docker

Run in a container:

```bash
# Deploy with Docker
./deploy.sh docker
```

## 📋 Prerequisites

### Required API Keys

1. **Spotify API**
   - Get from: https://developer.spotify.com/dashboard
   - Required: Client ID and Client Secret

2. **eBay API**
   - Get from: https://developer.ebay.com/
   - Required: App ID, Cert ID, Dev ID, and User Refresh Token
   - Follow eBay's OAuth flow to get the refresh token

3. **Optional APIs** (no keys needed)
   - MusicBrainz (rate limited)
   - Discogs (rate limited)

## 🏗️ Architecture

```
┌──────────────┐
│  UPC Input   │ (.txt file or GCS)
└──────┬───────┘
       │
┌──────▼───────┐
│ Orchestrator │ (main.py)
└──────┬───────┘
       │
   ┌───┴────┬──────┬──────┬──────┐
   │        │      │      │      │
┌──▼──┐ ┌──▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼──┐
│ UPC │ │Meta │ │Img │ │Price│ │Draft│
│Proc │ │Fetch│ │Fetch│ │Fetch│ │Comp │
└─────┘ └──┬──┘ └──┬─┘ └──┬─┘ └──┬─┘
           │       │       │       │
      ┌────▼───────▼───────▼───┐   │
      │   External APIs         │   │
      │ • MusicBrainz           │   │
      │ • Discogs               │   │
      │ • Spotify               │   │
      │ • Cover Art Archive     │   │
      │ • eBay Finding API      │   │
      └─────────────────────────┘   │
                                     │
                           ┌─────────▼─────────┐
                           │ eBay Sell API     │
                           │ (Draft Creation)  │
                           └───────────────────┘
```

## 📁 Project Structure

```
draftmaker/
├── src/
│   ├── components/
│   │   ├── upc_processor.py      # UPC validation and info extraction
│   │   ├── metadata_fetcher.py   # Album metadata retrieval
│   │   ├── image_fetcher.py      # Album artwork retrieval
│   │   ├── pricing_fetcher.py    # eBay pricing analysis
│   │   └── draft_composer.py     # eBay draft creation
│   ├── orchestrator/
│   │   └── listing_orchestrator.py # Main pipeline coordinator
│   └── utils/
│       ├── api_client.py         # API client utilities
│       ├── rate_limiter.py       # Rate limiting
│       └── logger.py             # Logging configuration
├── tests/
│   ├── unit/                    # Unit tests
│   └── integration/             # Integration tests
├── deploy/
│   └── deploy.sh               # Local deployment scripts
├── data/
│   └── test_upcs.txt          # Sample UPC codes
├── config.ini.example          # Configuration template
├── requirements.txt            # Python dependencies
├── Dockerfile.production       # Docker configuration
├── deploy-cloudrun.sh         # Cloud Run deployment
└── main.py                    # Entry point
```

## 🔧 Configuration

Create a `config.ini` file based on the example:

```ini
[APIs]
musicbrainz_user_agent = YourApp/1.0 (your@email.com)
spotify_client_id = your_spotify_client_id
spotify_client_secret = your_spotify_client_secret
ebay_app_id = your_ebay_app_id
ebay_cert_id = your_ebay_cert_id
ebay_dev_id = your_ebay_dev_id
ebay_refresh_token = your_ebay_refresh_token
ebay_environment = production  # or sandbox
ebay_site_id = 0  # 0 for US

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
```

## 📊 Input/Output

### Input Format

Create a text file with one UPC per line:
```
602537351169
828768352625
093624974680
```

### Output Files

The application generates:
- `output/drafts_YYYYMMDD_HHMMSS.json` - Draft listing details
- `logs/app.log` - Application logs
- `logs/errors_YYYYMMDD_HHMMSS.log` - Failed UPCs

### Sample Output

```json
{
  "upc": "602537351169",
  "draft_id": "123456789",
  "sku": "UPC-602537351169",
  "title": "Random Access Memories by Daft Punk (CD, 2013)",
  "price": 15.99,
  "images": [
    "https://example.com/album-cover.jpg"
  ],
  "status": "success"
}
```

## 🧪 Testing

Run the test suite:

```bash
# All tests
python -m pytest tests/ -v

# Unit tests only
python -m pytest tests/unit/ -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=html
```

## 🚢 Deployment Options

### Google Cloud Run (Recommended)
- Serverless, scales to zero
- Pay only when running
- See [CLOUDRUN_SIMPLE.md](CLOUDRUN_SIMPLE.md)

### Local Docker
```bash
./deploy.sh docker
```

### Systemd Service (Linux)
```bash
./deploy.sh systemd
```

### Cron Job
```bash
./deploy.sh cron
```

## 📈 Performance

- Processes ~100 UPCs in 5-10 minutes
- Handles rate limiting automatically
- Retries failed requests
- Concurrent processing for efficiency

## 🔒 Security

- API keys stored in environment variables or Secret Manager
- No credentials in code
- HTTPS for all API calls
- Minimal permissions for service accounts

## 🐛 Troubleshooting

### Common Issues

1. **Rate Limiting (429 errors)**
   - Reduce `batch_size` in config.ini
   - Increase `retry_delay`

2. **Token Expired (401 errors)**
   - eBay tokens expire after 18 months
   - Generate new refresh token

3. **No Metadata Found**
   - Some UPCs may not be in music databases
   - Check UPC is for music media

4. **Timeout Errors**
   - Increase timeout settings
   - Check network connectivity

### Debug Mode

Enable detailed logging:
```bash
export LOG_LEVEL=DEBUG
python main.py --upc-file data/test_upcs.txt
```

## 📚 Documentation

- [Production Deployment](PRODUCTION.md) - Detailed deployment guide
- [Cloud Run Setup](CLOUDRUN_SIMPLE.md) - Google Cloud Run instructions
- [API Documentation](docs/API.md) - Component API reference

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📄 License

[Your License Here]

## 🙏 Acknowledgments

- MusicBrainz for open music metadata
- Spotify Web API for album information
- eBay APIs for marketplace integration
- Cover Art Archive for album artwork

## 📮 Support

For issues or questions:
1. Check the [Troubleshooting](#-troubleshooting) section
2. Review logs for error details
3. Open an issue on GitHub

---

Built with ❤️ for music collectors and eBay sellers
