import asyncio
from src.collector import CryptoDataCollector
from src.data_quality import DataQualityMonitor
from config import config
import logging
import signal
import sys
import platform

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CryptoDataService:
    def __init__(self, debug_mode=False):
        """Initialize the service with configuration"""
        self.running = False
        self.debug_mode = debug_mode
        self.collector = CryptoDataCollector(config)
        # Initialize DataQualityMonitor with debug mode option
        self.monitor = DataQualityMonitor(self.collector.db, debug_quick_baseline=debug_mode)
        # Pass monitor to collector
        self.collector.set_quality_monitor(self.monitor)
        
    async def start(self):
        self.running = True
        logger.info(f"Starting Crypto Data Service in {'debug' if self.debug_mode else 'normal'} mode")
        
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
    # You can enable debug mode by passing an argument
    debug_mode = '--debug' in sys.argv
    service = CryptoDataService(debug_mode=debug_mode)
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        logger.info("Service shutdown complete")

if __name__ == "__main__":
    main()