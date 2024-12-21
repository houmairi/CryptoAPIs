-- Core tables
CREATE TABLE IF NOT EXISTS coins (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(10) NOT NULL,
    name VARCHAR(100) NOT NULL,
    coingecko_id VARCHAR(100) UNIQUE,
    description TEXT,
    genesis_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol)
);

-- Price data with high granularity
CREATE TABLE IF NOT EXISTS price_ticks (
    id SERIAL PRIMARY KEY,
    coin_id INTEGER REFERENCES coins(id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    price NUMERIC(24,8) NOT NULL,
    volume NUMERIC(24,8),
    bid_price NUMERIC(24,8),
    ask_price NUMERIC(24,8),
    source VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(coin_id, timestamp, source)
);

-- Metadata updates
CREATE TABLE IF NOT EXISTS coin_metadata (
    id SERIAL PRIMARY KEY,
    coin_id INTEGER REFERENCES coins(id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    market_cap_rank INTEGER,
    categories TEXT[],
    website_url TEXT,
    github_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- OHLCV data
CREATE TABLE IF NOT EXISTS ohlcv_data (
    id SERIAL PRIMARY KEY,
    coin_id INTEGER REFERENCES coins(id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    timeframe VARCHAR(10) NOT NULL,
    open_price NUMERIC(24,8),
    high_price NUMERIC(24,8),
    low_price NUMERIC(24,8),
    close_price NUMERIC(24,8),
    volume NUMERIC(24,8),
    num_trades INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(coin_id, timestamp, timeframe)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_price_ticks_timestamp ON price_ticks(timestamp);
CREATE INDEX IF NOT EXISTS idx_price_ticks_coin_timestamp ON price_ticks(coin_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_coins_symbol ON coins(symbol);
CREATE INDEX IF NOT EXISTS idx_ohlcv_coin_time ON ohlcv_data(coin_id, timestamp);