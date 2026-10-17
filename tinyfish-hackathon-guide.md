# TinyFish.ai — Hackathon Developer Guide

> **Unofficial guide.** This document was produced by an independent AI researcher, not by TinyFish (Tiny Fish Inc.). Always verify details against the official documentation at [docs.tinyfish.ai](https://docs.tinyfish.ai) and the official pricing page at [tinyfish.ai/pricing](https://www.tinyfish.ai/pricing).

---

## Table of Contents

1. [Title and Executive Summary](#1-title-and-executive-summary)
2. [Quick Start (≤ 15 Minutes)](#2-quick-start--15-minutes)
3. [Service and Feature Catalog](#3-service-and-feature-catalog)
4. [Detailed Service Sections](#4-detailed-service-sections)
   - 4.1 [Search API](#41-search-api)
   - 4.2 [Fetch API](#42-fetch-api)
   - 4.3 [Agent API](#43-agent-api)
   - 4.4 [Browser API](#44-browser-api)
   - 4.5 [Research API (Beta)](#45-research-api-beta)
   - 4.6 [Monitor](#46-monitor)
   - 4.7 [MCP Integration](#47-mcp-integration)
   - 4.8 [CLI](#48-cli)
   - 4.9 [Mako Model](#49-mako-model)
   - 4.10 [TinyVault / Browser Context Profiles](#410-tinyvault--browser-context-profiles)
   - 4.11 [Webhooks](#411-webhooks)
   - 4.12 [Agent Payments (Machine Payments Protocol)](#412-agent-payments-machine-payments-protocol)
5. [Authentication and Authorization](#5-authentication-and-authorization)
6. [Integration Guide](#6-integration-guide)
7. [Best Practices for Performance and Reliability](#7-best-practices-for-performance-and-reliability)
8. [Credits, Attribution, and Licensing](#8-credits-attribution-and-licensing)
9. [Hackathon Timeline Plan](#9-hackathon-timeline-plan)
10. [Example Project Ideas](#10-example-project-ideas)
11. [Troubleshooting and FAQ](#11-troubleshooting-and-faq)
12. [Disclaimers and Constraints](#12-disclaimers-and-constraints)
13. [Appendix](#13-appendix)
    - A. [Glossary](#a-glossary)
    - B. [Full Source List](#b-full-source-list)
    - C. [.env.example Template](#c-envexample-template)
    - D. [Quick-Reference Cheat Sheet](#d-quick-reference-cheat-sheet)

---

## 1. Title and Executive Summary

### What Is TinyFish?

**TinyFish** (legal name: Tiny Fish Inc., Palo Alto, CA) is an **enterprise-grade web infrastructure platform for AI agents**. It gives developers a unified API to search the web, extract clean page content, automate multi-step browser workflows, and run cloud browser sessions — all under a single API key and a single billing wallet.

TinyFish targets developers building AI agents, LLM pipelines, and autonomous workflows that must interact with live websites: scraping, form submission, authenticated dashboards, competitive research, and anything that requires a real browser but should not require maintaining one.

**Core products:**

| Product | Tagline |
|---------|---------|
| **Search** | Fast, structured web search for AI agents |
| **Fetch** | Any URL → clean Markdown/HTML/JSON |
| **Agent** | Multi-step web automation via natural-language goals |
| **Browser** | Cloud browser sessions (CDP/Playwright) |
| **Research** *(Beta)* | Multi-source cited research reports |
| **Monitor** | Scheduled page/topic change detection |
| **Mako** | Web-native model for live workflows |
| **MCP** | Model Context Protocol integration for AI assistants |
| **CLI** | Terminal-based automation runner |
| **Vault** | Secure credential integration (1Password, Bitwarden) |

### Why Use TinyFish at a Hackathon?

TinyFish collapses a week of browser-scraping infrastructure work into 15 minutes. Search and Fetch are **completely free** within generous daily limits. New accounts start with **$8 of pre-loaded wallet funds** — enough to run Agent and Browser tasks before committing a card. All four core APIs share one key, one SDK, and one endpoint domain. For a hackathon team that needs real-time web data, dynamic page automation, or competitive research without spinning up Puppeteer clusters, TinyFish is the fastest path from "idea" to "working demo."

**Document version:** 1.0
**Date researched:** October 12, 2026
**Sources:** See [Appendix B](#b-full-source-list)

---

## 2. Quick Start (≤ 15 Minutes)

### Step 1 — Create an Account (~2 min)

1. Go to [agent.tinyfish.ai/sign-up](https://agent.tinyfish.ai/sign-up).
2. Sign up with an email or OAuth provider.
3. New accounts receive **$8 of free Wallet funds** — no credit card required to start.

### Step 2 — Get Your API Key (~1 min)

1. Visit [agent.tinyfish.ai/api-keys](https://agent.tinyfish.ai/api-keys).
2. Click **Create API Key**.
3. Copy the key immediately — it is shown only once.

> **Warning:** Never commit an API key to version control. Store it in environment variables or a secrets manager.

```bash
export TINYFISH_API_KEY="sk-tinyfish-YOUR_KEY_HERE"
```

### Step 3 — Install the SDK (~2 min)

**Python:**
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install tinyfish
```

**Node.js / TypeScript:**
```bash
npm i @tiny-fish/sdk
npm pkg set type=module   # SDK is ESM-only
```

**CLI (optional):**
```bash
npm install -g @tiny-fish/cli
```

### Step 4 — Hello World (~5 min)

This example searches the web, fetches a page, and runs a goal-based agent automation.

**Python:**
```python
# hello_tinyfish.py
from tinyfish import TinyFish, CompleteEvent

client = TinyFish()  # reads TINYFISH_API_KEY from environment

# ── 1. Search ──────────────────────────────────────────────────
results = client.search.query(query="TinyFish web agent")
print("=== Search Results ===")
for r in results.results[:2]:
    print(f"  {r.title}  →  {r.url}")

# ── 2. Fetch ───────────────────────────────────────────────────
fetch_result = client.fetch.get_contents(urls=["https://www.tinyfish.ai/"])
print("\n=== Fetched Title ===")
print(fetch_result.results[0].title)

# ── 3. Agent (streaming) ───────────────────────────────────────
print("\n=== Agent Run ===")
with client.agent.stream(
    url="https://scrapeme.live/shop",
    goal="Extract the first 2 product names and prices. Return as JSON.",
) as stream:
    for event in stream:
        if isinstance(event, CompleteEvent):
            print("Result:", event.result_json)
```

**Expected output:**
```
=== Search Results ===
  TinyFish — Web Infrastructure for AI Agents  →  https://www.tinyfish.ai
  TinyFish Developer Documentation  →  https://docs.tinyfish.ai

=== Fetched Title ===
TinyFish — Web Infrastructure for AI Agents

=== Agent Run ===
Result: {"products": [{"name": "Bulbasaur", "price": "£63.00"}, {"name": "Ivysaur", "price": "£87.00"}]}
```

**TypeScript equivalent:**
```typescript
// hello-tinyfish.ts
import { TinyFish } from "@tiny-fish/sdk";

const client = new TinyFish();

// Search
const search = await client.search.query({ query: "TinyFish web agent" });
search.results.slice(0, 2).forEach(r => console.log(r.title, "→", r.url));

// Fetch
const fetchResult = await client.fetch.getContents({ urls: ["https://www.tinyfish.ai/"] });
console.log(fetchResult.results[0].title);

// Agent (streaming)
const stream = await client.agent.stream({
  url: "https://scrapeme.live/shop",
  goal: "Extract the first 2 product names and prices. Return JSON.",
});
for await (const event of stream) {
  if (event.type === "COMPLETE") console.log("Result:", event.result);
}
```

**Run it:**
```bash
# Python
python hello_tinyfish.py

# TypeScript
npx tsx hello-tinyfish.ts
```

---

## 3. Service and Feature Catalog

| Name | Purpose | Interface | Key Inputs | Key Outputs | Est. Setup Time |
|------|---------|-----------|------------|-------------|-----------------|
| **Search API** | Structured web search | REST / SDK / CLI / MCP | `query`, `location`, `language`, `domain_type` | Ranked results (title, snippet, URL) | ~2 min |
| **Fetch API** | URL → clean text | REST / SDK / CLI / MCP | `urls[]`, `format`, `ttl` | `title`, `text` (Markdown/HTML/JSON) | ~2 min |
| **Agent API** | Goal-based web automation | REST / SDK / CLI / MCP | `url`, `goal`, `output_schema` | Structured JSON result + SSE events | ~5 min |
| **Browser API** | Cloud CDP browser session | REST / SDK / CLI / MCP | `url`, `proxy_config` | `session_id`, `cdp_url` (WebSocket) | ~10 min |
| **Research API** *(Beta)* | Multi-source research report | REST | `query`, `mode` | SSE stream → cited report | ~5 min |
| **Monitor** | Scheduled page/topic change tracking | UI / REST | URL or topic query, schedule | Change diffs, webhook/email notifications | ~5 min (UI) |
| **MCP Integration** | Connect TinyFish to AI assistants | OAuth 2.1 / config | MCP server URL | All TinyFish tools available in-assistant | ~5 min |
| **CLI** | Terminal automation runner | Shell | `--url`, `goal`, commands | JSON / pretty output | ~3 min |
| **Mako** | Web-native LLM for live workflows | ⚠️ Unverified | ⚠️ Unverified | ⚠️ Unverified | ⚠️ Unverified |
| **Vault** | Secure site login (1Password/Bitwarden) | REST / SDK / CLI | Vault provider + credentials | Authenticated browser sessions | ~10 min |
| **Browser Context Profiles** | Persist logged-in browser state | REST / SDK | `profile_id`, setup session | Reusable session state for Agent runs | ~15 min |
| **Webhooks** | Run lifecycle notifications | REST config field | `webhook_url` on run start | POST payloads on run events | ~5 min |
| **Agent Payments (MPP)** | Agent-initiated wallet top-up | REST | Machine Payments Protocol challenge | Wallet credit | ⚠️ Unverified for broad use |

> **Note on Mako:** Mako appears as a product in TinyFish's navigation and is described as a "web-native model for live workflows," but no public API reference, pricing, or integration documentation was found in the official docs index at the time of research. Verify at [tinyfish.ai/mako](https://www.tinyfish.ai/mako).

---

## 4. Detailed Service Sections

---

### 4.1 Search API

#### Overview

The Search API performs web searches and returns structured, LLM-ready results (title, snippet, URL, and rich fields for news and academic searches). Free within a daily allowance of **12,000 requests per day**, resetting at 00:00 UTC.

#### Hackathon Use Cases

- Grounding an LLM with current web facts before generation
- Finding competitor pricing, news, or documentation
- Academic research synthesis pipelines
- Discovering URLs before feeding them to the Fetch or Agent API

#### Prerequisites

- TinyFish account + API key
- Python `tinyfish` package OR Node.js `@tiny-fish/sdk` package

#### Authentication

All requests require the `X-API-Key` header:
```
X-API-Key: YOUR_API_KEY
```
The SDK reads `TINYFISH_API_KEY` from the environment automatically.

#### Endpoint Reference

```
GET https://api.search.tinyfish.ai
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | string | **Yes** | — | Search query string |
| `purpose` | string | No | — | Why you are searching (intent signal, max 2000 chars) |
| `location` | string | No | `US` | Country code for geo-targeted results (e.g. `GB`, `DE`) |
| `language` | string | No | `en` | Language code (e.g. `fr`, `ja`) |
| `include_domains` | string | No | — | Comma-separated domains to restrict to |
| `exclude_domains` | string | No | — | Comma-separated domains to exclude |
| `recency_minutes` | integer | No | — | Freshness window from now (1–5,256,000) |
| `after_date` | string | No | — | Lower date cutoff `YYYY-MM-DD` |
| `before_date` | string | No | — | Upper date cutoff `YYYY-MM-DD` |
| `domain_type` | string | No | `web` | `web` \| `news` \| `research_paper` |
| `pub_year_min` | integer | No | — | Min publication year (research_paper only) |
| `pub_year_max` | integer | No | — | Max publication year (research_paper only) |
| `page` | integer | No | `0` | Pagination (0-indexed, max 10) |

**Response:**

```json
{
  "query": "web automation tools",
  "results": [
    {
      "position": 1,
      "site_name": "tinyfish.ai",
      "title": "TinyFish — AI Web Automation Platform",
      "snippet": "Automate any website with natural language instructions...",
      "url": "https://tinyfish.ai"
    }
  ],
  "total_results": 10,
  "page": 0
}
```

News results also include `publisher` and `date`; academic results include `authors`, `venue`, `year`, `cited_by_count`, `pdf_url`.

#### Code Examples

**cURL:**
```bash
curl "https://api.search.tinyfish.ai?query=python+web+scraping&location=US&language=en" \
  -H "X-API-Key: $TINYFISH_API_KEY"
```

**Python:**
```python
from tinyfish import TinyFish

client = TinyFish()
response = client.search.query(
    query="python web scraping tools",
    location="US",
    domain_type="web",
    recency_minutes=10080,  # past week
)
for r in response.results:
    print(f"{r.position}. {r.title}\n   {r.url}\n   {r.snippet}\n")
```

**TypeScript:**
```typescript
import { TinyFish } from "@tiny-fish/sdk";

const client = new TinyFish();
const response = await client.search.query({
  query: "python web scraping tools",
  location: "US",
  domainType: "web",
  recencyMinutes: 10080,
});
response.results.forEach(r => {
  console.log(`${r.position}. ${r.title}`);
  console.log(`   ${r.url}`);
});
```

#### Error Handling

| Status | Code | Fix |
|--------|------|-----|
| `400` | `INVALID_INPUT` | Check `query` is present and parameters are valid |
| `401` | `MISSING_API_KEY` / `INVALID_API_KEY` | Set/fix `X-API-Key` header |
| `402` | `INSUFFICIENT_CREDITS` | Daily allowance used + wallet at zero; add funds or wait for UTC midnight |
| `429` | `RATE_LIMIT_EXCEEDED` | Default 30 req/min; respect `Retry-After` header |
| `503` | `SERVICE_BUSY` | Retry with exponential backoff |

#### Rate Limits and Pricing

- **Free:** 12,000 requests/day (resets 00:00 UTC)
- **Rate limit:** 30 requests/minute per API key
- **Overage:** Draws from wallet when daily allowance is exceeded

#### Best Practices

- Pass `purpose` to improve result relevance for complex queries.
- Use `include_domains` / `exclude_domains` instead of `site:` operators in the query string.
- Do not combine `recency_minutes` with date filters — use one or the other.

#### Estimated Setup Time: ~2 minutes

---

### 4.2 Fetch API

#### Overview

The Fetch API takes one or more URLs and returns clean, LLM-ready text in Markdown, HTML, or structured JSON format. It renders JavaScript-heavy pages (SPAs, React apps) and strips navigation, cookie banners, and boilerplate. Free within **1,000 URLs/day**, resetting at 00:00 UTC.

#### Hackathon Use Cases

- Extracting article or documentation content for RAG pipelines
- Batch scraping multiple competitor pages simultaneously
- Converting JavaScript-rendered content to Markdown for an LLM context window
- Detecting page changes with conditional requests

#### Endpoint Reference

```
POST https://api.fetch.tinyfish.ai
```

**Request body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `urls` | string[] | **Yes** | — | Up to 10 URLs to fetch |
| `format` | string | No | `markdown` | `markdown` \| `html` \| `json` |
| `ttl` | integer | No | — | Cache freshness in seconds; `0` = always fresh |
| `purpose` | string | No | — | Why you're fetching (intent signal, max 2000 chars) |
| `include_selectors` | string[] | No | — | CSS selectors to scope extraction to (max 20) |
| `exclude_selectors` | string[] | No | — | CSS selectors to strip before extraction (max 20) |
| `per_url_timeout_ms` | integer | No | — | Per-URL wall-clock timeout budget |
| `links` | boolean | No | — | Include outbound URLs in response |
| `image_links` | boolean | No | — | Include image URLs in response |
| `if_none_match` | string | No | — | ETag for conditional request (single URL only) |
| `if_modified_since` | string | No | — | Last-Modified for conditional request (single URL only) |
| `include_etag_and_last_modified` | boolean | No | — | Return validators for future conditional requests |
| `highlights` | object | No | — | **Beta** — ranked verbatim passage extraction |

**Response:**

```json
{
  "results": [
    {
      "url": "https://www.tinyfish.ai/",
      "final_url": "https://www.tinyfish.ai/",
      "title": "TinyFish | Enterprise Web Agent Infrastructure",
      "description": "TinyFish provides enterprise infrastructure for AI web agents.",
      "language": "en",
      "format": "markdown",
      "text": "# TinyFish | Enterprise Web Agent Infrastructure\n\n..."
    }
  ],
  "errors": []
}
```

> **Note:** Per-URL failures appear in `errors[]` alongside a 200 HTTP response — they do not fail the whole request.

#### Code Examples

**cURL:**
```bash
curl -X POST https://api.fetch.tinyfish.ai \
  -H "X-API-Key: $TINYFISH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": [
      "https://docs.python.org/3/tutorial/index.html",
      "https://nodejs.org/en/docs/"
    ],
    "format": "markdown"
  }'
```

**Python:**
```python
from tinyfish import TinyFish

client = TinyFish()
result = client.fetch.get_contents(
    urls=[
        "https://docs.python.org/3/tutorial/index.html",
        "https://nodejs.org/en/docs/",
    ],
    format="markdown",
    ttl=3600,  # accept cached entries up to 1 hour old
)
for page in result.results:
    print(f"Title: {page.title}\n{page.text[:200]}\n")
for error in result.errors:
    print(f"Failed: {error.url} — {error.error}")
```

**TypeScript:**
```typescript
import { TinyFish } from "@tiny-fish/sdk";

const client = new TinyFish();
const result = await client.fetch.getContents({
  urls: [
    "https://docs.python.org/3/tutorial/index.html",
    "https://nodejs.org/en/docs/",
  ],
  format: "markdown",
  ttl: 3600,
});
result.results.forEach(p => console.log(p.title, "→", p.text.slice(0, 200)));
result.errors.forEach(e => console.error("Failed:", e.url, e.error));
```

#### Error Handling

| Status | Meaning | Fix |
|--------|---------|-----|
| `400` | Invalid request (> 10 URLs, conflicting conditional params) | Read `error.details` |
| `401` | Auth error | Check API key |
| `402` | Daily allowance exhausted + wallet empty | Add funds or wait for reset |
| `429` | Rate limit (150 URLs/min) | Back off; use `Retry-After` header |

#### Rate Limits and Pricing

- **Free:** 1,000 URLs/day (resets 00:00 UTC)
- **Rate limit:** 150 URLs/minute
- **Overage:** Draws from wallet

#### Best Practices

- Use `ttl: 0` for real-time data; omit `ttl` to allow cached content (faster and free-quota-friendly).
- Use `include_selectors` to target only `article` or `main` content — smaller payloads, less token usage.
- Batch up to 10 URLs per request — they process in parallel.
- Use conditional requests (`if_none_match`) to skip re-processing unchanged pages.

#### Estimated Setup Time: ~2 minutes

---

### 4.3 Agent API

#### Overview

The Agent API lets you describe a task in natural language and have TinyFish execute it on a real website using a cloud browser. The agent navigates, clicks, fills forms, and extracts data — returning structured JSON. Priced at **$0.016 per step** from your wallet.

Three execution patterns:

| Endpoint | Pattern | Best for |
|----------|---------|---------|
| `POST /v1/automation/run` | Synchronous (blocks until done) | Quick tasks, simple integrations |
| `POST /v1/automation/run-async` | Async (returns `run_id` immediately) | Long tasks, batch processing |
| `POST /v1/automation/run-sse` | SSE stream (real-time events) | User-facing apps needing live progress |

#### Hackathon Use Cases

- Automating multi-step form submissions
- Extracting data from login-gated dashboards
- Competitive pricing or product comparison across many sites
- Testing web app flows with natural-language assertions

#### Prerequisites

- TinyFish account with positive wallet balance
- Default concurrency limit: 2 concurrent runs (configurable via sales)

#### Endpoint Reference

**Base URL:** `https://agent.tinyfish.ai/v1/automation/`

**Common Request Body Fields:**

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `url` | string | **Yes** | — | Target website URL (must include `https://`) |
| `goal` | string | **Yes** | — | Natural-language automation instruction |
| `output_schema` | object | No | — | JSON Schema subset for structured output |
| `browser_profile` | string | No | `lite` | `lite` \| `stealth` (stealth bypasses more anti-bot) |
| `proxy_config.enabled` | boolean | No | — | Enable proxy for this run |
| `proxy_config.type` | string | No | `tinyfish` | `tinyfish` \| `custom` |
| `proxy_config.country_code` | string | No | `US` | `US` \| `GB` \| `CA` \| `DE` \| `FR` \| `JP` \| `AU` |
| `proxy_config.url` | string | No | — | Required when `type: "custom"` |
| `agent_config.mode` | string | No | — | **Beta** — `default` \| `strict` |
| `agent_config.max_steps` | integer | No | 150 | **Beta** — step budget (1–500) |
| `agent_config.max_duration_seconds` | integer | No | — | Wall-clock time limit |
| `webhook_url` | string | No | — | HTTPS URL for run lifecycle notifications |
| `use_profile` | boolean | No | — | Use default Browser Context Profile |
| `profile_id` | string | No | — | Specific Browser Context Profile ID |
| `use_vault` | boolean | No | — | Enable vault credentials for login |
| `credential_item_ids` | string[] | No | — | Scope to specific vault credentials |

**SSE Event Types (run-sse):**

| Event | Fields |
|-------|--------|
| `STARTED` | `type`, `run_id`, `timestamp` |
| `STREAMING_URL` | `type`, `run_id`, `streaming_url`, `timestamp` |
| `PROGRESS` | `type`, `run_id`, `purpose`, `timestamp` |
| `HEARTBEAT` | `type`, `timestamp` |
| `COMPLETE` | `type`, `run_id`, `status`, `result?`, `error?`, `timestamp` |

**Synchronous response (`/run`):**

```json
{
  "run_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "COMPLETED",
  "started_at": "2024-01-01T00:00:00Z",
  "finished_at": "2024-01-01T00:00:30Z",
  "num_of_steps": 5,
  "result": { "plans": [{ "name": "Starter", "price": "$9/mo" }] },
  "error": null
}
```

**Run status values:** `PENDING` → `RUNNING` → `COMPLETED` | `FAILED` | `CANCELLED`

#### Code Examples

**cURL (SSE):**
```bash
curl -N -X POST https://agent.tinyfish.ai/v1/automation/run-sse \
  -H "X-API-Key: $TINYFISH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://scrapeme.live/shop",
    "goal": "Extract the first 2 product names and prices. Return as JSON."
  }'
```

**Python (SSE streaming):**
```python
from tinyfish import TinyFish, CompleteEvent, ProgressEvent

client = TinyFish()

with client.agent.stream(
    url="https://scrapeme.live/shop",
    goal="Extract the first 2 product names and prices. Return as JSON.",
) as stream:
    for event in stream:
        if isinstance(event, ProgressEvent):
            print(f"[Progress] {event.purpose}")
        elif isinstance(event, CompleteEvent):
            print(f"[Status]   {event.status}")
            print(f"[Result]   {event.result_json}")
```

**Python (synchronous — simple):**
```python
from tinyfish import TinyFish

client = TinyFish()
result = client.agent.run(
    url="https://scrapeme.live/shop",
    goal="Extract first 2 product names and prices. Return as JSON.",
)
print(result.status, result.result)
```

**Python (async + poll — for long tasks):**
```python
from tinyfish import TinyFish
import time

client = TinyFish()

run = client.agent.run_async(
    url="https://scrapeme.live/shop",
    goal="Extract the first 5 products. Return as JSON.",
)
print(f"Run started: {run.run_id}")

while True:
    status = client.runs.get(run.run_id)
    if status.status in ("COMPLETED", "FAILED", "CANCELLED"):
        print(status.result)
        break
    time.sleep(5)
```

**TypeScript (SSE streaming):**
```typescript
import { TinyFish } from "@tiny-fish/sdk";

const client = new TinyFish();
const stream = await client.agent.stream({
  url: "https://scrapeme.live/shop",
  goal: "Extract the first 2 product names and prices. Return JSON.",
});

for await (const event of stream) {
  if (event.type === "PROGRESS") console.log("[Progress]", event.purpose);
  if (event.type === "COMPLETE") {
    console.log("[Status]", event.status);
    console.log("[Result]", event.result);
  }
}
```

**Raw SSE without SDK (Python):**
```python
import os, httpx, json

url = "https://agent.tinyfish.ai/v1/automation/run-sse"
headers = {"X-API-Key": os.environ["TINYFISH_API_KEY"]}
payload = {"url": "https://example.com", "goal": "Extract the page title"}

with httpx.stream("POST", url, headers=headers, json=payload, timeout=120) as resp:
    for line in resp.iter_lines():
        if line.startswith("data: "):
            event = json.loads(line[6:])
            print(event["type"], event.get("purpose", event.get("result", "")))
            if event["type"] == "COMPLETE":
                break
```

#### Error Handling

| HTTP Status | Code | Fix |
|-------------|------|-----|
| `400` | `INVALID_INPUT` | Check `url` (must be HTTPS), `goal` not empty |
| `401` | `MISSING_API_KEY` / `INVALID_API_KEY` | Set/fix API key |
| `402` | `INSUFFICIENT_CREDITS` | Add $10+ to wallet |
| `403` | `FORBIDDEN` | No credits on legacy plan, or entitlement missing |
| `429` | `RATE_LIMIT_EXCEEDED` | Wait for existing runs to finish (pending-run cap: 2) |
| `500` | `INTERNAL_ERROR` | Retry after a short delay |

**Run-response errors (HTTP 200, check `result.error.code`):**

| Code | Category | Fix |
|------|----------|-----|
| `SITE_BLOCKED` | `AGENT_FAILURE` | Switch to `browser_profile: "stealth"`, add proxy |
| `TASK_FAILED` | `AGENT_FAILURE` | Refine goal, add context, use Vault for auth |
| `MAX_STEPS_EXCEEDED` | `AGENT_FAILURE` | Simplify goal, split into multiple runs |
| `TIMEOUT` | `SYSTEM_FAILURE` | Retry; simplify goal if persistent |
| `SERVICE_BUSY` | `SYSTEM_FAILURE` | Retry with exponential backoff |

> **SSE disconnect recovery:** SSE does not support `Last-Event-ID`. On disconnect, poll `GET /v1/runs/{run_id}` every 5 seconds until terminal status.

#### Rate Limits and Pricing

- **$0.016 per step** (a "step" = one agent action/navigation cycle)
- **Default concurrency:** 2 simultaneous runs
- Runs cannot be cancelled when created via `/run` (synchronous endpoint)

#### Best Practices

- Write specific goals: state the exact output format, the target page section, and any login context.
- Use `output_schema` for consistent, typed JSON output.
- Use `stealth` browser profile for sites with aggressive bot detection.
- Set `max_duration_seconds` to prevent runaway costs on complex pages.
- Start async runs and poll for long tasks to avoid HTTP timeout issues.
- Cancel unused async runs: `POST /v1/runs/{id}/cancel`.

#### Estimated Setup Time: ~5 minutes

---

### 4.4 Browser API

#### Overview

The Browser API creates an isolated, managed cloud Chromium session and returns a CDP (Chrome DevTools Protocol) WebSocket URL. Connect with Playwright, Puppeteer, or any CDP-compatible client. Priced at **$0.002 per browser-minute**.

#### Hackathon Use Cases

- Automated UI testing with Playwright against live sites
- Recording user flows for demo purposes
- Controlled scraping where you need precise DOM interaction
- Setting up Browser Context Profiles (logged-in state) for later Agent API reuse

#### Prerequisites

- Positive wallet balance
- Playwright or Puppeteer installed locally

```bash
# Python
pip install playwright tinyfish
playwright install chromium

# Node.js
npm install @tiny-fish/sdk playwright
npx playwright install chromium
```

#### Endpoint Reference

```
POST https://api.browser.tinyfish.ai
```

**Request body:**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `url` | string | No | Optional starting URL |
| `proxy_config.enabled` | boolean | No | Enable/disable proxy |
| `proxy_config.type` | string | No | `tinyfish` (default) \| `custom` |
| `proxy_config.country_code` | string | No | `US` (default), `GB`, `DE`, `FR`, `JP`, etc. |
| `proxy_config.url` | string | No | Custom proxy URL |
| `timeout_seconds` | integer | No | Session inactivity timeout |

**Response:**

```json
{
  "session_id": "br-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "cdp_url": "wss://example.tinyfish.io/cdp",
  "base_url": "https://example.tinyfish.io"
}
```

> **Important:** Pass `cdp_url` (the WebSocket URL) to Playwright's `connect_over_cdp`. Do **not** use `base_url` for Playwright connections.

**Session lifecycle:**
- Auto-terminates after inactivity timeout (15 min on free plans, 60 min on paid).
- Terminate early: `DELETE https://api.browser.tinyfish.ai/{session_id}`

#### Code Examples

**cURL (create session):**
```bash
curl -X POST https://api.browser.tinyfish.ai \
  -H "X-API-Key: $TINYFISH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.example.com"}'
```

**Python (create + Playwright):**
```python
import asyncio
from tinyfish import TinyFish
from playwright.async_api import async_playwright

async def main():
    client = TinyFish()
    # Create remote browser session (~10-30 seconds to provision)
    session = client.browser.sessions.create(url="https://www.example.com")
    print(f"Session ID: {session.session_id}")
    print(f"CDP URL:    {session.cdp_url}")

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(session.cdp_url)
        await asyncio.sleep(2)  # let startup navigation settle

        page = browser.contexts[0].pages[0]
        await page.wait_for_load_state("domcontentloaded")
        print(f"Title: {await page.title()}")

        # --- your automation here ---

        await browser.close()

    # Terminate session explicitly to stop billing
    client.browser.sessions.terminate(session.session_id)

asyncio.run(main())
```

**TypeScript (create + Playwright):**
```typescript
import { TinyFish } from "@tiny-fish/sdk";
import { chromium } from "playwright";

const client = new TinyFish();
const session = await client.browser.sessions.create({ url: "https://example.com" });
console.log("CDP URL:", session.cdp_url);

const browser = await chromium.connectOverCDP(session.cdp_url);
await new Promise(r => setTimeout(r, 2000)); // let startup settle

const page = browser.contexts()[0].pages()[0];
await page.waitForLoadState("domcontentloaded");
console.log("Title:", await page.title());
await browser.close();
```

#### Error Handling

| Status | Meaning | Fix |
|--------|---------|-----|
| `401` | Auth error | Check API key |
| `402` | Insufficient wallet funds | Add $10+ to wallet |
| `429` | Concurrent session limit hit | Wait for sessions to end or terminate them |

> **Timeout note:** Session creation takes 10–30 seconds. Set HTTP client timeout to at least 60 seconds.

#### Rate Limits and Pricing

- **$0.002 per browser-minute**
- **Default:** 5 concurrent sessions
- Inactivity timeout: 15 min (free) / 60 min (paid)

#### Best Practices

- Always terminate sessions explicitly when done to avoid unexpected charges.
- Wait 2 seconds after connecting before interacting with the page.
- Use `proxy_config.country_code` when testing geo-restricted content.
- For reusable logged-in state, save the session as a **Browser Context Profile**.

#### Estimated Setup Time: ~10 minutes

---

### 4.5 Research API (Beta)

#### Overview

The Research API runs a multi-step search-and-synthesis workflow across the web and returns a cited, structured research report as a Server-Sent Events stream. Available to all accounts during beta.

#### Endpoint Reference

```
POST https://agent.tinyfish.ai/v1/automation/run-research
```

**Request body:**

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `query` | string | **Yes** | Natural-language research question |
| `mode` | string | **Yes** | `standard` (⚠️ additional modes not confirmed in public docs) |

**SSE events:**
```
data: {"event":"created","research_run_id":"..."}
data: {"event":"plan_updated","iteration":1,...}
data: {"event":"final_result","result":"...","citations":[...]}
data: {"event":"done"}
```

#### Code Examples

**Python:**
```python
import os, httpx

with httpx.stream(
    "POST",
    "https://agent.tinyfish.ai/v1/automation/run-research",
    headers={"X-API-Key": os.environ["TINYFISH_API_KEY"]},
    json={"query": "Compare open-source LLM frameworks in 2026", "mode": "standard"},
    timeout=2700,
) as resp:
    resp.raise_for_status()
    for line in resp.iter_lines():
        if line.startswith("data: "):
            print(line[6:])
```

**TypeScript:**
```typescript
const response = await fetch("https://agent.tinyfish.ai/v1/automation/run-research", {
  method: "POST",
  headers: {
    "X-API-Key": process.env.TINYFISH_API_KEY!,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({ query: "Compare open-source LLM frameworks in 2026", mode: "standard" }),
});
for await (const chunk of response.body!) {
  process.stdout.write(new TextDecoder().decode(chunk));
}
```

**cURL:**
```bash
curl --no-buffer https://agent.tinyfish.ai/v1/automation/run-research \
  -H "X-API-Key: $TINYFISH_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare open-source LLM frameworks in 2026", "mode": "standard"}'
```

> **Warning:** Research runs can take several minutes. Set long timeouts (`timeout=2700`).

#### Rate Limits and Pricing

⚠️ **Unverified** — The error codes page references a daily cap (`DAILY_LIMIT_EXCEEDED`), but exact pricing per research run is not confirmed in public documentation. Check [tinyfish.ai/pricing](https://www.tinyfish.ai/pricing).

#### Estimated Setup Time: ~5 minutes

---

### 4.6 Monitor

#### Overview

Monitor checks a webpage or web topic on a recurring schedule and notifies you of changes.

- **Page Monitor** — Compares extracted content of a known URL between runs.
- **Topic Monitor** — Identifies new URLs from repeated search queries.

#### Pricing

**$0.005 per completed run** (failed runs are free). Daily ≈ $0.15/month; hourly ≈ $3.65/month.

#### Setup (UI)

1. Go to [agent.tinyfish.ai/monitor](https://agent.tinyfish.ai/monitor) → **New monitor**.
2. Choose **Page** or **Topic**.
3. Enter URL (Page) or search query (Topic).
4. Set schedule. (Topic Monitors: minimum 30-minute intervals.)
5. Optionally add a webhook URL or email address.

#### Limits

- Up to **50 Monitors** per account.
- Topic Monitors: minimum 30-minute schedule intervals.

#### Estimated Setup Time: ~5 minutes (UI)

---

### 4.7 MCP Integration

#### Overview

TinyFish exposes an MCP (Model Context Protocol) endpoint that allows AI assistants to call TinyFish tools directly.

**MCP endpoint:** `https://agent.tinyfish.ai/mcp`
**Auth:** OAuth 2.1 (browser flow) or API key (Command Code only)

#### Quick Install by Client

```bash
# Codex
codex mcp add tinyfish --url https://agent.tinyfish.ai/mcp

# Claude Code
npx -y install-mcp@latest https://agent.tinyfish.ai/mcp --client claude-code

# Cursor
npx -y install-mcp@latest https://agent.tinyfish.ai/mcp --client cursor

# Windsurf
npx -y install-mcp@latest https://agent.tinyfish.ai/mcp --client windsurf

# OpenCode
opencode mcp add tinyfish --url https://agent.tinyfish.ai/mcp

# Claude (one-tap in browser)
# https://claude.ai/directory/tinyfish

# ChatGPT (one-tap in browser)
# https://chatgpt.com/plugins/plugin_asdk_app_695325bae7348191b58ae9349a963d22
```

#### Available MCP Tools

| Tool | Description |
|------|-------------|
| `run_web_automation` | Execute multi-step automation (SSE streaming) |
| `run_web_automation_async` | Start automation, return run_id immediately |
| `get_run` | Retrieve run details by ID |
| `list_runs` | List runs with optional filtering |
| `cancel_run` | Cancel a run by ID |
| `batch_status` | Check status of up to 8 runs |
| `batch_cancel` | Cancel up to 8 runs |
| `search` | Web search with structured results |
| `get_search_usage` | List past search usage |
| `fetch_content` | Fetch and extract content from URLs |
| `list_fetch_usage` | List past fetch records |
| `create_browser_session` | Create a cloud CDP browser session |
| `list_browser_sessions` | List browser sessions |
| `close_browser_session` | Terminate a browser session |
| `get_wallet` | Read wallet balance and rates |
| `top_up_wallet` | Agent-initiated wallet top-up (MPP, rolling out) |

#### MCP Rates (same as REST)

| Tool | Rate |
|------|------|
| `search` | $0.00/request |
| `fetch_content` | $0.00/URL |
| `run_web_automation` | $0.016/step |
| `create_browser_session` | $0.002/browser-minute |

---

### 4.8 CLI

#### Overview

The TinyFish CLI lets you run automations, check status, and manage runs from the terminal without writing code.

#### Installation

```bash
npm install -g @tiny-fish/cli@latest
tinyfish --version
```

#### Authentication

```bash
# Interactive (opens browser)
tinyfish auth login

# CI/CD (pipe key directly)
echo $TINYFISH_API_KEY | tinyfish auth set

# Verify
tinyfish auth status
```

#### Key Commands

```bash
# Run an automation
tinyfish agent run "Extract product prices and return JSON" \
  --url https://scrapeme.live/shop --pretty

# Check wallet balance
tinyfish wallet status --pretty

# List recent runs
tinyfish runs list --pretty

# Cancel a run
tinyfish runs cancel <run_id>

# Connect to MCP clients
tinyfish connect command-code
```

#### Environment Variables

| Variable | Description |
|----------|-------------|
| `TINYFISH_API_KEY` | API key (takes priority over saved config) |
| `TINYFISH_DEBUG` | Set to `1` for debug output |
| `TINYFISH_NO_TELEMETRY` | Disable analytics |
| `TINYFISH_VAULT_TOKEN` | 1Password service account token |
| `TINYFISH_VAULT_CLIENT_SECRET` | Bitwarden client secret |
| `TINYFISH_VAULT_MASTER_PASSWORD` | Bitwarden master password |

#### Estimated Setup Time: ~3 minutes

---

### 4.9 Mako Model

> **⚠️ Unverified.** Mako is listed as a TinyFish product ("web-native model for live workflows") but no API reference, pricing, or integration documentation was found in the public docs index at the time of research. Verify at [tinyfish.ai/mako](https://www.tinyfish.ai/mako) or contact TinyFish directly.

---

### 4.10 TinyVault / Browser Context Profiles

#### Overview

**TinyVault** integrates your password manager (1Password, Bitwarden) so the Agent can log into websites without exposing credentials to the LLM.

**Browser Context Profiles** persist cookies and storage state across multiple runs, avoiding re-authentication every time.

#### Setup (Vault via CLI)

```bash
# Connect 1Password
tinyfish vault connection add --provider 1password

# Connect Bitwarden
tinyfish vault connection add --provider bitwarden --client-id YOUR_CLIENT_ID
```

Pass `use_vault: true` in any Agent API run:

```json
{
  "url": "https://app.example.com",
  "goal": "Summarize the account dashboard",
  "use_vault": true
}
```

#### Setup (Browser Context Profiles)

1. Create a profile via dashboard or REST API (`POST /v1/profiles`).
2. Start a setup session → receive `cdp_url`.
3. Connect Playwright to `cdp_url` and log in manually.
4. Save the session → profile captures cookies + storage.
5. Use the profile in future runs: `"use_profile": true, "profile_id": "prof_abc123"`.

#### Estimated Setup Time: ~15 minutes (including manual login step)

---

### 4.11 Webhooks

#### Overview

Add a `webhook_url` to any Agent run to receive HTTP POST notifications on run lifecycle events.

```json
{
  "url": "https://example.com",
  "goal": "...",
  "webhook_url": "https://yourapp.com/webhooks/tinyfish"
}
```

- `webhook_url` must use HTTPS.
- Validate webhook payloads using the `run_id` you started.

---

### 4.12 Agent Payments (Machine Payments Protocol)

#### Overview

**MPP** lets AI agents top up their own TinyFish wallet programmatically without human intervention. First call returns `402` with a payment challenge; retry with a payment credential to fund the wallet.

> **⚠️ Unverified for broad use.** MPP is rolling out gradually. Accounts outside the rollout will not see `top_up_wallet` in MCP tool lists. Check [docs.tinyfish.ai/agent-payments](https://docs.tinyfish.ai/agent-payments) for current availability.

---

## 5. Authentication and Authorization

### How Keys Are Issued

1. Sign in at [agent.tinyfish.ai](https://agent.tinyfish.ai).
2. Navigate to [agent.tinyfish.ai/api-keys](https://agent.tinyfish.ai/api-keys).
3. Click **Create API Key**. The key (format: `sk-tinyfish-...`) is shown **once only**.
4. Copy and store it immediately.

### Header Format

All REST API requests:
```http
X-API-Key: YOUR_API_KEY
```

MCP integrations use OAuth 2.1 (browser flow) instead of an API key.

### Key Rotation and Revocation

- Generate a new key any time on the API Keys page.
- Old keys are not automatically revoked when new ones are created — revoke manually.
- Use separate keys for development and production.
- Rotate keys after team-member changes.

### Secure Storage

**Never hardcode keys in source files.**

```bash
# Shell (add to .bashrc / .zshrc)
export TINYFISH_API_KEY="sk-tinyfish-YOUR_KEY"
```

```bash
# .env file (Node.js projects)
TINYFISH_API_KEY=sk-tinyfish-YOUR_KEY
```

```bash
# .gitignore
.env
.env.local
```

### Auth Setup by Language

**Python:**
```python
import os
from dotenv import load_dotenv
from tinyfish import TinyFish

load_dotenv()
client = TinyFish()  # reads TINYFISH_API_KEY automatically
```

**TypeScript / JavaScript:**
```typescript
import { TinyFish } from "@tiny-fish/sdk";
// reads TINYFISH_API_KEY from process.env
const client = new TinyFish();
```

**cURL:**
```bash
curl -H "X-API-Key: $TINYFISH_API_KEY" \
     -H "Content-Type: application/json" \
     -X POST https://agent.tinyfish.ai/v1/automation/run-sse \
     -d '{"url": "...", "goal": "..."}'
```

---

## 6. Integration Guide

### Recommended Project Structure

**Python:**
```
my-hackathon-project/
├── .env                     # API keys — git-ignored
├── .gitignore               # includes .env
├── .venv/                   # virtual environment — git-ignored
├── requirements.txt
├── main.py
└── agents/
    ├── search_agent.py
    ├── fetch_agent.py
    └── automation_agent.py
```

**Node.js / TypeScript:**
```
my-hackathon-project/
├── .env
├── .gitignore
├── package.json             # "type": "module" required
├── tsconfig.json
├── src/
│   ├── index.ts
│   ├── search.ts
│   ├── fetch.ts
│   └── automation.ts
└── README.md
```

### Environment Setup

**Python:**
```bash
python3 -m venv .venv
source .venv/bin/activate      # macOS/Linux
# .venv\Scripts\activate       # Windows
pip install tinyfish python-dotenv
```

**Node.js:**
```bash
npm init -y
npm pkg set type=module
npm i @tiny-fish/sdk dotenv
```

### End-to-End Example: Competitor Pricing Pipeline

```python
# competitor_pricing.py
import os, json
from tinyfish import TinyFish, CompleteEvent
from dotenv import load_dotenv

load_dotenv()
client = TinyFish()

def competitor_pricing_pipeline(topic: str) -> list[dict]:
    """Search → Fetch → Extract structured pricing for a given topic."""

    # 1. Search for relevant pages
    print(f"[1/3] Searching: {topic}")
    search_results = client.search.query(
        query=f"{topic} pricing plans",
        domain_type="web",
        recency_minutes=43200,  # last 30 days
    )
    urls = [r.url for r in search_results.results[:3]]

    # 2. Batch-fetch all URLs
    print("[2/3] Fetching content...")
    fetch_result = client.fetch.get_contents(urls=urls, format="markdown", ttl=3600)
    pages = fetch_result.results
    if fetch_result.errors:
        print(f"      Warning: {len(fetch_result.errors)} URLs failed")

    # 3. Run Agent on each page to extract pricing
    print("[3/3] Extracting pricing via Agent...")
    all_pricing = []
    for page in pages:
        with client.agent.stream(
            url=page.url,
            goal=(
                "Find the pricing section. Extract all plan names and prices. "
                'Return JSON: {"plans": [{"name": "string", "price": "string"}]}'
            ),
        ) as stream:
            for event in stream:
                if isinstance(event, CompleteEvent) and event.result:
                    all_pricing.append({"source": page.url, "pricing": event.result})
    return all_pricing

if __name__ == "__main__":
    results = competitor_pricing_pipeline("project management software")
    print(json.dumps(results, indent=2))
```

### Integrating with LangChain (Python)

```python
from langchain.tools import tool
from tinyfish import TinyFish

client = TinyFish()

@tool
def web_search(query: str) -> str:
    """Search the web and return top results as plain text."""
    resp = client.search.query(query=query)
    return "\n".join(
        f"{r.position}. {r.title}: {r.url}" for r in resp.results[:5]
    )

@tool
def fetch_page(url: str) -> str:
    """Fetch and extract clean text from a URL."""
    result = client.fetch.get_contents(urls=[url], format="markdown")
    if result.results:
        return result.results[0].text[:4000]  # truncate for context window
    return "Failed to fetch page."
```

### Testing and Debugging Tips

- Enable CLI debug mode: `TINYFISH_DEBUG=1 tinyfish agent run ...`
- Use `--pretty` flag for human-readable CLI output.
- For Agent runs, watch the browser live by copying the `streaming_url` from the `STREAMING_URL` SSE event into the TinyFish dashboard.
- Poll `GET /v1/runs/{run_id}` for async run state.
- A 200 HTTP response from Fetch does NOT mean all URLs succeeded — always check `errors[]`.
- Test authentication quickly with a free Search call before debugging paid services.

---

## 7. Best Practices for Performance and Reliability

### Batching

- **Fetch:** Send up to 10 URLs per request — they process in parallel.
- **Agent batch:** Use `POST /v1/automation/run-batch` (max 100 runs per request; returns run_ids immediately).
- **MCP:** Use `batch_status` to poll multiple run IDs simultaneously.

### Caching

- Use `ttl` in Fetch requests to reuse cached content (saves quota and reduces latency).
- Set `ttl: 0` only when you specifically need fresh data.

### Cost Management

- Monitor wallet balance: `client.wallet.get()` or `tinyfish wallet status`.
- Set `agent_config.max_steps` (Beta) to cap per-run costs.
- Set `agent_config.max_duration_seconds` to prevent runaway runs.
- Use Search and Fetch (free) wherever you don't need interactive browser automation.

### Retry Strategy

```python
import time, random
from tinyfish import TinyFish, RateLimitError, InternalServerError

client = TinyFish()

def with_exponential_backoff(fn, max_retries=5):
    """Call fn() with exponential backoff on rate limits and server errors."""
    for attempt in range(max_retries):
        try:
            return fn()
        except RateLimitError as e:
            if attempt == max_retries - 1:
                raise
            wait = getattr(e, "retry_after", None) or (2 ** attempt + random.uniform(0, 1))
            print(f"Rate limited. Retrying in {wait:.1f}s...")
            time.sleep(wait)
        except InternalServerError:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
```

### Graceful Degradation for Demos

```python
def safe_search(query: str, fallback: list = None):
    """Return search results, or a static fallback if the API is unavailable."""
    try:
        return client.search.query(query=query).results
    except Exception as e:
        print(f"[Warn] Search failed: {e}. Using fallback.")
        return fallback or []

def safe_fetch(url: str, fallback: str = "Content unavailable."):
    """Return page text, or a fallback string if fetch fails."""
    try:
        result = client.fetch.get_contents(urls=[url])
        if result.results:
            return result.results[0].text
    except Exception as e:
        print(f"[Warn] Fetch failed for {url}: {e}")
    return fallback
```

### Anti-Bot Handling

- Switch to `browser_profile: "stealth"` when you see `SITE_BLOCKED` errors.
- Use `proxy_config` with different country codes to bypass geo-blocks.
- Use **Browser Context Profiles** to avoid re-triggering login checks.
- See the [Anti-Bot Guide](https://docs.tinyfish.ai/anti-bot-guide) for site-specific advice.

---

## 8. Credits, Attribution, and Licensing

### Free Tier and New Account Credits

| Item | Amount | Notes |
|------|--------|-------|
| New account Wallet credit | **$8.00** | Applied automatically; no card required |
| Search free allowance | **12,000 req/day** | Resets 00:00 UTC; no wallet draw |
| Fetch free allowance | **1,000 URLs/day** | Resets 00:00 UTC; no wallet draw |
| Minimum wallet top-up | **$10.00** | Required to continue Agent/Browser after $8 is spent |

> **Note:** TinyFish does not advertise hackathon-specific credit allocations or partner deals in public documentation as of the research date. If your hackathon has a TinyFish partnership, verify any sponsor credits with the hackathon organizers or TinyFish directly at their [contact page](https://www.tinyfish.ai).

### Attribution Requirements

⚠️ **Unverified** — No specific attribution, branding, or credit-line requirements for hackathon projects were found in public documentation. Check the official Terms of Service and with your hackathon organizers.

### Terms of Service Points

Key points relevant to hackathon submissions (**verify against the current ToS**):

- TinyFish is a commercial service — do not re-distribute TinyFish infrastructure as your own product.
- Do not commit API keys to public repositories.
- Usage must comply with TinyFish's acceptable use policy.
- Automated access to third-party websites must respect those sites' terms of service.

---

## 9. Hackathon Timeline Plan

### Suggested Schedule (24-Hour Hackathon)

| Time | Activity | Services | Est. Duration |
|------|---------|---------|---------------|
| **Hour 0:00–0:30** | Account setup, API key, SDK install | Auth | 30 min |
| **Hour 0:30–1:00** | Hello World: Search + Fetch | Search, Fetch | 30 min |
| **Hour 1:00–2:00** | Core feature: Agent automation | Agent API | 60 min |
| **Hour 2:00–4:00** | Build main project features | Search + Fetch + Agent | 120 min |
| **Hour 4:00–6:00** | Add Browser sessions (if needed) | Browser API | 120 min |
| **Hour 6:00–8:00** | Integrate with LLM / framework | Agent + LLM tooling | 120 min |
| **Hour 8:00–10:00** | Add structured output schemas | Agent `output_schema` | 120 min |
| **Hour 10:00–14:00** | Polish demo, error handling, fallbacks | All | 4 hr |
| **Hour 14:00–14:30** | Set up Monitor (if needed) | Monitor | 30 min |
| **Hour 14:30–22:00** | Testing, bug fixing | All | 7.5 hr |
| **Hour 22:00–24:00** | Pre-submission checklist, README | — | 2 hr |

### Per-Service Integration Time Estimates

| Service | Setup | Working Integration | Assumption |
|---------|-------|---------------------|------------|
| Search | 2 min | 15 min | SDK installed, key set |
| Fetch | 2 min | 15 min | SDK installed, key set |
| Agent (sync) | 5 min | 30 min | Goal crafting included |
| Agent (SSE) | 5 min | 45 min | Stream handling included |
| Browser + Playwright | 10 min | 60 min | Playwright install + connect |
| Research API | 5 min | 30 min | SSE parsing included |
| Monitor | 5 min | 15 min | UI setup |
| MCP integration | 5 min | 15 min | Client supports MCP |
| Vault / Profiles | 15 min | 60 min | Manual login step required |

### Pre-Submission Checklist

```
[ ] Working demo runs end-to-end without errors
[ ] All API keys removed from source code
[ ] .env file in .gitignore and NOT committed
[ ] No credentials or personal data in repository
[ ] README.md explains setup steps (including TINYFISH_API_KEY env var)
[ ] Error handling for API failures (fallbacks for demo stability)
[ ] Wallet balance checked — enough funds for live demo runs
[ ] Attribution included (per ToS)
[ ] All dependencies listed in requirements.txt / package.json
[ ] Demo video / screenshots captured
```

---

## 10. Example Project Ideas

### Project 1 — Real-Time Competitive Intelligence Dashboard

**What it does:** Monitors competitor websites for pricing changes, new features, and blog posts. Sends Slack/email alerts when changes are detected.

**Architecture:**
1. **Monitor API** — Page Monitors on competitor pricing pages; Topic Monitors on competitor blog topics.
2. **Fetch API** — Fetch updated pages on change detection.
3. **Agent API** — Extract structured pricing/feature data from changed pages.
4. **Webhook** — Receive Monitor notifications and trigger downstream processing.
5. **LLM** — Summarize changes and generate alert messages.

**Services:** Search, Fetch, Agent, Monitor, Webhooks

---

### Project 2 — Autonomous Research Assistant

**What it does:** Takes a research question, finds relevant sources, fetches full content, and synthesizes a cited report.

**Architecture:**
1. **Search API** — Find top sources (web + research_paper domain types).
2. **Fetch API** — Batch-fetch all relevant URLs.
3. **Research API** — Run deep synthesis.
4. **LLM** — Final formatting and presentation layer.
5. **MCP** — Allow the user to interact via Claude or ChatGPT directly.

**Services:** Search, Fetch, Research API, MCP

---

### Project 3 — Multi-Site Product Price Comparison

**What it does:** Given a product query, finds the top sellers, scrapes prices and availability, and returns a ranked comparison table.

**Architecture:**
1. **Search API** — Find product pages across multiple retailers.
2. **Agent API** (batch async) — Launch concurrent Agent runs extracting structured price data from each site.
3. **Structured Output** — Use `output_schema` for consistent `{name, price, availability, url}` JSON.
4. **Frontend** — Display ranked results in a simple table or Streamlit app.

**Services:** Search, Agent API (batch + output_schema)

---

### Project 4 — AI-Powered Form Automation Bot

**What it does:** Automates repetitive form submissions (job applications, event registrations) using natural-language goals and saved credentials.

**Architecture:**
1. **Vault** — Secure credential storage for site logins.
2. **Browser Context Profiles** — Persist logged-in state across runs.
3. **Agent API** — Submit forms with goal-based instructions.
4. **Webhook** — Confirm completion or flag failures.

**Services:** Agent API, Vault, Browser Context Profiles, Webhooks

---

### Project 5 — News Briefing Agent (MCP-Powered)

**What it does:** A Claude- or ChatGPT-powered assistant that searches for, fetches, and summarizes today's top news on any topic, delivered on demand.

**Architecture:**
1. **MCP** — Connect TinyFish to Claude or ChatGPT (5-minute setup).
2. **`search` tool** — Find today's top news articles (`domain_type: "news"`, `recency_minutes: 1440`).
3. **`fetch_content` tool** — Fetch full article text from top results.
4. **Assistant LLM** — Synthesize a briefing and answer follow-up questions.

**Services:** MCP (search + fetch_content tools)

---

## 11. Troubleshooting and FAQ

### Common Problems and Fixes

**Q: My API key doesn't work.**
- Run `echo $TINYFISH_API_KEY` — if empty, re-run the `export` command.
- The key must start with `sk-tinyfish-`. If you lost it, generate a new one on the [API Keys page](https://agent.tinyfish.ai/api-keys) — old keys cannot be recovered.
- Ensure no extra whitespace around the key in your env file.

**Q: I get `402 INSUFFICIENT_CREDITS` on Agent or Browser.**
- Your wallet balance is zero or negative.
- Go to [agent.tinyfish.ai/wallet](https://agent.tinyfish.ai/wallet) and add funds (minimum $10).
- Search and Fetch continue working even at $0 balance (within their daily limits).

**Q: I get `429 RATE_LIMIT_EXCEEDED` on Agent.**
- This means your pending-run concurrency cap (default 2) is hit.
- Wait for existing runs to complete before starting new ones.
- Check `GET /v1/runs` for runs still in `RUNNING` or `PENDING` state.

**Q: My Agent run returns `SITE_BLOCKED`.**
- The target site detected automation. Switch to `browser_profile: "stealth"`.
- Add `proxy_config` to route through a different IP or country.
- Consider using a warmed Browser Context Profile.

**Q: `pip install tinyfish` fails on macOS.**
- Homebrew Python 3.11+ blocks system-wide `pip` (PEP 668).
- Create a virtual environment first: `python3 -m venv .venv && source .venv/bin/activate`, then `pip install tinyfish`.

**Q: TypeScript fails with `ERR_PACKAGE_PATH_NOT_EXPORTED`.**
- The SDK is ESM-only. Add `"type": "module"` to `package.json`: `npm pkg set type=module`.

**Q: Browser API session creation takes forever.**
- Session creation takes 10–30 seconds normally.
- Set your HTTP client timeout to at least 60 seconds.

**Q: My SSE stream disconnects mid-run.**
- SSE does not support `Last-Event-ID` reconnection for Agent API.
- Fall back to polling: `GET /v1/runs/{run_id}` every 5 seconds until terminal status.

**Q: How do I know if my account is on wallet billing or legacy credits?**
- Call `GET /v1/wallet`. A `404 FEATURE_NOT_AVAILABLE` response means you're on the legacy plan.

### Where to Get Help

| Resource | URL |
|----------|-----|
| Official Docs | [docs.tinyfish.ai](https://docs.tinyfish.ai) |
| Quickstart | [docs.tinyfish.ai/quick-start](https://docs.tinyfish.ai/quick-start) |
| Cookbook (GitHub) | [github.com/tinyfish-io/tinyfish-cookbook](https://github.com/tinyfish-io/tinyfish-cookbook) |
| Discord Community | [discord.com/invite/tinyfish](https://discord.com/invite/tinyfish) |
| Status Page | [agent.tinyfish.ai/status](https://agent.tinyfish.ai/status) |
| Error Codes Reference | [docs.tinyfish.ai/error-codes](https://docs.tinyfish.ai/error-codes) |
| X / Twitter | [@Tiny_Fish](https://x.com/Tiny_Fish) |

---

## 12. Disclaimers and Constraints

1. **Unofficial guide.** This document was produced by an independent AI researcher, not by Tiny Fish Inc. It may contain inaccuracies.

2. **Verify before relying.** TinyFish's APIs, pricing, rate limits, terms, and SDK versions can change at any time. Always verify against the current official documentation at [docs.tinyfish.ai](https://docs.tinyfish.ai).

3. **Research date.** All information was gathered on **October 12, 2026**. Details may be outdated.

4. **Unverified items.** The following items were not confirmed from official public documentation and are flagged with ⚠️:
   - **Mako model:** No API reference found in public docs.
   - **Hackathon-specific credits:** Not confirmed from public docs.
   - **Agent Payments (MPP):** Rolling out gradually; not available to all accounts.
   - `agent_config.mode: "strict"` and `agent_config.max_steps`: Beta-gated.
   - **Highlights in Fetch API:** Beta, requires account enablement.
   - **Exact Research API pricing per run:** Not found in public documentation.
   - **Branding/attribution requirements:** Not documented publicly.

5. **Third-party sites.** Agent and Browser API usage against third-party websites must respect those websites' terms of service and applicable laws. Compliance is the developer's responsibility.

6. **No warranty.** The author makes no warranties about the accuracy or completeness of this guide. Use at your own risk.

---

## 13. Appendix

### A. Glossary

| Term | Definition |
|------|------------|
| **Agent API** | TinyFish service that executes natural-language goals on real websites |
| **Browser API** | TinyFish service that creates cloud CDP browser sessions for Playwright/Puppeteer |
| **Browser Context Profile** | Persisted browser state (cookies, storage) reusable across multiple Agent runs |
| **Browser Profile** | Runtime mode for Agent runs: `lite` (standard) or `stealth` (anti-bot bypass) |
| **CDP** | Chrome DevTools Protocol — WebSocket API for controlling Chromium |
| **EVA** | TinyFish's internal web agent model (referenced in docs; not a public-facing name) |
| **Fetch API** | TinyFish service that extracts clean text from URLs |
| **Goal** | Plain-English instruction passed to the Agent API in the `goal` field |
| **Mako** | TinyFish's web-native model product (API unverified at research date) |
| **MCP** | Model Context Protocol — standard for LLM tool integration |
| **Monitor** | TinyFish service for scheduled page/topic change detection |
| **MPP** | Machine Payments Protocol — enables AI agents to self-fund TinyFish wallets |
| **Research API** | TinyFish service that produces cited multi-source research reports |
| **Run** | A single Agent API execution unit with its own `run_id` |
| **Search API** | TinyFish service for structured web, news, and academic search |
| **SSE** | Server-Sent Events — HTTP streaming format used by Agent and Research APIs |
| **Step** | One agent action/navigation cycle; billing unit for Agent API ($0.016/step) |
| **Vault** | TinyFish integration with password managers (1Password, Bitwarden) for site login |
| **Wallet** | Prepaid credit balance on a TinyFish account used for Agent and Browser billing |

---

### B. Full Source List

| # | URL | Content | Access Date |
|---|-----|---------|-------------|
| 1 | https://www.tinyfish.ai/ | Homepage, product descriptions, FAQ, org JSON-LD | Oct 12, 2026 |
| 2 | https://www.tinyfish.ai/pricing | Pricing page with embedded JSON-LD pricing data | Oct 12, 2026 |
| 3 | https://docs.tinyfish.ai/ | Documentation portal main page | Oct 12, 2026 |
| 4 | https://docs.tinyfish.ai/llms.txt | Complete documentation index (machine-readable) | Oct 12, 2026 |
| 5 | https://docs.tinyfish.ai/quick-start.md | Quickstart guide | Oct 12, 2026 |
| 6 | https://docs.tinyfish.ai/authentication.md | Authentication reference | Oct 12, 2026 |
| 7 | https://docs.tinyfish.ai/agent-api/index.md | Agent API overview | Oct 12, 2026 |
| 8 | https://docs.tinyfish.ai/agent-api/reference.md | Agent API technical reference | Oct 12, 2026 |
| 9 | https://docs.tinyfish.ai/search-api/index.md | Search API overview | Oct 12, 2026 |
| 10 | https://docs.tinyfish.ai/search-api/reference.md | Search API parameter & response reference | Oct 12, 2026 |
| 11 | https://docs.tinyfish.ai/fetch-api/index.md | Fetch API overview | Oct 12, 2026 |
| 12 | https://docs.tinyfish.ai/browser-api/index.md | Browser API overview | Oct 12, 2026 |
| 13 | https://docs.tinyfish.ai/research-api/index.md | Research API overview | Oct 12, 2026 |
| 14 | https://docs.tinyfish.ai/monitor/index.md | Monitor overview | Oct 12, 2026 |
| 15 | https://docs.tinyfish.ai/error-codes.md | Complete error code reference | Oct 12, 2026 |
| 16 | https://docs.tinyfish.ai/mcp-integration/index.md | MCP integration guide | Oct 12, 2026 |
| 17 | https://docs.tinyfish.ai/cli/index.md | CLI reference | Oct 12, 2026 |
| 18 | https://www.tinyfish.ai/mako | Mako product page | Oct 12, 2026 |
| 19 | Web search: "Tinyfish.ai API documentation services features 2024 2025" | Secondary cross-check | Oct 12, 2026 |
| 20 | Web search: "Tinyfish.ai pricing plans credits rate limits free tier" | Secondary pricing cross-check | Oct 12, 2026 |

---

### C. `.env.example` Template

```bash
# TinyFish API Key — get yours at https://agent.tinyfish.ai/api-keys
# Key is shown only once at creation; store it securely.
TINYFISH_API_KEY=sk-tinyfish-YOUR_KEY_HERE

# Optional: Vault integration (1Password)
# TINYFISH_VAULT_TOKEN=ops-YOUR_1PASSWORD_SERVICE_ACCOUNT_TOKEN

# Optional: Vault integration (Bitwarden)
# TINYFISH_VAULT_CLIENT_SECRET=YOUR_BITWARDEN_CLIENT_SECRET
# TINYFISH_VAULT_MASTER_PASSWORD=YOUR_BITWARDEN_MASTER_PASSWORD

# Optional: CLI debug mode
# TINYFISH_DEBUG=1

# Optional: Disable CLI telemetry
# TINYFISH_NO_TELEMETRY=1

# Your application settings (examples)
# APP_PORT=3000
# DATABASE_URL=sqlite:///app.db
```

---

### D. Quick-Reference Cheat Sheet

```
═══════════════════════════════════════════════════════════════
                    TINYFISH CHEAT SHEET
═══════════════════════════════════════════════════════════════

── SETUP ───────────────────────────────────────────────────────
Sign up:   https://agent.tinyfish.ai/sign-up
API Keys:  https://agent.tinyfish.ai/api-keys
Wallet:    https://agent.tinyfish.ai/wallet
Docs:      https://docs.tinyfish.ai
Discord:   https://discord.com/invite/tinyfish

export TINYFISH_API_KEY="sk-tinyfish-..."

pip install tinyfish                           # Python SDK
npm i @tiny-fish/sdk && npm pkg set type=module # Node SDK
npm install -g @tiny-fish/cli                  # CLI

── AUTH HEADER ─────────────────────────────────────────────────
X-API-Key: $TINYFISH_API_KEY

── PRICING ─────────────────────────────────────────────────────
Search:  FREE  — 12,000 req/day  (30 req/min limit)
Fetch:   FREE  — 1,000 URLs/day  (150 URLs/min limit)
Monitor: $0.005 / completed run
Agent:   $0.016 / step           (2 concurrent runs default)
Browser: $0.002 / browser-minute (5 concurrent sessions default)
New account: $8.00 free wallet credit | Min top-up: $10.00

── ENDPOINTS ───────────────────────────────────────────────────
Search:   GET  https://api.search.tinyfish.ai?query=...
Fetch:    POST https://api.fetch.tinyfish.ai
Agent:    POST https://agent.tinyfish.ai/v1/automation/run
          POST https://agent.tinyfish.ai/v1/automation/run-async
          POST https://agent.tinyfish.ai/v1/automation/run-sse
Browser:  POST https://api.browser.tinyfish.ai
Research: POST https://agent.tinyfish.ai/v1/automation/run-research
Wallet:   GET  https://agent.tinyfish.ai/v1/wallet
Run:      GET  https://agent.tinyfish.ai/v1/runs/{id}
Cancel:   POST https://agent.tinyfish.ai/v1/runs/{id}/cancel
MCP:           https://agent.tinyfish.ai/mcp

── PYTHON SDK ──────────────────────────────────────────────────
from tinyfish import TinyFish, CompleteEvent
client = TinyFish()  # reads TINYFISH_API_KEY from env

# Search
resp = client.search.query(query="...")

# Fetch
resp = client.fetch.get_contents(urls=["https://..."])

# Agent (sync)
resp = client.agent.run(url="...", goal="...")

# Agent (stream)
with client.agent.stream(url="...", goal="...") as s:
    for event in s:
        if isinstance(event, CompleteEvent):
            print(event.result_json)

# Browser
sess = client.browser.sessions.create(url="...")
# → use sess.cdp_url with Playwright connect_over_cdp()

# Wallet
w = client.wallet.get()
print(w.available_balance, w.currency)

── TYPESCRIPT SDK ──────────────────────────────────────────────
import { TinyFish } from "@tiny-fish/sdk";
const client = new TinyFish();

const r  = await client.search.query({ query: "..." });
const r2 = await client.fetch.getContents({ urls: ["..."] });
const s  = await client.agent.stream({ url: "...", goal: "..." });
for await (const e of s) {
  if (e.type === "COMPLETE") console.log(e.result);
}
const sess = await client.browser.sessions.create({ url: "..." });

── CLI ─────────────────────────────────────────────────────────
tinyfish auth login
tinyfish agent run "goal text" --url https://... --pretty
tinyfish wallet status --pretty
tinyfish runs list --pretty
tinyfish runs cancel <run_id>

── ERROR QUICK-FIX ─────────────────────────────────────────────
401 MISSING_API_KEY      → Add X-API-Key header
401 INVALID_API_KEY      → Regenerate key at api-keys page
402 INSUFFICIENT_CREDITS → Add $10+ at wallet page
403 FORBIDDEN            → Check credits / plan entitlements
429 RATE_LIMIT_EXCEEDED  → Backoff; wait for run slots free up
SITE_BLOCKED             → Use browser_profile: "stealth"
TASK_FAILED              → Refine goal; add auth or context
SSE disconnect           → Poll GET /v1/runs/{id} until terminal
pip install fails macOS  → Create venv first; pip inside venv
tsx ERR_PACKAGE_PATH     → npm pkg set type=module

═══════════════════════════════════════════════════════════════
```

---

*TinyFish.ai Hackathon Developer Guide v1.0 — Researched October 12, 2026*
*Unofficial. Not produced by Tiny Fish Inc. Verify all details at docs.tinyfish.ai.*
