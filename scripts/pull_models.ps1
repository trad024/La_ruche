# Pull all Phase-1 models sequentially (run once, can be interrupted and re-run)
# Ollama skips models already downloaded.
#
# Usage: powershell -ExecutionPolicy Bypass -File scripts\pull_models.ps1

$models = @(
    "qwen2.5:3b",           # already pulled, will skip instantly
    "qwen2.5:7b",           # main conversational — 4.7 GB
    "llama3.2:3b",          # already pulled, will skip instantly
    "phi3.5",               # US model (Microsoft) — ~2.2 GB
    "mistral:7b-instruct",  # French model (Mistral) — ~4.1 GB
    "deepseek-r1:7b",       # reasoning model — ~4.7 GB  (optional, pull last)
    "nomic-embed-text"      # embeddings — already pulled, will skip instantly
)

foreach ($m in $models) {
    Write-Host "`n==> Pulling $m ..." -ForegroundColor Cyan
    ollama pull $m
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: $m" -ForegroundColor Red
    } else {
        Write-Host "OK: $m" -ForegroundColor Green
    }
}

Write-Host "`nAll models ready. Run the benchmark:" -ForegroundColor Yellow
Write-Host "  uv run --package eval python eval/src/eval/bench_models.py" -ForegroundColor White
