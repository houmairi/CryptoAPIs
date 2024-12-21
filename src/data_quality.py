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
                
        # Track and log progress
        progress = len(self.metrics_history[symbol][timeframe]['volume'])
        if progress % 10 == 0:  # Log every 10 data points
            self.logger.info(
                f"Building baseline for {symbol} {timeframe}: "
                f"{progress}/{self.min_data_points} data points"
            )
                
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
            
    def get_validation_thresholds(self, symbol: str, timeframe: str) -> Dict:
        """Enhanced threshold calculation with more detail"""
        stats = self.statistics.get(symbol, {}).get(timeframe)
        
        if not stats:
            return None
            
        # Check if we have enough data points
        metrics = self.metrics_history[symbol][timeframe]
        has_baseline = len(metrics['volume']) >= self.min_data_points
        
        if not has_baseline:
            return {
                'baseline_complete': False,
                'volume': None,
                'trades': None
            }
            
        # Calculate thresholds
        min_volume = np.percentile(metrics['volume'], self.percentile_threshold)
        min_trades = np.percentile(metrics['trades'], self.percentile_threshold)
        
        # Apply time-based adjustments
        hour = datetime.now().hour
        if 0 <= hour < 8:  # During low activity hours
            min_volume *= 0.5
            min_trades *= 0.5
        
        return {
            'baseline_complete': True,
            'volume': min_volume,
            'trades': min_trades
        }

    def validate_data(self, symbol: str, timeframe: str, data: dict) -> Tuple[bool, List[str], Dict]:
        """Synchronous validation with detailed metrics"""
        warnings = []
        metrics = {}
        volume = float(data.get('volume', 0))
        trades = int(data.get('trades', 0))
        
        thresholds = self.get_validation_thresholds(symbol, timeframe)
        
        if not thresholds:
            return True, ["Initializing validation metrics..."], {}
            
        metrics.update({
            'volume': volume,
            'trades': trades,
            'baseline_complete': thresholds['baseline_complete']
        })
        
        if not thresholds['baseline_complete']:
            return True, ["Building baseline statistics..."], metrics
            
        # Calculate deficits and add to metrics
        if volume < thresholds['volume']:
            volume_deficit = ((thresholds['volume'] - volume) / thresholds['volume']) * 100
            metrics['volume_deficit'] = volume_deficit
            
            # More nuanced validation levels for volume
            if volume < thresholds['volume'] * 0.5:  # Below 50%
                severity = 'high'
            elif volume < thresholds['volume'] * 0.75:  # Below 75%
                severity = 'medium'
            else:  # Below 100%
                severity = 'low'
                
            warnings.append({
                'type': 'low_volume',
                'severity': severity,
                'message': f"Volume ({volume:.2f}) {volume_deficit:.1f}% below threshold ({thresholds['volume']:.2f})"
            })
        
        if trades < thresholds['trades']:
            trades_deficit = ((thresholds['trades'] - trades) / thresholds['trades']) * 100
            metrics['trades_deficit'] = trades_deficit
            
            # More nuanced validation levels for trades
            if trades < thresholds['trades'] * 0.5:  # Below 50%
                severity = 'high'
            elif trades < thresholds['trades'] * 0.75:  # Below 75%
                severity = 'medium'
            else:  # Below 100%
                severity = 'low'
                
            warnings.append({
                'type': 'low_trades',
                'severity': severity,
                'message': f"Trades ({trades}) {trades_deficit:.1f}% below threshold ({thresholds['trades']:.0f})"
            })
            
            is_valid = all(w['severity'] != 'high' for w in warnings if isinstance(w, dict))
        
            return is_valid, warnings, metrics
    
    def get_baseline_threshold(self, current_value: float) -> float:
        """More flexible threshold calculation"""
        # Start at 60% of original threshold, gradually increase
        if self.baseline_progress < 50:  # First 50 data points
            return current_value * 0.6
        elif self.baseline_progress < 100:  # Next 50 points
            return current_value * 0.8
        else:
            return current_value