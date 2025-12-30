import asyncio
import logging
import signal
from app.consumers.bookmark_consumer import BookmarkEnrichmentConsumer
from app.config import get_settings
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


class EnrichmentService:
    """Main enrichment service with FastAPI health endpoints and Kafka consumer."""

    def __init__(self):
        self.consumer = BookmarkEnrichmentConsumer()
        self.shutdown_event = asyncio.Event()
        self.uvicorn_server = None

    async def run_uvicorn(self):
        """Run FastAPI server using uvicorn."""
        config = uvicorn.Config(
            "app.api:app",
            host=settings.host,
            port=settings.port,
            log_level="info",
            access_log=False,  # Minimal logging for health checks
        )
        self.uvicorn_server = uvicorn.Server(config)
        await self.uvicorn_server.serve()

    async def run_consumer(self):
        """Run Kafka consumer."""
        try:
            await self.consumer.start()
            await self.consumer.consume_and_enrich()
        except asyncio.CancelledError:
            logger.info("Consumer cancelled")
        finally:
            await self.consumer.stop()

    async def start(self):
        """Start both FastAPI server and Kafka consumer concurrently."""
        logger.info(f"Starting {settings.app_name} v{settings.app_version}")

        # Setup signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(
                sig,
                lambda: asyncio.create_task(self.shutdown())
            )

        try:
            # Run both FastAPI server and consumer concurrently
            await asyncio.gather(
                self.run_uvicorn(),
                self.run_consumer(),
                return_exceptions=True
            )
        except asyncio.CancelledError:
            logger.info("Service cancelled")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown of both FastAPI and consumer."""
        if not self.shutdown_event.is_set():
            logger.info("Shutting down gracefully...")
            self.shutdown_event.set()

            # Shutdown uvicorn server
            if self.uvicorn_server:
                self.uvicorn_server.should_exit = True

            # Shutdown consumer
            await self.consumer.stop()


if __name__ == "__main__":
    service = EnrichmentService()
    asyncio.run(service.start())
