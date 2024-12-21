import asyncio
from src.collector import CryptoDataCollector
from config import config
import logging
import signal
import sys
import platform

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CryptoDataService:
    def __init__(self):
        """Initialize the service with configuration"""
        self.running = False
        self.collector = CryptoDataCollector(config)
        
    async def start(self):
        self.running = True
        logger.info("Starting Crypto Data Service")
        
        try:
            # Set up platform-specific signal handling
            if platform.system() != 'Windows':
                # Unix-like systems
                for sig in (signal.SIGTERM, signal.SIGINT):
                    asyncio.get_event_loop().add_signal_handler(
                        sig,
                        lambda s=sig: self.handle_shutdown(s)
                    )
            else:
                # Windows - use simple signal handlers
                signal.signal(signal.SIGINT, lambda s, f: self.handle_shutdown())
                signal.signal(signal.SIGTERM, lambda s, f: self.handle_shutdown())
            
            # Start all collection tasks
            await self.collector.start_collection()
            
            # Keep the service running
            while self.running:
                try:
                    await asyncio.sleep(1)
                except asyncio.CancelledError:
                    break
                
        except Exception as e:
            logger.error(f"Service error: {e}")
        finally:
            await self.shutdown()
            
    def handle_shutdown(self, sig=None):
        """Handle shutdown signals"""
        if sig:
            logger.info(f"Received signal {sig.name}")
        asyncio.create_task(self.shutdown())

    async def shutdown(self):
        """Shutdown the service gracefully"""
        if self.running:
            logger.info("Shutting down service...")
            self.running = False
            
            try:
                # Stop collection tasks
                await self.collector.stop_collection()
                
                # Cancel remaining tasks
                tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
                if tasks:
                    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                
            except Exception as e:
                logger.error(f"Error during shutdown: {e}")
            finally:
                logger.info("Service shutdown complete")

def main():
    service = CryptoDataService()
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        logger.info("Service shutdown complete")

if __name__ == "__main__":
    main()