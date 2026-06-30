from chromadb.telemetry.product import ProductTelemetryClient, ProductTelemetryEvent
from overrides import override


class NoOpProductTelemetryClient(ProductTelemetryClient):
    """Disable Chroma product telemetry without invoking a network client."""

    @override
    def capture(self, event: ProductTelemetryEvent) -> None:
        return None
