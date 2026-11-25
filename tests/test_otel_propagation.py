"""Tests for W3C trace context propagation across the QStash boundary.

When OpenTelemetry is configured, each outbound call to QStash must carry
the current ``traceparent`` as ``Upstash-Forward-traceparent`` so QStash
forwards it (stripped of the prefix) to the workflow destination — making
the next step invocation a child of the current trace rather than a new
root. Without this, multi-step workflows fragment into N disjoint root
traces in any tracing UI (Tempo, Jaeger, Datadog, etc.).

The injection is wired through ``_get_headers``, which is the single
header-building chokepoint for every QStash publish in the library
(initial trigger, step submissions, third-party-call steps, all of them).
So a single integration test against ``_get_headers`` covers every
outbound path.

OpenTelemetry is a soft dependency: when it isn't installed, the
injection helper is a no-op and the library behaves exactly as before.
"""

import pytest

from upstash_workflow.workflow_requests import _get_headers, _inject_otel_context


@pytest.fixture
def otel_traced():
    """Configure an in-memory OTel tracer, yield a tracer that produces
    real traceparent values, then tear down so other tests are unaffected.
    """
    # Soft-import OTel so the test file can be loaded even when the
    # opentelemetry package is unavailable (in which case the parametrize
    # below sees zero ids and the test is skipped, matching the soft-dep
    # contract).
    pytest.importorskip("opentelemetry")
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    previous_provider = trace.get_tracer_provider()
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    try:
        tracer = trace.get_tracer("test")
        yield tracer
    finally:
        # Best-effort teardown — restoring an arbitrary previous provider
        # isn't always possible (the API doesn't expose a setter for the
        # NoOpTracerProvider), but tests don't rely on the previous state.
        del previous_provider


def test_get_headers_injects_traceparent_when_span_is_active(otel_traced) -> None:
    """With an active OTel span, ``_get_headers`` writes the current
    ``traceparent`` as ``Upstash-Forward-traceparent`` so QStash can
    forward it to the next step destination."""
    with otel_traced.start_as_current_span("publisher"):
        response = _get_headers(
            init_header_value="true",
            workflow_run_id="wfr-test-id",
            workflow_url="https://example.com",
        )

    assert "Upstash-Forward-traceparent" in response.headers, (
        "Without this header, QStash delivers the next step invocation with "
        "no parent context and the trace fragments into disjoint roots."
    )
    # W3C traceparent shape: ``00-<32 hex trace_id>-<16 hex span_id>-<2 hex flags>``
    traceparent = response.headers["Upstash-Forward-traceparent"]
    parts = traceparent.split("-")
    assert len(parts) == 4, f"malformed traceparent: {traceparent!r}"
    assert parts[0] == "00", "expected W3C version 00"
    assert len(parts[1]) == 32, "expected 32-hex trace_id"
    assert len(parts[2]) == 16, "expected 16-hex span_id"


def test_get_headers_omits_traceparent_when_no_span_is_active(otel_traced) -> None:
    """Without an active span, OTel's propagator writes nothing — and
    we don't fabricate a header."""
    response = _get_headers(
        init_header_value="true",
        workflow_run_id="wfr-test-id",
        workflow_url="https://example.com",
    )
    assert "Upstash-Forward-traceparent" not in response.headers


def test_inject_otel_context_is_noop_when_opentelemetry_missing(monkeypatch) -> None:
    """The injection helper soft-imports ``opentelemetry`` so the library
    has no runtime cost for users that don't run OTel. Simulate the
    package being absent by making the import raise."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("opentelemetry"):
            raise ImportError("simulated: opentelemetry not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    headers = {"X-Existing": "preserved"}
    _inject_otel_context(headers)  # must not raise
    assert headers == {"X-Existing": "preserved"}, (
        "soft-dependency contract: when opentelemetry is missing, the "
        "helper is a pure no-op and leaves the headers dict unchanged"
    )
