Write-Host "Activating Python virtual environment..." -ForegcontainerroundColor Cyan
# Activate the virtual environment
& .\.venv_\Scripts\Activate.ps1

Write-Host "Clearing streamlit cache..." -ForegroundColor Cyan
python -m streamlit cache clear

Write-Host "Running app.py..." -ForegroundColor Cyan
python -m streamlit run app.py
