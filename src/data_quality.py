import numpy as np
from collections import defaultdict
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple

class DataQualityMonitor:
    def __init__(self, db_handler):
        self.db = db_handler
        self.logger = logging.getLogger(__name__)
        self.metrics_history = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        self.statistics = defaultdict(dict)
        self.initialization_period = timedelta(days=7)  # Adjust as needed
        self.percentile_threshold = 1  # Use 1st percentile instead of 3 std deviations
        self.min_data_points = 100  # Minimum required data points for validation
        
    async def initialize_from_db(self, symbol: str, timeframe: str):
        """Load historical data from database to initialize metrics"""
        try:
            # Get last week's data
            start_date = datetime.now() - self.initialization_period
            historical_data = await self.db.get_ohlcv_data(
                symbol, 
                timeframe,
                start_date=start_date
            )
            
            if not historical_data:
                self.logger.warning(f"No historical data found for {symbol} {timeframe}")
                return False
                
            # Initialize metrics
            for candle in historical_data:
                self.add_metrics(symbol, timeframe, {
                    'volume': float(candle['volume']),
                    'trades': int(candle['num_trades'])
                })
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error initializing metrics: {e}")
            return False
            
    def add_metrics(self, symbol: str, timeframe: str, data: dict):
        """Add new metrics to history"""
        self.metrics_history[symbol][timeframe]['volume'].append(data['volume'])
        self.metrics_history[symbol][timeframe]['trades'].append(data['trades'])
        
        # Keep only last week's worth of data
        max_history = 7 * 24 * 60  # 1 week of minute data
        for metric in ['volume', 'trades']:
            if len(self.metrics_history[symbol][timeframe][metric]) > max_history:
                self.metrics_history[symbol][timeframe][metric].pop(0)
                
        self._update_statistics(symbol, timeframe)
        
    def _update_statistics(self, symbol: str, timeframe: str):
        """Update statistical measures for the symbol/timeframe"""
        try:
            metrics = self.metrics_history[symbol][timeframe]
            
            if not metrics['volume'] or not metrics['trades']:
                return
                
            # Calculate statistics for volume and trades
            self.statistics[symbol][timeframe] = {
                'volume': {
                    'mean': np.mean(metrics['volume']),
                    'std': np.std(metrics['volume']),
                    'min': np.percentile(metrics['volume'], 5),
                    'max': np.percentile(metrics['volume'], 95)
                },
                'trades': {
                    'mean': np.mean(metrics['trades']),
                    'std': np.std(metrics['trades']),
                    'min': np.percentile(metrics['trades'], 5),
                    'max': np.percentile(metrics['trades'], 95)
                }
            }
        except Exception as e:
            self.logger.error(f"Error updating statistics: {e}")
            
    def get_validation_thresholds(self, symbol: str, timeframe: str) -> Tuple[float, float]:
        """Get dynamic thresholds based on historical data"""
        stats = self.statistics.get(symbol, {}).get(timeframe)
        
        if not stats:
            return None, None
            
        # Check if we have enough data points
        if len(self.metrics_history[symbol][timeframe]['volume']) < self.min_data_points:
            return None, None
            
        # Use percentile instead of standard deviation
        min_volume = np.percentile(self.metrics_history[symbol][timeframe]['volume'], 
                                 self.percentile_threshold)
        min_trades = np.percentile(self.metrics_history[symbol][timeframe]['trades'], 
                                 self.percentile_threshold)
        
        # Add time-based adjustment
        hour = datetime.now().hour
        if 0 <= hour < 8:  # During low activity hours
            min_volume *= 0.5
            min_trades *= 0.5
            
        return min_volume, min_trades
        
    def validate_data(self, symbol: str, timeframe: str, data: dict) -> Tuple[bool, List[str], Dict]:
        """Enhanced validation with severity levels"""
        warnings = []
        metrics = {}
        volume = float(data.get('volume', 0))
        trades = int(data.get('trades', 0))
        
        min_volume, min_trades = self.get_validation_thresholds(symbol, timeframe)
        
        if min_volume is None or min_trades is None:
            return True, ["Building baseline statistics..."], {}
            
        # Calculate how far below threshold we are (as percentage)
        if volume < min_volume:
            volume_deficit = ((min_volume - volume) / min_volume) * 100
            severity = 'high' if volume_deficit > 50 else 'medium'
            metrics['volume_deficit'] = volume_deficit
            warnings.append({
                'type': 'low_volume',
                'severity': severity,
                'message': f"Volume ({volume:.2f}) {volume_deficit:.1f}% below historical minimum ({min_volume:.2f})"
            })
            
        if trades < min_trades:
            trades_deficit = ((min_trades - trades) / min_trades) * 100
            severity = 'high' if trades_deficit > 50 else 'medium'
            metrics['trades_deficit'] = trades_deficit
            warnings.append({
                'type': 'low_trades',
                'severity': severity,
                'message': f"Trade count ({trades}) {trades_deficit:.1f}% below historical minimum ({min_trades:.0f})"
            })
            
        # Consider data valid if deficits are not too severe
        is_valid = all(w['severity'] != 'high' for w in warnings)
        
        return is_valid, warnings, metrics