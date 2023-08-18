from opentelemetry.sdk._logs.export import ConsoleLogExporter, BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk._logs import LoggerProvider, LogRecord, LoggingHandler
from opentelemetry._logs import (
    get_logger_provider,
    set_logger_provider,
)
from opentelemetry._logs.severity import SeverityNumber

import time
import logging

def configure_log_emitter_provider():
    provider = LoggerProvider(resource=Resource.create())
    set_logger_provider(provider)
    exporter = ConsoleLogExporter()
    provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

if __name__ == "__main__":
    configure_log_emitter_provider()
    log_emitter = get_logger_provider().get_logger("shopper", "0.1.2")
    log_emitter.emit(LogRecord(
        timestamp=time.time_ns(),
        body="first log line",
        severity_number=SeverityNumber.INFO,
    ))

    logger = logging.getLogger(__file__)
    logger.setLevel(logging.DEBUG)
    handler = LoggingHandler()
    logger.addHandler(handler)
    logger.warning("second log line", extra={"key1": "val1"})
    logger.info("second log line")