import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime
import logging
import asyncio
from functools import partial

class DatabaseHandler:
    def __init__(self, config):
        self.config = config['database']
        self.conn = None
        self.setup_logging()
        
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
        """Async wrapper for metadata operations"""
        try:
            def db_operation():
                self.connect()
                with self.conn.cursor() as cur:
                    # Update or insert coin info
                    cur.execute("""
                        INSERT INTO coins (coingecko_id, symbol, name)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (coingecko_id) DO UPDATE 
                        SET name = EXCLUDED.name, 
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