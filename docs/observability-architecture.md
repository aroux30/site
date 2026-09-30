# Distributed Observability Architecture

```
                                  [ Browser / Client ]
                                          │
                               (W3C traceparent header)
                                          ▼
                                     [ Nginx ]
                                          │
                                          ▼
                                 [ FastAPI Backend ]
                                 ┌─────────────────┐
                                 │ OpenTelemetry   │
                                 │ SDK & Tracer    │
                                 └────────┬────────┘
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
          [ PostgreSQL / SQL ]       [ Redis Cache ]     [ External APIs ]
          - SQLAlchemy Hooks        - Hit/Miss Metrics  - Zarinpal / IDPay
          - Slow Query Log          - Latency Observer  - W3C Outbound Trace
                    │                     │                     │
                    └─────────────────────┼─────────────────────┘
                                          ▼
                             [ OpenTelemetry Collector ]
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    ▼                     ▼                     ▼
             [ Grafana Tempo ]     [ Grafana Loki ]      [ Prometheus ]
             (Distributed Traces)  (Structured Logs)    (Metrics & Latency)
                                          │
                                          ▼
                                  [ Grafana Dashboards ]
```

---

## 1. Trace Context Propagation Pipeline

Every inbound and outbound interaction complies with the W3C Trace Context specification:
- **traceparent:** `00-${traceId}-${spanId}-01`
- **trace_id:** 32-character hexadecimal identifier.
- **span_id:** 16-character hexadecimal identifier.
- **request_id:** UUIDv4 or client-supplied correlation token.

---

## 2. Telemetry Ingestion Stack

1. **Traces:** Ingested via OTLP HTTP (`http://otel-collector:4318/v1/traces`) and routed to Grafana Tempo.
2. **Logs:** Emitted as single-line JSON on stdout, collected by Docker log driver / Promtail and routed to Grafana Loki.
3. **Metrics:** Scraped by Prometheus from `/metrics` endpoint with counters, histograms, and gauges.

---

## 3. Latency Tiers & Alerting Thresholds

| Component | Normal | Warning | Critical / Alert |
| :--- | :--- | :--- | :--- |
| **API Endpoints** | < 300 ms | 300 - 700 ms | > 1400 ms (`slow_request`) |
| **PostgreSQL Queries** | < 25 ms | 25 - 100 ms | > 100 ms (`slow_query`) |
| **Redis Cache Ops** | < 5 ms | 5 - 20 ms | > 20 ms (`slow_redis`) |
| **External Payment APIs**| < 800 ms | 800 - 1500 ms | > 3000 ms (Timeout Alert) |
