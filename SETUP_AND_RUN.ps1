$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Installing project requirements..." -ForegroundColor Cyan
python -m pip install -r requirements.txt

Write-Host "Running pre-submission smoke test..." -ForegroundColor Cyan
python pre_submission_check.py

Write-Host "Starting Digital Wellness Analyzer..." -ForegroundColor Green
python app.py
