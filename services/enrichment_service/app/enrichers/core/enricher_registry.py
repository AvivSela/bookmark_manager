"""Central registry for enricher discovery and management."""

import logging
from typing import Dict, List, Type

from app.enrichers.core.base_enricher import BaseEnricher
from app.enrichers.core.resource_types import ResourceType

logger = logging.getLogger(__name__)


class EnricherRegistry:
    """Central registry for all available enrichers."""

    def __init__(self):
        self._enrichers: Dict[str, Type[BaseEnricher]] = {}

    def register(self, enricher_class: Type[BaseEnricher]) -> Type[BaseEnricher]:
        """
        Register an enricher class.

        Can be used as a decorator:
            @registry.register
            class MyEnricher(BaseEnricher):
                ...

        Args:
            enricher_class: Enricher class to register

        Returns:
            The enricher class (for decorator use)
        """
        # Instantiate temporarily to get the name
        try:
            temp_instance = enricher_class()
            name = temp_instance.name
            self._enrichers[name] = enricher_class
            logger.info("Registered enricher: %s", name)
        except Exception as e:
            logger.error(
                "Failed to register enricher %s: %s", enricher_class.__name__, e
            )
            raise

        return enricher_class

    def get_enricher(self, name: str, config: Dict = None) -> BaseEnricher:
        """
        Instantiate an enricher by name.

        Args:
            name: Enricher name
            config: Optional configuration dict

        Returns:
            Instantiated enricher

        Raises:
            ValueError: If enricher not found
        """
        if name not in self._enrichers:
            raise ValueError(
                f"Enricher '{name}' not registered. Available: {list(self._enrichers.keys())}"
            )

        return self._enrichers[name](config)

    def get_applicable_enrichers(
        self,
        resource_type: ResourceType,
        enabled_enrichers: List[str],
        config: Dict = None,
    ) -> List[BaseEnricher]:
        """
        Get all enrichers applicable to a resource type.

        Args:
            resource_type: Detected resource type
            enabled_enrichers: List of enricher names enabled in config
            config: Optional configuration dict for enrichers

        Returns:
            List of instantiated enrichers
        """
        enrichers = []

        for name in enabled_enrichers:
            if name not in self._enrichers:
                logger.warning(
                    f"Enricher '{name}' is enabled but not registered. Skipping."
                )
                continue

            try:
                instance = self.get_enricher(name, config)
                if instance.is_applicable(resource_type):
                    enrichers.append(instance)
                    logger.debug(
                        f"Enricher '{name}' is applicable for type {resource_type}"
                    )
                else:
                    logger.debug(
                        f"Enricher '{name}' is not applicable for type {resource_type}"
                    )
            except Exception as e:
                logger.error("Failed to instantiate enricher '%s': %s", name, e)

        return enrichers

    def list_enrichers(self) -> List[str]:
        """
        Get list of all registered enricher names.

        Returns:
            List of enricher names
        """
        return list(self._enrichers.keys())


# Global registry instance
registry = EnricherRegistry()
