import asyncio
import aiohttp
from datetime import datetime
import logging
from src.database import DatabaseHandler

class CryptoDataCollector:
    def __init__(self, config):
        self.config = config
        self.db = DatabaseHandler(config)
        self.setup_logging()
        
    def setup_logging(self):
        self.logger = logging.getLogger(__name__)
    
    async def collect_binance_data(self, symbol):
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
    
    async def collect_coingecko_data(self, coin_id):
        url = f"{self.config['apis']['coingecko']['base_url']}/coins/{coin_id}"
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        await self.db.save_metadata(data, 'coingecko')
                    else:
                        self.logger.error(f"Error collecting CoinGecko data: Status {response.status}")
            except Exception as e:
                self.logger.error(f"Error in CoinGecko collection for {coin_id}: {e}")

    async def continuous_collection(self):
        while True:
            try:
                tasks = []
                for symbol in self.config['collection']['symbols']:
                    tasks.append(asyncio.create_task(self.collect_binance_data(symbol)))
                
                if datetime.now().minute % 5 == 0:
                    for symbol in self.config['collection']['symbols']:
                        tasks.append(asyncio.create_task(self.collect_coingecko_data(symbol.lower())))
                
                # Wait for all tasks to complete
                await asyncio.gather(*tasks, return_exceptions=True)
                
                # Wait for next interval
                await asyncio.sleep(self.config['collection']['interval'])
                
            except Exception as e:
                self.logger.error(f"Error in continuous collection: {e}")
                await asyncio.sleep(5)