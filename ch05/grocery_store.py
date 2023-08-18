from flask import Flask, request
from opentelemetry import trace
from opentelemetry.semconv.trace import HttpFlavorValues, SpanAttributes
from opentelemetry.trace import SpanKind
from common import configure_meter, configure_tracer, set_span_attributes_from_flask
from opentelemetry import context

from opentelemetry.propagate import extract, inject, set_global_textmap
from opentelemetry.propagators.b3 import B3MultiFormat
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation import tracecontext

import requests, time

set_global_textmap(CompositePropagator([tracecontext.TraceContextTextMapPropagator(), B3MultiFormat()]))

tracer = configure_tracer("0.1.2", "grocery-store")
meter = configure_meter("grocery-store", "0.1.2")

request_counter = meter.create_counter(
    name="requests",
    unit="request",
    description="Total number of requests",
)

total_duration_histo = meter.create_histogram(
    name="duration",
    description="request duration",
    unit="ms",
)

upstream_duration_histo = meter.create_histogram(
    name="upstream_request_duration",
    description="duration of upstream requests",
    unit="ms",
)

concurrent_counter = meter.create_up_down_counter(
    name="concurrent_requests",
    unit="request",
    description="Total number of concurrent requests",
)

app = Flask(__name__)


@app.before_request
def before_request_func():
    token = context.attach(extract(request.headers))
    request_counter.add(1)
    request.environ["context_token"] = token
    request.environ["start_time"] = time.time_ns()
    concurrent_counter.add(1)

@app.after_request
def after_request_func(response):
    request_counter.add(1, {"code": response.status_code})
    duration = (time.time_ns() - request.environ["start_time"]) / 1e6
    total_duration_histo.record(duration)
    concurrent_counter.add(-1)
    return response

@app.teardown_request
def teardown_request_func(err):
    token = request.environ.get("context_token", None)
    if token:
        context.detach(token)

@app.route("/")
@tracer.start_as_current_span("welcome", kind=SpanKind.SERVER)
def welcome():
    set_span_attributes_from_flask()
    return "Welcome to the grocery store!"

@app.route("/products")
@tracer.start_as_current_span("/products", kind=SpanKind.SERVER)
def products():
    set_span_attributes_from_flask()
    with tracer.start_as_current_span("inventory request") as span:
        url = "http://localhost:5001/inventory"
        span.set_attributes({
            SpanAttributes.HTTP_METHOD: "GET",
            SpanAttributes.HTTP_FLAVOR: str(HttpFlavorValues.HTTP_1_1),
            SpanAttributes.HTTP_URL: url,
            SpanAttributes.NET_PEER_IP: "127.0.0.1",
        })
        headers = {}
        inject(headers)
        
        start = time.time_ns()
        resp = requests.get(url, headers=headers)
        duration = (time.time_ns() - start) / 1e6
        upstream_duration_histo.record(duration)
                               
        return resp.text

if __name__ == "__main__":
    app.run()