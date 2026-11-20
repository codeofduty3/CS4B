# Unit economics

| Line | Ask the Panel |
|---|---|
| Cost per completed task | $0.00060 per answerable task (estimated $0.00544 for all ten; local replay costs $0.00) |
| Latency | 18 ms median and 56 ms p95 for local replay across ten questions |
| Human time saved | 3.33 hours and $400 for ten tasks at 20 minutes and $120/hour (range: 1.67–6.67 hours and $200–$800) |
| Quality | 9/10 questions answered, 1/10 correctly declined, 3 failed SQL attempts repaired in earlier traces, 0 repairs and 0 final failures in the final run |
| Cost of failure | $0.00227 model cost from the three failed attempts in the earlier traces; the final replay incurred $0.00 extra failure cost |

Costs use the Gemini 3.5 Flash-Lite Standard paid-tier rates in `params.yaml` ($0.30 input and $2.50 output per million tokens) and token counts from Gemini's usage metadata. Gemini's free tier is $0 for this model, so the recorded requests incurred no charge on the free tier. The local replay timings exclude network and model inference time.
