import requests
import time
from pprint import pprint

def test_coingecko_endpoints():
    base_url = "https://api.coingecko.com/api/v3"
    
    # Test different endpoints
    endpoints = {
        "price": "/simple/price?ids=bitcoin&vs_currencies=usd",
        "market_data": "/coins/bitcoin?localization=false&tickers=false&community_data=false&developer_data=false",
        "historical": "/coins/bitcoin/market_chart?vs_currency=usd&days=1&interval=hourly"
    }
    
    results = {}
    for name, endpoint in endpoints.items():
        try:
            response = requests.get(f"{base_url}{endpoint}")
            response.raise_for_status()
            results[name] = response.json()
            time.sleep(1.5)  # Respect rate limits
        except requests.exceptions.RequestException as e:
            results[name] = f"Error: {str(e)}"
    
    return results

# Run the test
api_results = test_coingecko_endpoints()
pprint(api_results)