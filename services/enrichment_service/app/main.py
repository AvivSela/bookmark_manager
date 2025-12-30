import asyncio
import logging
import signal
from app.consumers.bookmark_consumer import BookmarkEnrichmentConsumer
from app.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


class EnrichmentService:
    """Main enrichment service."""

    def __init__(self):
        self.consumer = BookmarkEnrichmentConsumer()
        self.shutdown_event = asyncio.Event()

    async def start(self):
        """Start the service."""
        logger.info(f"Starting {settings.app_name} v{settings.app_version}")

        # Setup signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(
                sig,
                lambda: asyncio.create_task(self.shutdown())
            )

        try:
            await self.consumer.start()
            await self.consumer.consume_and_enrich()
        except asyncio.CancelledError:
            logger.info("Service cancelled")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown."""
        if not self.shutdown_event.is_set():
            logger.info("Shutting down gracefully...")
            self.shutdown_event.set()
            await self.consumer.stop()


if __name__ == "__main__":
    service = EnrichmentService()
    asyncio.run(service.start())
