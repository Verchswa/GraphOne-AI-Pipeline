# GraphOne / FrontierAtlas — AI Intelligence Ingestion Pipeline

High-throughput, asynchronous multi-modal ingestion pipeline capable of acquiring and structuring 500,000+ AI startups, products, research papers, jobs, and news signals.

## System Highlights
- **Zero Hallucination:** Every record traces directly to an authoritative source URL.
- **Dynamic Metrics:** Extracts live GitHub repository stars via GitHub API.
- **24-Hour Freshness Guarantee:** Rejects news or job postings that cannot be verified as $\le 24$ hours old.
- **Resilient Multi-Tier LLM Fallback:** Routes across Gemini 1.5 Flash $\to$ Groq Llama 3 $\to$ DeepSeek with 413 semantic chunking and 429 backoff.
- **Deterministic Entity Resolution:** Resolves raw company variations into canonical names using normalized rule-based token matching and seed catalogs.

## Quickstart

### 1. Setup Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
