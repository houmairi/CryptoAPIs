# Crypto Data Collection System

A robust, automated system for collecting and storing cryptocurrency market data, designed for ML model training and market analysis.

## Overview

This project implements a comprehensive cryptocurrency data collection system that continuously gathers market data from multiple sources (Binance and CoinGecko) and stores it in a PostgreSQL database. The system is designed to be reliable, scalable, and suitable for machine learning applications.

## Features

- **Real-time Data Collection**
  - Price ticks (1-minute intervals)
  - OHLCV (candlestick) data at multiple timeframes
  - Metadata updates from CoinGecko
  - Currently tracking: BTC, ETH, BNB, SOL

- **Supported Timeframes**
  - 1 minute
  - 5 minutes
  - 15 minutes
  - 1 hour
  - 4 hours
  - 1 day

- **Technical Implementation**
  - Asynchronous data collection using `aiohttp`
  - Thread-safe database operations
  - Rate limit management
  - Error handling and automatic retry logic
  - Proper connection pooling
  - Minute-aligned data collection

## System Requirements

- Python 3.8+
- PostgreSQL 12+
- Required Python packages:
  - aiohttp
  - asyncio
  - psycopg2
  - logging

## Project Structure

```
CryptoAPIs/
├── src/
│   ├── __init__.py
│   ├── database.py      # Database operations
│   ├── collector.py     # Data collection logic
│   └── config.py        # Configuration settings
├── schema.sql          # Database schema
├── main.py            # Entry point
├── requirements.txt    # Dependencies
└── README.md
```

## Database Schema

- **coins**: Base cryptocurrency information
- **price_ticks**: High-frequency price and volume data
- **coin_metadata**: Detailed coin information and updates
- **ohlcv_data**: Candlestick data at different timeframes

## Installation

1. Clone the repository:
```bash
git clone [repository-url]
cd CryptoAPIs
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up PostgreSQL database:
```bash
psql -U postgres
CREATE DATABASE crypto_db;
```

5. Initialize the database schema:
```bash
psql -U postgres -d crypto_db -f schema.sql
```

## Configuration

Update `config.py` with your settings:
- Database credentials
- API configurations
- Collection intervals
- Tracked symbols

## Usage

Run the collector:
```bash
python main.py
```

Run the Debug Version: 
```bash
# Will run the collector with 3 Data Points needed to evaluate threshold instead of 100 Data Points needed
python main.py --debug
```

## Future Plans

1. Data Analysis Tools
   - Real-time analytics dashboard
   - Data export capabilities
   - Customizable alerts system

2. Enhanced Features
   - Support for more exchanges
   - Additional cryptocurrencies
   - Order book data collection
   - Market sentiment analysis
   - Network metrics collection (blockchain data)

3. ML Integration
   - Feature engineering pipelines
   - Basic ML models for testing
   - Real-time prediction capabilities
   - Automated backtesting framework

4. System Improvements
   - Advanced error recovery
   - Data validation and cleaning
   - Performance optimizations
   - Data backup solutions
   - Monitoring and alerting system

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is for educational and research purposes only. Always conduct your own research before making any investment decisions.