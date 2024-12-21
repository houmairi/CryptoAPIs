config = {
    'database': {
        'host': 'localhost',
        'database': 'crypto_db', # name of db
        'user': 'your_username', # username which will access the db duh
        'password': 'your_password', # and the chosen pw (when installed locally the pw you set during installation)
        'port': 5432
    },
    'collection': {
        'symbols': ['BTC', 'ETH', 'BNB', 'SOL'],  # Add or remove symbols as needed
        'sync_interval': 60,  # Sync to every X minutes (60 for hourly)
        'intervals': {
            'price_ticks': 60,  # seconds
            'metadata': 300,    # seconds
            'ohlcv': {
                '1m': 60,
                '5m': 300,
                '15m': 900,
                '1h': 3600,
                '4h': 14400,
                '1d': 86400
            }
        }
    },
    'apis': {
        'binance': {
            'base_url': 'https://api.binance.com/api/v3',
            'rate_limit': 1200
        },
        'coingecko': {
            'base_url': 'https://api.coingecko.com/api/v3',
            'rate_limit': 50,
            'api_key': None  # Optional: Add your API key if you have one
        }
    },
    'validation': {
        'min_trades': {
            '1m': 2,     # Base minimum trades
            '5m': 20,    # Base for 5m
            '15m': 50,   # Base for 15m
            '1h': 150,   # Base for 1h
            '4h': 500,   # Base for 4h
            '1d': 2000   # Base for daily
        },
        'min_volume': {
            '1m': 0.1,   # Base minimum volume
            '5m': 0.5,   # Base for 5m
            '15m': 1.5,  # Base for 15m
            '1h': 5.0,   # Base for 1h
            '4h': 15.0,  # Base for 4h
            '1d': 50.0   # Base for daily
        }
    }
}