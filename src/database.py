import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import logging
import asyncio
import os
import json

class DatabaseHandler:
    def __init__(self, config):
        self.config = config['database']
        self.conn = None
        self.setup_logging()
        self.initialize_database()
        self.initialize_tracked_coins()
        
    def setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('crypto_collector.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def initialize_database(self):
        """Initialize database with schema if tables don't exist"""
        try:
            # First try to connect to the database
            try:
                self.connect()
            except psycopg2.OperationalError as e:
                if "does not exist" in str(e):
                    # Database doesn't exist, create it
                    temp_config = self.config.copy()
                    temp_config['database'] = 'postgres'  # Connect to default postgres database
                    with psycopg2.connect(**temp_config) as conn:
                        conn.autocommit = True
                        with conn.cursor() as cur:
                            cur.execute(f"CREATE DATABASE {self.config['database']}")
                    self.connect()
                else:
                    raise
                
                # Read and execute schema.sql
            schema_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'schema.sql')
            with open(schema_path, 'r') as f:
                schema_sql = f.read()
                
            with self.conn.cursor() as cur:
                cur.execute(schema_sql)
            
            self.conn.commit()
            self.logger.info("Database initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            raise
    
    def connect(self):
        if not self.conn or self.conn.closed:
            try:
                self.conn = psycopg2.connect(**self.config)
                self.conn.autocommit = True
                self.logger.info("Successfully connected to database")
            except Exception as e:
                self.logger.error(f"Error connecting to database: {e}")
                raise

    def get_or_create_coin(self, symbol):
        """Get coin_id or create new coin entry if it doesn't exist"""
        try:
            self.connect()
            with self.conn.cursor() as cur:
                clean_symbol = symbol.replace('USDT', '')
                
                cur.execute("""
                    SELECT id FROM coins WHERE symbol = %s
                """, (clean_symbol,))
                
                result = cur.fetchone()
                if result:
                    return result[0]
                
                cur.execute("""
                    INSERT INTO coins (symbol, name)
                    VALUES (%s, %s)
                    RETURNING id
                """, (clean_symbol, clean_symbol))
                
                return cur.fetchone()[0]
                
        except Exception as e:
            self.logger.error(f"Error getting/creating coin: {e}")
            raise
        
    async def get_recent_ohlcv_data(self, symbol, timeframe, limit=5):
        """Get recent OHLCV data for calculating dynamic thresholds"""
        try:
            def db_operation():
                self.connect()
                with self.conn.cursor() as cur:
                    # Get coin_id first
                    clean_symbol = symbol.replace('USDT', '')
                    cur.execute("""
                        SELECT timestamp, volume, num_trades as trades
                        FROM ohlcv_data od
                        JOIN coins c ON od.coin_id = c.id
                        WHERE c.symbol = %s AND timeframe = %s
                        ORDER BY timestamp DESC
                        LIMIT %s
                    """, (clean_symbol, timeframe, limit))
                    
                    rows = cur.fetchall()
                    # Convert to list of dicts
                    columns = ['timestamp', 'volume', 'trades']
                    return [dict(zip(columns, row)) for row in rows]

            # Run database operation in a thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, db_operation)
            return result

        except Exception as e:
            self.logger.error(f"Error getting recent OHLCV data: {e}")
            return []
        
    async def get_ohlcv_data(self, symbol: str, timeframe: str, start_date=None):
        """Get OHLCV data for a specific symbol and timeframe"""
        try:
            def db_operation():
                self.connect()
                with self.conn.cursor() as cur:
                    clean_symbol = symbol.replace('USDT', '')
                    query = """
                        SELECT 
                            od.timestamp,
                            od.open_price,
                            od.high_price,
                            od.low_price,
                            od.close_price,
                            od.volume,
                            od.num_trades
                        FROM ohlcv_data od
                        JOIN coins c ON od.coin_id = c.id
                        WHERE c.symbol = %s 
                        AND od.timeframe = %s
                    """
                    params = [clean_symbol, timeframe]
                    
                    if start_date:
                        query += " AND od.timestamp >= %s"
                        params.append(start_date)
                        
                    query += " ORDER BY od.timestamp DESC"
                    
                    cur.execute(query, params)
                    columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'num_trades']
                    return [dict(zip(columns, row)) for row in cur.fetchall()]
                    
            # Run database operation in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, db_operation)
            return result
            
        except Exception as e:
            self.logger.error(f"Error getting OHLCV data: {e}")
            return []

    async def save_ticker_data(self, data, source):
        """Async wrapper for database operations"""
        try:
            def db_operation():
                coin_id = self.get_or_create_coin(data['symbol'])
                
                with self.conn.cursor() as cur:
                    query = """
                    INSERT INTO price_ticks (
                        coin_id, timestamp, price, volume, bid_price, ask_price, source
                    ) VALUES %s
                    ON CONFLICT (coin_id, timestamp, source) 
                    DO NOTHING
                    """
                    
                    values = [(
                        coin_id,
                        datetime.fromtimestamp(data['closeTime']/1000),
                        float(data['lastPrice']),
                        float(data['volume']),
                        float(data['bidPrice']),
                        float(data['askPrice']),
                        source
                    )]
                    
                    execute_values(cur, query, values)
                    self.logger.info(f"Saved ticker data for {data['symbol']}")
            
            # Run database operation in a thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, db_operation)
                
        except Exception as e:
            self.logger.error(f"Error saving ticker data: {e}")
            raise
            
    async def save_metadata(self, data, source):
        try:
            def db_operation():
                self.connect()
                with self.conn.cursor() as cur:
                    # Update or insert coin info
                    cur.execute("""
                        INSERT INTO coins (coingecko_id, symbol, name)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (symbol) DO UPDATE 
                        SET coingecko_id = EXCLUDED.coingecko_id,
                            name = EXCLUDED.name, 
                            updated_at = CURRENT_TIMESTAMP
                    """, (data['id'], data['symbol'].upper(), data['name']))
                    
                    # Save metadata
                    cur.execute("""
                        INSERT INTO coin_metadata (
                            coin_id, timestamp, market_cap_rank, categories,
                            website_url, github_url
                        ) VALUES (
                            (SELECT id FROM coins WHERE coingecko_id = %s),
                            %s, %s, %s, %s, %s
                        )
                    """, (
                        data['id'],
                        datetime.now(),
                        data.get('market_cap_rank'),
                        data.get('categories', []),
                        data['links']['homepage'][0] if data['links']['homepage'] else None,
                        data['links']['repos_url']['github'][0] if data['links']['repos_url']['github'] else None
                    ))
                    
            # Run database operation in a thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, db_operation)
                
        except Exception as e:
            self.logger.error(f"Error saving metadata: {e}")
            raise
        
    def initialize_tracked_coins(self):
        """Initialize basic entries for all tracked coins"""
        try:
            self.connect()
            with self.conn.cursor() as cur:
                for symbol in ['BTC', 'ETH', 'BNB', 'SOL']:  # Add all your tracked coins
                    cur.execute("""
                        INSERT INTO coins (symbol, name)
                        VALUES (%s, %s)
                        ON CONFLICT (symbol) DO NOTHING
                    """, (symbol, symbol))
            self.conn.commit()
        except Exception as e:
            self.logger.error(f"Error initializing tracked coins: {e}")
            raise
        
    async def save_ohlcv_data(self, symbol, timeframe, data):
        """Save OHLCV data to database with additional checks"""
        try:
            if not data or len(data) == 0:
                self.logger.warning(f"No OHLCV data received for {symbol} {timeframe}")
                return
                
            kline = data[0]  # Get first kline since limit=1
            
            def db_operation():
                coin_id = self.get_or_create_coin(symbol)
                timestamp = datetime.fromtimestamp(kline[0]/1000)
                
                # Add check for existing data
                with self.conn.cursor() as cur:
                    # First check if we already have data for this timestamp and timeframe
                    cur.execute("""
                        SELECT volume, num_trades 
                        FROM ohlcv_data 
                        WHERE coin_id = %s 
                        AND timestamp = %s 
                        AND timeframe = %s
                    """, (coin_id, timestamp, timeframe))
                    
                    existing = cur.fetchone()
                    if existing:
                        # Compare with existing data
                        existing_volume, existing_trades = existing
                        new_volume = float(kline[5])
                        new_trades = int(kline[8])
                        
                        if existing_volume == new_volume and existing_trades == new_trades:
                            self.logger.warning(
                                f"Duplicate data detected for {symbol} {timeframe} at {timestamp}. "
                                f"Existing volume: {existing_volume}, new volume: {new_volume}. "
                                f"Existing trades: {existing_trades}, new trades: {new_trades}"
                            )
                    
                    # Insert or update the data
                    cur.execute("""
                        INSERT INTO ohlcv_data (
                            coin_id, timestamp, timeframe, open_price, high_price,
                            low_price, close_price, volume, num_trades
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (coin_id, timestamp, timeframe) 
                        DO UPDATE SET
                            open_price = EXCLUDED.open_price,
                            high_price = EXCLUDED.high_price,
                            low_price = EXCLUDED.low_price,
                            close_price = EXCLUDED.close_price,
                            volume = EXCLUDED.volume,
                            num_trades = EXCLUDED.num_trades
                    """, (
                        coin_id,
                        timestamp,
                        timeframe,
                        float(kline[1]),  # Open
                        float(kline[2]),  # High
                        float(kline[3]),  # Low
                        float(kline[4]),  # Close
                        float(kline[5]),  # Volume
                        int(kline[8])     # Number of trades
                    ))
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, db_operation)
                
        except Exception as e:
            self.logger.error(f"Error saving OHLCV data: {e}")
            raise
        
    async def save_invalid_data(self, symbol, data_type, timeframe, data, error_message):
        """Save invalid data to a separate table for analysis"""
        try:
            def db_operation():
                self.connect()
                with self.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO invalid_data 
                        (symbol, data_type, timeframe, raw_data, error_message)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (
                        symbol,
                        data_type,
                        timeframe,
                        psycopg2.extras.Json(data),  # Convert dict to JSONB
                        error_message
                    ))
            
            # Run database operation in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, db_operation)
                
        except Exception as e:
            self.logger.error(f"Error saving invalid data: {e}")
            raise