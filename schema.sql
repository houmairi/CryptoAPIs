-- First, drop existing tables if needed (be careful with this in production!)
-- DROP TABLE IF EXISTS price_ticks CASCADE;
-- DROP TABLE IF EXISTS coin_metadata CASCADE;
-- DROP TABLE IF EXISTS coins CASCADE;

-- Core tables
CREATE TABLE coins (
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
CREATE TABLE price_ticks (
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
CREATE TABLE coin_metadata (
    id SERIAL PRIMARY KEY,
    coin_id INTEGER REFERENCES coins(id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    market_cap_rank INTEGER,
    categories TEXT[],
    website_url TEXT,
    github_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_price_ticks_timestamp ON price_ticks(timestamp);
CREATE INDEX idx_price_ticks_coin_timestamp ON price_ticks(coin_id, timestamp);
CREATE INDEX idx_coins_symbol ON coins(symbol);
CREATE INDEX idx_ohlcv_coin_time ON ohlcv_data(coin_id, timestamp);



