import asyncio
import aiohttp
import time
from datetime import datetime
from datetime import timedelta
import logging
from src.database import DatabaseHandler
import random

class CryptoDataCollector:
    def __init__(self, config):
        self.config = config
        self.db = DatabaseHandler(config)
        self.setup_logging()
        self.timeframes = {
            '1m': '1m',
            '5m': '5m',
            '15m': '15m',
            '1h': '1h',
            '4h': '4h',
            '1d': '1d'
        }
        self.coingecko_ids = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum',
            'BNB': 'binancecoin',
            'SOL': 'solana'
        }
        self.collection_task = None
        self.running = False
        
    def setup_logging(self):
        self.logger = logging.getLogger(__name__)
    
    async def start_collection(self):
        """Start the collection process"""
        self.running = True
        self.collection_task = asyncio.create_task(self.continuous_collection())
        self.logger.info("Started crypto data collection")

    async def stop_collection(self):
        """Stop the collection process"""
        self.running = False
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        self.logger.info("Stopped crypto data collection")

    async def collect_ticker_data(self, symbol):
        """Collect real-time ticker data from Binance"""
        url = f"{self.config['apis']['binance']['base_url']}/ticker/24hr"
        params = {'symbol': f"{symbol}USDT"}
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        await self.db.save_ticker_data(data, 'binance')
                        self.logger.debug(f"Successfully collected ticker data for {symbol}")
                    elif response.status == 429:  # Rate limit
                        self.logger.warning("Binance rate limit reached, waiting before next request")
                        await asyncio.sleep(60)
                    elif response.status == 404:
                        self.logger.error(f"Symbol {symbol}USDT not found on Binance")
                        await asyncio.sleep(5)
                    else:
                        self.logger.error(f"Error collecting Binance data: Status {response.status}")
                        await asyncio.sleep(5)
            except Exception as e:
                self.logger.error(f"Error in Binance collection for {symbol}: {e}")
                await asyncio.sleep(5)

    async def collect_klines_data(self, symbol, timeframe):
        """Collect OHLCV data for a specific timeframe"""
        url = f"{self.config['apis']['binance']['base_url']}/klines"
        params = {
            'symbol': f"{symbol}USDT",
            'interval': timeframe,
            'limit': 1
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, params=params) as response:
                    response_text = await response.text()
                    if response.status == 200:
                        data = await response.json()
                        await self.db.save_ohlcv_data(symbol, timeframe, data)
                        self.logger.debug(f"Successfully collected klines for {symbol} {timeframe}")
                    elif response.status == 429:
                        self.logger.warning("Binance rate limit reached, waiting before next request")
                        await asyncio.sleep(60)
                    elif response.status == 404:
                        self.logger.error(f"Symbol {symbol}USDT or timeframe {timeframe} not found")
                        self.logger.debug(f"Response: {response_text}")
                        await asyncio.sleep(5)
                    else:
                        self.logger.error(f"Error collecting klines: Status {response.status}")
                        self.logger.debug(f"Response: {response_text}")
                        await asyncio.sleep(5)
            except Exception as e:
                self.logger.error(f"Error in klines collection for {symbol} {timeframe}: {e}")
                await asyncio.sleep(5)

    async def collect_coingecko_data(self, symbol):
        """Collect metadata from CoinGecko"""
        coin_id = self.coingecko_ids.get(symbol.upper())
        if not coin_id:
            self.logger.warning(f"No CoinGecko ID mapping for symbol {symbol}")
            return

        url = f"{self.config['apis']['coingecko']['base_url']}/coins/{coin_id}"
        params = {
            'localization': 'false',
            'tickers': 'false',
            'market_data': 'true',
            'community_data': 'false',
            'developer_data': 'false'
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                headers = {'accept': 'application/json'}
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        await self.db.save_metadata(data, 'coingecko')
                        self.logger.info(f"Successfully collected CoinGecko data for {symbol}")
                    elif response.status == 429:
                        self.logger.warning("CoinGecko rate limit reached, waiting before next request")
                        await asyncio.sleep(60)
                    else:
                        self.logger.error(f"Error collecting CoinGecko data: Status {response.status}")
            except Exception as e:
                self.logger.error(f"Error in CoinGecko collection for {symbol}: {e}")
                await asyncio.sleep(5)

    def validate_symbol(self, symbol):
        """Validate trading pair symbol"""
        return f"{symbol}USDT"

    def validate_timeframe(self, timeframe):
        """Validate and return correct timeframe format"""
        valid_timeframes = ['1m', '5m', '15m', '1h', '4h', '1d']
        if timeframe not in valid_timeframes:
            raise ValueError(f"Invalid timeframe {timeframe}. Must be one of {valid_timeframes}")
        return timeframe

    async def test_connection(self):
        """Test API connectivity"""
        url = f"{self.config['apis']['binance']['base_url']}/ping"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        self.logger.info("Successfully connected to Binance API")
                        return True
                    else:
                        self.logger.error(f"Failed to connect to Binance API: {response.status}")
                        return False
            except Exception as e:
                self.logger.error(f"Connection test failed: {e}")
                return False

    async def continuous_collection(self):
        """Continuous collection synchronized to minute marks"""
        if not await self.test_connection():
            self.logger.error("Failed to establish connection. Exiting...")
            return

        # Initial synchronization to next minute mark
        now = datetime.now()
        next_minute = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
        wait_seconds = (next_minute - now).total_seconds()
        
        if wait_seconds > 0:
            self.logger.info(f"Initial synchronization to next minute mark ({wait_seconds:.2f} seconds)...")
            await asyncio.sleep(wait_seconds)

        while self.running:
            try:
                start_time = datetime.now()
                tasks = []
                
                # Collect data
                for symbol in self.config['collection']['symbols']:
                    tasks.append(asyncio.create_task(self.collect_ticker_data(symbol)))
                    for timeframe in self.timeframes:
                        tasks.append(asyncio.create_task(
                            self.collect_klines_data(symbol, timeframe)
                        ))

                # Execute all tasks
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Calculate time taken and adjust sleep to hit next minute mark precisely
                collection_time = (datetime.now() - start_time).total_seconds()
                sleep_time = max(0, 60 - collection_time)
                
                self.logger.debug(f"Collection took {collection_time:.2f}s, sleeping for {sleep_time:.2f}s")
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in continuous collection: {e}")
                if self.running:
                    await asyncio.sleep(5)