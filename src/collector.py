import asyncio
import aiohttp
import time
from datetime import datetime
import logging
from src.database import DatabaseHandler
import random

class CryptoDataCollector:
    def __init__(self, config):
        self.config = config
        self.db = DatabaseHandler(config)
        self.setup_logging()
        self.timeframes = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400
        }
        # CoinGecko ID mapping
        self.coingecko_ids = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'BNB': 'binancecoin',
            'SOL': 'solana'
        }
        
    def setup_logging(self):
        self.logger = logging.getLogger(__name__)
    
    async def collect_ticker_data(self, symbol):  # This was previously collect_binance_data
        """Collect real-time ticker data from Binance"""
        url = f"{self.config['apis']['binance']['base_url']}/ticker/24hr"
        params = {'symbol': f"{symbol}USDT"}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        await self.db.save_ticker_data(data, 'binance')
                    else:
                        self.logger.error(f"Error collecting Binance data: Status {response.status}")
            except Exception as e:
                self.logger.error(f"Error in Binance collection for {symbol}: {e}")

    async def collect_klines_data(self, symbol, timeframe):
        """Collect OHLCV data for a specific timeframe"""
        url = f"{self.config['apis']['binance']['base_url']}/klines"
        params = {
            'symbol': f"{symbol}USDT",
            'interval': timeframe,
            'limit': 1000
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        await self.db.save_ohlcv_data(symbol, timeframe, data)
                    else:
                        self.logger.error(f"Error collecting klines data: Status {response.status}")
            except Exception as e:
                self.logger.error(f"Error in klines collection for {symbol} {timeframe}: {e}")

    async def collect_coingecko_data(self, symbol):
        """Collect metadata from CoinGecko using correct coin IDs"""
        coin_id = self.coingecko_ids.get(symbol.upper())
        if not coin_id:
            self.logger.warning(f"No CoinGecko ID mapping for symbol {symbol}")
            return

        url = f"{self.config['apis']['coingecko']['base_url']}/coins/{coin_id}"
        params = {
            'localization': 'false',
            'tickers': 'false',
            'community_data': 'false',
            'developer_data': 'false'
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        await self.db.save_metadata(data, 'coingecko')
                        self.logger.info(f"Successfully collected CoinGecko data for {symbol}")
                    elif response.status == 429:  # Rate limit
                        self.logger.warning("CoinGecko rate limit reached, waiting before next request")
                        await asyncio.sleep(60)  # Wait a minute before retrying
                    else:
                        self.logger.error(f"Error collecting CoinGecko data for {symbol}: Status {response.status}")
            except Exception as e:
                self.logger.error(f"Error in CoinGecko collection for {symbol}: {e}")

    async def continuous_collection(self):
        while True:
            try:
                tasks = []
                current_time = time.time()
                
                # Regular ticker data collection
                for symbol in self.config['collection']['symbols']:
                    tasks.append(asyncio.create_task(self.collect_ticker_data(symbol)))
                
                # OHLCV data collection based on timeframe
                for symbol in self.config['collection']['symbols']:
                    for timeframe, seconds in self.timeframes.items():
                        if int(current_time) % seconds < 2:
                            tasks.append(asyncio.create_task(
                                self.collect_klines_data(symbol, timeframe)
                            ))
                
                # CoinGecko metadata collection (every 5 minutes)
                if datetime.now().minute % 5 == 0:
                    for symbol in self.config['collection']['symbols']:
                        tasks.append(asyncio.create_task(
                            self.collect_coingecko_data(symbol)  # Pass the symbol directly
                        ))
                
                # Wait for all tasks to complete
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Add some randomization to the interval to prevent exact timing issues
                jitter = random.uniform(-0.1, 0.1)  # ±0.1 seconds
                await asyncio.sleep(self.config['collection']['interval'] + jitter)
                
            except Exception as e:
                self.logger.error(f"Error in continuous collection: {e}")
                await asyncio.sleep(5)