import asyncio
import aiohttp
import time
from datetime import datetime
from datetime import timedelta
import logging
from src.database import DatabaseHandler
import random
from src.data_quality import DataQualityMonitor
from collections import defaultdict

class ValidationError(Exception):
    """Custom exception for data validation errors"""
    pass

class CryptoDataCollector:
    # Define default threshold values as class variables
    DEFAULT_MIN_TRADES = {
        '1m': 2,     # Base minimum trades
        '5m': 20,    # Base for 5m
        '15m': 50,   # Base for 15m
        '1h': 150,   # Base for 1h
        '4h': 500,   # Base for 4h
        '1d': 2000   # Base for daily
    }
    
    DEFAULT_MIN_VOLUME = {
        '1m': 0.1,   # Base minimum volume
        '5m': 0.5,   # Base for 5m
        '15m': 1.5,  # Base for 15m
        '1h': 5.0,   # Base for 1h
        '4h': 15.0,  # Base for 4h
        '1d': 50.0   # Base for daily
    }

    def __init__(self, config):
        self.config = config
        self.db = DatabaseHandler(config)
        self.setup_logging()
        
        # Initialize thresholds from config or use defaults
        self.min_trades = config.get('validation', {}).get('min_trades', self.DEFAULT_MIN_TRADES)
        self.min_volume = config.get('validation', {}).get('min_volume', self.DEFAULT_MIN_VOLUME)
        
        self.quality_monitor = None  # Will be set via set_quality_monitor
        self.initialization_done = defaultdict(lambda: defaultdict(bool))
        
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
        
    def get_base_thresholds(self, timeframe):
        """Get base threshold values for each timeframe"""
        return (
            self.min_trades.get(timeframe, self.DEFAULT_MIN_TRADES[timeframe]),
            self.min_volume.get(timeframe, self.DEFAULT_MIN_VOLUME[timeframe])
        )

    async def get_market_activity_multiplier(self, symbol, timeframe):
        """Calculate market activity multiplier based on recent data"""
        try:
            # Get recent data from database for the symbol and timeframe
            recent_data = await self.db.get_recent_ohlcv_data(symbol, timeframe, limit=5)
            
            if not recent_data:
                # If no recent data, use default multiplier of 0.5 (50% of base thresholds)
                return 0.5
                
            # Calculate average volume and trades from recent data
            avg_volume = sum(float(candle['volume']) for candle in recent_data) / len(recent_data)
            avg_trades = sum(int(candle['trades']) for candle in recent_data) / len(recent_data)
            
            # Calculate time of day factor (reduce thresholds during off-hours)
            hour = datetime.now().hour
            time_factor = 1.0
            if 0 <= hour < 8:  # Reduced activity hours
                time_factor = 0.5
                
            # Calculate market activity score (normalize between 0.3 and 1.5)
            base_trades, base_volume = self.get_base_thresholds(timeframe)
            volume_ratio = min(avg_volume / base_volume, 3.0)  # Cap at 3x
            trades_ratio = min(avg_trades / base_trades, 3.0)  # Cap at 3x
            
            activity_multiplier = ((volume_ratio + trades_ratio) / 2) * time_factor
            
            # Ensure multiplier stays within reasonable bounds
            return max(0.3, min(activity_multiplier, 1.5))
            
        except Exception as e:
            self.logger.warning(f"Error calculating market multiplier: {e}")
            return 0.5  # Default to 50% of base thresholds on error

    async def get_dynamic_thresholds(self, symbol, timeframe):
        """Get dynamic thresholds based on market conditions"""
        base_trades, base_volume = self.get_base_thresholds(timeframe)
        
        # Get market activity multiplier
        multiplier = await self.get_market_activity_multiplier(symbol, timeframe)
        
        # Calculate final thresholds
        return {
            'min_trades': int(base_trades * multiplier),
            'min_volume': base_volume * multiplier
        }
    
    def set_quality_monitor(self, monitor):
        """Set the data quality monitor"""
        self.quality_monitor = monitor
    
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
                        try:
                            # Validate the ticker data before saving
                            if self.validate_ticker_data(data):
                                await self.db.save_ticker_data(data, 'binance')
                                self.logger.debug(f"Successfully collected ticker data for {symbol}")
                        except ValidationError as ve:
                            self.logger.error(f"Validation error for ticker {symbol}: {str(ve)}")
                            # Optionally store invalid data for analysis
                            await self.db.save_invalid_data(
                                symbol=symbol,
                                data_type='ticker',
                                timeframe=None,
                                data=data,
                                error_message=str(ve)
                            )
                    elif response.status == 429:
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
        
        self.current_timeframe = timeframe
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
                        self.logger.debug(
                            f"Raw klines data for {symbol} {timeframe}: "
                            f"Open: {data[0][1]}, High: {data[0][2]}, "
                            f"Low: {data[0][3]}, Close: {data[0][4]}, "
                            f"Volume: {data[0][5]}, Trades: {data[0][8]}"
                        )
                        try:
                            # Pass symbol to validation
                            if await self.validate_ohlcv_data(data[0], symbol):
                                kline_timestamp = datetime.fromtimestamp(data[0][0]/1000)
                                self.logger.debug(f"Kline timestamp for {timeframe}: {kline_timestamp}")
                                
                                await self.db.save_ohlcv_data(symbol, timeframe, data)
                                self.logger.debug(f"Successfully collected klines for {symbol} {timeframe}")
                        except ValidationError as ve:
                            self.logger.error(f"Validation error for {symbol} {timeframe}: {str(ve)}")
                            await self.db.save_invalid_data(
                                symbol=symbol,
                                data_type='klines',
                                timeframe=timeframe,
                                data=data,
                                error_message=str(ve)
                            )
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

    async def validate_ohlcv_data(self, data, symbol=None):
        """Validate OHLCV (klines) data before saving to database"""
        if not self.quality_monitor:
            raise RuntimeError("Quality monitor not initialized. Call set_quality_monitor first.")
        
        try:
            timestamp = int(data[0])
            open_price = float(data[1])
            high_price = float(data[2])
            low_price = float(data[3])
            close_price = float(data[4])
            volume = float(data[5])
            num_trades = int(data[8])

            timeframe = self.current_timeframe

            # Basic validations
            if any(price <= 0 for price in [open_price, high_price, low_price, close_price]):
                raise ValidationError("All prices must be positive")
            if high_price < low_price:
                raise ValidationError("High price cannot be lower than low price")
            if volume < 0:
                raise ValidationError("Volume cannot be negative")

            # Get dynamic thresholds
            thresholds = await self.get_dynamic_thresholds(symbol, timeframe)
            min_trade_count = thresholds['min_trades']
            min_volume_threshold = thresholds['min_volume']

            # Validate against dynamic thresholds
            if num_trades < min_trade_count:
                raise ValidationError(
                    f"Low trade count for {timeframe}: {num_trades} < {min_trade_count}"
                )
            
            if volume < min_volume_threshold:
                raise ValidationError(
                    f"Low volume for {timeframe}: {volume} < {min_volume_threshold}"
                )

            # Additional checks for larger timeframes
            if timeframe in ['5m', '15m', '1h', '4h', '1d']:
                # Price variance check
                price_range = high_price - low_price
                price_range_percent = (price_range / low_price) * 100

                if price_range_percent < 0.01:
                    raise ValidationError(
                        f"Suspicious price range for {timeframe}: {price_range_percent}%"
                    )

                # Check for identical OHLC values
                if len({open_price, high_price, low_price, close_price}) == 1:
                    raise ValidationError(
                        f"All OHLC prices identical in {timeframe} timeframe"
                    )

            # Initialize quality monitor if needed
            await self.initialize_quality_monitor(symbol, self.current_timeframe)
        
            # Add metrics to history
            self.quality_monitor.add_metrics(symbol, self.current_timeframe, {
                'volume': volume,
                'trades': num_trades
            })
            
            # Get validation results (now synchronous)
            is_valid, warnings, metrics = self.quality_monitor.validate_data(
                symbol, 
                self.current_timeframe,
                {'volume': volume, 'trades': num_trades}
            )
            
            # If we got a simple info message
            if len(warnings) == 1 and isinstance(warnings[0], str):
                self.logger.info(warnings[0])
                return True
            
            # Save metrics to database (moved from quality monitor)
            if metrics and metrics.get('baseline_complete'):
                # Get thresholds
                thresholds = self.quality_monitor.get_validation_thresholds(
                    symbol, 
                    self.current_timeframe
                )
            
            await self.db.save_validation_metrics(
                symbol,
                self.current_timeframe,
                metrics,
                thresholds
            )
            
            # Log warnings with severity
            for warning in warnings:
                if isinstance(warning, dict):
                    level = logging.ERROR if warning['severity'] == 'high' else logging.WARNING
                    self.logger.log(level, f"{symbol} {self.current_timeframe}: {warning['message']}")

            return is_valid
            
        except (IndexError, ValueError, TypeError) as e:
            raise ValidationError(f"Data format error: {str(e)}")

    def validate_ticker_data(self, data):
        """
        Validate ticker data before saving to database
        {
            "symbol": "BTCUSDT",
            "priceChange": "-94.99999800",
            "volume": "28.00000000",
            ...
        }
        """
        try:
            required_fields = ['symbol', 'lastPrice', 'volume', 'quoteVolume']
            
            # Check for required fields
            if not all(field in data for field in required_fields):
                raise ValidationError("Missing required fields in ticker data")

            # Price validation
            last_price = float(data['lastPrice'])
            if last_price <= 0:
                raise ValidationError("Price must be positive")

            # Volume validation
            volume = float(data['volume'])
            if volume < 0:
                raise ValidationError("Volume cannot be negative")

            # Symbol validation
            if not data['symbol'].endswith('USDT'):
                raise ValidationError("Invalid trading pair - must end with USDT")

            return True

        except (KeyError, ValueError, TypeError) as e:
            raise ValidationError(f"Ticker data format error: {str(e)}")
        
    async def initialize_quality_monitor(self, symbol: str, timeframe: str):
        """Initialize quality monitoring for a symbol/timeframe pair"""
        if not self.initialization_done[symbol][timeframe]:
            success = await self.quality_monitor.initialize_from_db(symbol, timeframe)
            self.initialization_done[symbol][timeframe] = success