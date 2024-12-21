import asyncio
from src.collector import CryptoDataCollector
from config import CONFIG

async def main():
    collector = CryptoDataCollector(CONFIG)
    await collector.continuous_collection()

if __name__ == "__main__":
    asyncio.run(main())