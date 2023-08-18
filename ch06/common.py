from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes
from local_machine_resource_detector import LocalMachineResourceDetector

from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.metrics import get_meter_provider, set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    ConsoleMetricExporter,
    PeriodicExportingMetricReader,
)

from opentelemetry.sdk.metrics._internal.measurement import Measurement

from opentelemetry.sdk._logs.export import ConsoleLogExporter, BatchLogRecordProcessor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry._logs import set_logger_provider

from flask import request
import resource
import logging

def configure_meter(name, version):
    exporter = ConsoleMetricExporter()
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=5000)
    local_resource = LocalMachineResourceDetector().detect()
    resource = local_resource.merge(Resource.create({
        ResourceAttributes.SERVICE_NAME: name,
        ResourceAttributes.SERVICE_VERSION: version,
    }))

    provider = MeterProvider(metric_readers=[reader],resource=resource)
    set_meter_provider(provider)
    schema_url = "https://opentelemetry.io/schemas/1.9.0"
    return get_meter_provider().get_meter(
        name=name,
        version=version,
        schema_url=schema_url,
    )

def configure_tracer(name, version):
    exporter = ConsoleSpanExporter()
    span_processor = BatchSpanProcessor(exporter)
    
    local_resource = LocalMachineResourceDetector().detect()
    resource = local_resource.merge(
        Resource.create(
            {
                ResourceAttributes.SERVICE_NAME: name,
                ResourceAttributes.SERVICE_VERSION: version,
            }
        )
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(span_processor)
    trace.set_tracer_provider(provider)
    return trace.get_tracer(name, version)

def set_span_attributes_from_flask():
    span = trace.get_current_span()
    span.set_attributes({
        SpanAttributes.HTTP_FLAVOR: request.environ.get("SERVER_PROTOCOL"),
        SpanAttributes.HTTP_METHOD: request.method,
        SpanAttributes.HTTP_USER_AGENT: str(request.user_agent),
        SpanAttributes.HTTP_HOST: request.host,
        SpanAttributes.HTTP_SCHEME: request.scheme,
        SpanAttributes.HTTP_TARGET: request.path,
        SpanAttributes.HTTP_CLIENT_IP: request.remote_addr,
    })

def record_max_rss_callback():
    yield Measurement(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)

def start_recording_memory_metrics(meter):
    meter.create_observable_gauge(
        callbacks=[record_max_rss_callback],
        name="maxrss",
        unit="bytes",
        description="Max resident set size",
    )

def configure_logger(name, version):
    provider = LoggerProvider(resource=Resource.create())
    set_logger_provider(provider)
    exporter = ConsoleLogExporter()
    provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    handler = LoggingHandler()
    logger.addHandler(handler)
    return logger