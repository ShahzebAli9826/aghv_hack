# TinyFish contract used by `app/intel`

Accessed 2026-10-16. Primary sources were the OpenAPI specs at `https://agent.tinyfish.ai/v1/openapi/{main,fetch,search,research}` (downloaded and read field by field) and the docs pages `docs.tinyfish.ai/{key-concepts/runs, key-concepts/endpoints, key-concepts/structured-output, webhooks, error-codes, monitor, monitor/api-reference}`, plus `www.tinyfish.ai/pricing`.

Every request sends the header `X-API-Key: <TINYFISH_API_KEY>` (OpenAPI `securitySchemes.ApiKeyAuth`, all four specs).

## Verified endpoints

| Use in Aegis | Method and URL | Request fields we send | Response fields we read | Normalizer |
|---|---|---|---|---|
| Agent, async | `POST https://agent.tinyfish.ai/v1/automation/run-async` | `url`, `goal`, `output_schema`, `webhook_url` (optional), `agent_config.max_steps` (1 to 500) | `run_id`, `error{code,message}` | `start_agent_run` |
| Agent, streamed (F1) | `POST https://agent.tinyfish.ai/v1/automation/run-sse` | same as run-async | events `STARTED{run_id}`, `STREAMING_URL{run_id,streaming_url}`, `PROGRESS`, `HEARTBEAT`, `COMPLETE{status,result}` (also `TF_API_RESULT`, ignored) | `_normalize_sse_line_block` |
| Run status | `GET https://agent.tinyfish.ai/v1/runs/{id}?screenshots=none&html=none` | | `run_id`, `status` (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED), `result`, `error{code,message,category,retry_after,help_url,profile_hint}`, `num_of_steps`, `started_at`, `finished_at`, `streaming_url`, `profile_hint{reason: auth_wall or bot_challenge}` | `_normalize_run` |
| Cancel | `POST https://agent.tinyfish.ai/v1/runs/{id}/cancel` | | `status` (CANCELLED, COMPLETED, FAILED) | `cancel_run` |
| Search | `GET https://api.search.tinyfish.ai/` | query params `query`, `include_domains`, `domain_type` (web, news, research_paper), `recency_minutes` | `results[]{position,site_name,title,snippet,url,date}` | `_normalize_search` |
| Fetch | `POST https://api.fetch.tinyfish.ai/` | `urls[]`, `format` (markdown), `purpose` | `results[]{url,final_url,title,text,published_date,language}`, `errors[]{url,error,status}` | `_normalize_fetch` |
| Research (F5) | `POST https://agent.tinyfish.ai/v1/automation/run-research-async` | `query`, `domain_filter{mode: include, domains[]}`, `recency_minutes` | `research_run_id` | `start_research` |
| Research result | `GET https://agent.tinyfish.ai/v1/research-run/{id}` | | `status` (QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED, TIMED_OUT), `quick_result{answer,citations[]}`, `deep_result{result,citations[]}`, `error` | `_normalize_research` |
| Research cancel | `POST https://agent.tinyfish.ai/v1/research-run/{id}/cancel` | | `cancelled` | `run_research` |
| Monitor create (F2) | `POST https://agent.tinyfish.ai/v1/monitors` | `type` (fetch = Page, search = Topic), `config` (`url`,`format` or `query`,`result_limit`,`recency_minutes`), `schedule_cron`, `name`, `purpose`, `webhook_url` | 201 `monitor{id,type,config,status,...}`, `run{id,is_baseline,results[]}` | `_normalize_monitor` |
| Monitor list / get / delete / run now | `GET /v1/monitors` (`monitors[]`), `GET /v1/monitors/{id}`, `DELETE /v1/monitors/{id}` (`deleted`,`id`), `POST /v1/monitors/{id}/runs` (201 `run`) | | | `list_monitors`, `get_monitor`, `delete_monitor`, `trigger_monitor` |

## Verified semantics

