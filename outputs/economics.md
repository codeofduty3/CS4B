# Unit economics

| Line | Ask the Panel |
|---|---|
| Cost per completed task | $0.0012 per answerable task (estimated $0.01065 for all ten; local replay costs $0.00) |
| Latency | 37 ms median and 73 ms p95 for local replay across ten questions |
| Human time saved | 3.33 hours and $400 for ten tasks at 20 minutes and $120/hour (range: 1.67–6.67 hours and $200–$800) |
| Quality | 9/10 questions answered, 1/10 correctly declined, 3 invalid SQL attempts repaired, 0 final failures |
| Cost of failure | $0.00227 estimated for the 3 repaired attempts, with 0 timeouts and 0 incorrect final answers |

Costs use the Gemini 3.8 Flash standard rates in `params.yaml` and estimated token counts derived from request and response sizes. The local replay timings exclude network and model inference time.
