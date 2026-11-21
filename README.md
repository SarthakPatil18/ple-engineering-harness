# ple-engineering-harness

PLE (Physical-Engineering's Last Exam) agent harness submission.

## Structure

| File | Purpose |
|---|---|
| `submission.yaml` | Build/serve config; declares `model_api: gemini/gemini-3.8-flash` |
| `serve.py` | WebSocket server entrypoint on `$PORT` |
| `harness.py` | Agent loop: model + bash/read_file/write_file tools, retries, wrap-up |
| `taskbridge.py` | PLE serve protocol implementation (session, exec, read_file, write_file) |
| `requirements.txt` | Python dependencies (openai, websockets) |
| `LICENSE` | Apache-2.0 |
| `artifacts/` | Dev-set outputs from `uv run python eval/run.py` (committed) |
| `figures/` | Writeup figures: architecture.png, score_vs_cost.png, failure_breakdown.png |

## Local development

```bash
# Install dependencies
uv venv --python 3.12 .venv
uv pip install -r requirements.txt

# Validate submission.yaml (no Docker needed)
uv run python -m kit validate ../ple-engineering-harness

# Run dev set and generate artifacts (needs Docker)
uv run python eval/run.py ../ple-engineering-harness

# Check entry is ready to submit (needs Docker)
uv run python -m kit check ../ple-engineering-harness
```

## Submission

- GitHub repo: https://github.com/SarthakPatil18/ple-engineering-harness
- Commit SHA: `fd8df1defcb5b59e67adb24e05feed9b994a1fbf`
- Kaggle Writeup: Google Doc `1oMfxgyuBtBN6SsMWXI9q4BapiMJpBXUqDhGdm4Ag-pk`
- Deadline: January 5, 2027 (11:59 PM UTC)
