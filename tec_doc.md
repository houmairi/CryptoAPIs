# CryptoAPIs Technical Documentation 21.12.2024

## Project Status: Prototype Phase

This document outlines the current state, architecture, and development priorities of the CryptoAPIs project, a cryptocurrency data collection system.

## Core Architecture

### Data Collection System

The system implements a concurrent data collection mechanism using Python's asyncio framework, with the following key components:

- **Main Service (`CryptoDataService`)**: Handles lifecycle management and graceful shutdown
- **Data Collectors**: Implementations for Binance and CoinGecko APIs
- **Database Layer**: PostgreSQL with asyncio-compatible operations
- **Data Quality Monitor**: Real-time validation and quality metrics tracking

### Current Implementation Status

#### Working Features
- Minute-aligned price tick collection
- Basic OHLCV data collection
- PostgreSQL schema with proper indexing
- Graceful shutdown handling
- Platform-specific signal handling (Windows/Unix)
- Data quality monitoring with dynamic thresholds
- Debug mode for rapid development testing
- Type-safe database operations

#### Recent Improvements
1. Data Quality System
   - Implemented baseline metrics establishment
   - Added debug mode for faster testing (3 vs 100 data points)
   - Fixed numpy type conversions in database operations
   - Added proper baseline completion tracking
   - Implemented severity-based warning system

2. System Integration
   - Integrated DataQualityMonitor with main service
   - Fixed database handler references
   - Improved error logging and tracking

#### Development Priorities
1. OHLCV Data Collection Refinement
   - Further timeframe alignment optimization for 15min, 1h, 4h intervals
   - Enhanced validation of collection completeness
   - Timestamp synchronization improvements

2. Data Quality System Enhancement
   - Market cap based threshold adjustments
   - More granular time-of-day adaptations
   - Pair-specific validation rules

## Technical Deep Dive

### Database Schema

The database design focuses on four main entities:

1. **coins**: Base cryptocurrency information
   - Primary identifiers
   - Exchange-specific IDs
   - Basic metadata

2. **price_ticks**: High-frequency data
   - Minute-aligned timestamps
   - Price and volume data
   - Source tracking

3. **ohlcv_data**: Aggregated candlestick data
   - Multiple timeframe support
   - Trade count tracking
   - Unique constraints per (coin, timestamp, timeframe)

4. **validation_metrics**: Data quality tracking
   - Volume and trade thresholds
   - Deficit calculations
   - Baseline completion tracking
   - Severity-based warning history

### Data Quality Monitoring

The `DataQualityMonitor` class implements a sophisticated validation system:

```python
# Key thresholds and parameters
initialization_period = 7 days
percentile_threshold = 1st percentile
min_data_points = 100  # 3 in debug mode
```

Validation Process:
1. Baseline Establishment
   - Historical data collection
   - Automatic completion tracking
   - Debug mode support for rapid testing

2. Dynamic Validation
   - Statistical baseline comparison
   - Multi-level severity warnings
   - Time-aware threshold adjustments

3. Quality Metrics
   - Volume validation with dynamic thresholds
   - Trade count monitoring
   - Market activity tracking

Current Default Thresholds:
```python
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
```

### Error Handling

The system implements a multi-layered error handling approach:

1. **Collection Level**
   - API-specific error catching
   - Rate limit management
   - Connection error recovery

2. **Service Level**
   - Graceful shutdown handling
   - Task cancellation management
   - Platform-specific signal handling

3. **Data Quality Level**
   - Invalid data logging
   - Severity-based warning system
   - Type-safe database operations

## Development Guidelines

### Current Development Focus

1. Data Quality Refinement
   - Fine-tune threshold values based on market data
   - Implement market cap based adjustments
   - Enhance warning system granularity

2. System Testing
   - Extended debug mode testing
   - Long-running stability validation
   - Edge case handling verification

3. Performance Optimization
   - Database operation efficiency
   - Memory usage optimization
   - Collection timing precision

### Code Style and Practices

1. Async/Await Usage
   - Consistent use of asyncio
   - Proper task management
   - Error propagation

2. Error Handling
   - Specific exception types
   - Detailed error logging
   - Graceful degradation

3. Data Validation
   - Type-safe operations
   - Multi-level quality checks
   - Comprehensive error tracking

## Deployment Considerations (Future)

While still in prototype phase, the following should be considered for future deployment:

1. **Infrastructure Requirements**
   - PostgreSQL 12+
   - Python 3.8+
   - Sufficient storage for tick data
   - Network stability for API access
   - Memory for quality metrics tracking

2. **Monitoring Needs**
   - Data collection completeness
   - API rate limit usage
   - System resource usage
   - Data quality metrics
   - Warning pattern analysis

3. **Backup Strategy**
   - Database backup planning
   - Data verification procedures
   - Recovery testing
   - Quality metrics preservation

## Next Steps

1. Fine-tune quality thresholds based on collected data
2. Implement market cap based validation rules
3. Enhance time-of-day threshold adjustments
4. Plan VPS deployment architecture
5. Develop monitoring dashboard for quality metrics