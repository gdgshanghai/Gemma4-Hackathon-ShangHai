# Shared OpenTelemetry instrumentation — placeholder.
#
# Common tracing, metrics, and logging utilities for all services.
#
# Key SLIs:
#   - Closed-loop round-trip latency (sense → infer → decide → stimulate)
#   - Edge→Cloud upload throughput
#   - Inference request latency (P50, P95, P99)
#   - Safety-guard rejection rate
#
# Exporters: OTLP gRPC to cluster-local collector.