- `COMPLETED` only means the infrastructure worked. A failed goal is `COMPLETED` with `result.status == "failure"` and `result.reason`. `validation.judge_run` checks the run status first, then `result.status`, then the output schema.
- `FAILED` runs carry `error.category`: `SYSTEM_FAILURE` (retry after `retry_after`; `null` means do not retry), `AGENT_FAILURE` (fix the input; codes `TASK_FAILED`, `SITE_BLOCKED`, `MAX_STEPS_EXCEEDED`, `CONTENT_POLICY_VIOLATION`), `BILLING_FAILURE` (rejected before start; ends `CANCELLED`), `UNKNOWN` (treat as retryable). Aegis retries once, waits at most `max_retry_wait_s` (120 s), and uses 5 s for `UNKNOWN` without `retry_after`.
- HTTP errors: 400 `INVALID_INPUT`, 401 `MISSING_API_KEY`/`INVALID_API_KEY`, 402 `INSUFFICIENT_CREDITS`/`FREE_ALLOWANCE_EXHAUSTED`, 403 `FORBIDDEN`, 404, 409 `RETRY_REQUIRED`, 429 `RATE_LIMIT_EXCEEDED` (retry) or `DAILY_LIMIT_EXCEEDED` (do not retry until reset), 5xx (retry, honour `Retry-After`). Error bodies are `{"error":{"code","message","details"},"request_id"}`.
- `output_schema` keyword allowlist: `anyOf`, `enum`, `format`, `items`, `maxItems`, `maximum`, `minItems`, `minimum`, `nullable`, `properties`, `propertyOrdering`, `required`, `type`. `additionalProperties`, `const`, `oneOf` and examples are rejected with HTTP 400. Max 64 KB and depth 10. Our schemas use only `type`, `properties`, `items`, `required`, `enum`, `description`.
- `agent_config.max_steps` caps steps per run (1 to 500, default 150, marked beta). The budget ledger sets it per run so a run cannot exceed the remaining request budget.
- Webhooks: `POST` with `{event, run_id, status, data}` where `data` has the shape of `GET /v1/runs/{id}`. Events `run.completed`, `run.failed`, `run.cancelled`. HTTPS only. 4 attempts (1 s, 2 s, 4 s backoff), 10 s timeout, no retry on 4xx. Duplicates can arrive; dedupe on `run_id`. **No signature is documented**; the docs recommend calling `GET /v1/runs/{run_id}` before acting, which `monitors.handle_webhook` does.
- Monitor webhooks are sent for every scheduled run, changed or not. Page payload: `fetch_monitor_id`, `id`, `is_baseline`, `results[]`, `errors[]`. Topic payload: `search_monitor_id`, `id`, `query`, `results[]`, `new_result_positions[]`. Manual runs (`POST .../runs`) send no webhook. Topic schedules must be at least 30 minutes apart. Up to 50 monitors per account; $0.005 per completed run (monitor overview page).
- `streaming_url` is valid for 24 hours and the docs describe embedding it in an iframe. They say nothing about access control, so Aegis exposes it only on the authenticated run view while the run is running and never persists or logs it.
- Pricing page: Agent $0.016 per step; 2 concurrent Agent runs on pay-as-you-go; Search free at 30/min and 500/hour; Fetch free at 150 URLs/min and 1,000 URLs/day.

## Unverified (isolated behind one function each, marked `# unverified:`)

| What | Where | What to check |
|---|---|---|
| SSE wire framing. The OpenAPI schema documents the event JSON objects but not the `data:` line framing. | `tinyfish_client._normalize_sse_line_block` | Capture one live `run-sse` stream and confirm each event is a `data: {json}` block separated by a blank line. |
| `include_domains` encoding. OpenAPI types it as a plain string. | `TinyFishClient.search` | Confirm a comma-separated list is accepted. |
| `GET /v1/monitors/{id}` body. The docs do not show it. | `tinyfish_client._normalize_monitor` | Confirm it returns the same `monitor` object as create. |
| IMD API auth header (not TinyFish). `api_reference.html` lists `/districtwarning` fields but no auth scheme. | `runner.LiveGateway.api_get`; source `imd_api` stays `verified=False` | Confirm the header once IMD issues a key. |

Not used and not verified: `POST /v1/automation/run-batch` (exists in OpenAPI; bulk relief-camp extraction would use it), Browser API, Vault, browser profiles, the research SSE event names (we poll `GET /v1/research-run/{id}`), and research pricing or daily limits (the brief cites 5 runs per day from a blog post).

## Indian sources checked by hand on 2026-10-16

| Source id | Start URL | Result | `verified` |
|---|---|---|---|
| `cwc_ffs` | `https://ffs.india-water.gov.in/` | 200, title "Flood Forecast - Central Water Commision, Govt. Of India" | true |
| `imd_mausam` | `https://mausam.imd.gov.in/responsive/districtWiseWarningGIS.php` | 200, title "DW Warnings, India Meteorological Department" | true |
| `imd_api` | `https://api.imd.gov.in/api/v1/districtwarning` | portal loads; registration required; auth undocumented | false |
| `sachet_in`, `sachet_bihar`, `sachet_assam` | `https://sachet.ndma.gov.in/cap_public_website/rss/rss_{india,bihar,assam}.xml` | RSS 2.0, items link to CAP 1.2 XML (`FetchXMLFile?identifier=`). The Bihar feed carried CWC river advisories with level, warning and danger values. | true |
| `fmisc_bihar` | `https://fmiscwrdbihar.gov.in/fmis/DailyfloodInd.aspx` | page loads; its "Daily Flood Bulletin" PDF returned 404 (season ended 15 Oct) | true, seasonal |
| `fmisc_contacts` | `https://fmiscwrdbihar.gov.in/` | lists Central Flood Control Room 0612-2256999 | true |
| `ndma_contact` | `https://ndma.gov.in/en/contact-us` | lists Control Room +91-11-26701728 | true |
| `ntes` | `https://enquiry.indianrail.gov.in/mntes/` | `/ntes/` redirects here; title "NTES" with cancelled/diverted/rescheduled sections | true |
| `nhai_notices` | search on `nhai.gov.in`, `morth.gov.in`, `morth.nic.in` | both sites load | true |
| `apdcl` | `https://www.apdcl.org/website/` | title "APDCL, Assam Power Distribution Company Limited" | true |
| `asdma_reports` | `https://asdma.gov.in/` | connection refused on ports 80 and 443 | false |
| `bihar_dmd` | `https://state.bihar.gov.in/disastermgmt/CitizenHome.html` | 302 redirect loop | false |
| `bihar_health` | `https://state.bihar.gov.in/health/CitizenHome.html` | `health.bihar.gov.in` does not resolve; `state.bihar.gov.in` loops | false |
| `nbpdcl` | `https://nbpdcl.co.in/` | 200 but empty title; no outage page found | false |
| `news_search`, `research_brief` | TinyFish Search and Research over domain allowlists | API verified; not portals | true |
