$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$dashboardPath = Join-Path $projectRoot "dashboard.py"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Project environment not found. Create .venv and install requirements first."
}

& $pythonPath -m streamlit run $dashboardPath @args

