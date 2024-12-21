import requests
import time
from pprint import pprint

def test_binance_endpoints():
    base_url = "https://api.binance.com/api/v3"
    
    endpoints = {
        "price": "/ticker/price?symbol=BTCUSDT",
        "24h_stats": "/ticker/24hr?symbol=BTCUSDT",
        "recent_trades": "/trades?symbol=BTCUSDT&limit=5"
    }
    
    results = {}
    for name, endpoint in endpoints.items():
        try:
            response = requests.get(f"{base_url}{endpoint}")
            response.raise_for_status()
            results[name] = response.json()
            time.sleep(1)
        except requests.exceptions.RequestException as e:
            results[name] = f"Error: {str(e)}"
    
    return results

binance_results = test_binance_endpoints()
pprint(binance_results)