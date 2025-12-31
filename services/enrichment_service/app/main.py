import asyncio
import logging
import signal
from app.consumers.bookmark_consumer import BookmarkEnrichmentConsumer
from app.config import get_settings
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()


class EnrichmentService:
    """Main enrichment service with FastAPI health endpoints and Kafka consumer."""

    def __init__(self):
        self.consumer = BookmarkEnrichmentConsumer()
        self._shutdown_initiated = False
        self.uvicorn_server = None

    def set_consumer_in_app_state(self):
        """Store consumer reference in FastAPI app state for health checks."""
        from app.api import app

        app.state.consumer = self.consumer

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

        # Store consumer reference in app state for health checks
        self.set_consumer_in_app_state()

        # Setup signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: loop.create_task(self.shutdown()))

        try:
            # Run both FastAPI server and consumer concurrently
            results = await asyncio.gather(
                self.run_uvicorn(), self.run_consumer(), return_exceptions=False
            )
            # Check if any task failed
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    task_name = ["FastAPI server", "Kafka consumer"][i]
                    logger.error(
                        f"{task_name} crashed with error: {result}", exc_info=result
                    )
                    # Re-raise to trigger shutdown
                    raise result

        except asyncio.CancelledError:
            logger.info("Graceful shutdown initiated via cancellation")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Graceful shutdown of both FastAPI and consumer."""
        if not self._shutdown_initiated:
            logger.info("Shutting down gracefully...")
            self._shutdown_initiated = True

            # Shutdown uvicorn server
            if self.uvicorn_server:
                self.uvicorn_server.should_exit = True

            # Shutdown consumer
            await self.consumer.stop()


if __name__ == "__main__":
    service = EnrichmentService()
    asyncio.run(service.start())
