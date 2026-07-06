Write-Host "Activating Python virtual environment..." -ForegcontainerroundColor Cyan
# Activate the virtual environment
<<<<<<< HEAD
& .\.venv_\Scripts\Activate.ps1
=======
& .\.venv\Scripts\Activate.ps1
>>>>>>> 07eef9d1562d7ccb8b67f11a28953febfcf60431

Write-Host "Clearing streamlit cache..." -ForegroundColor Cyan
python -m streamlit cache clear

Write-Host "Running app.py..." -ForegroundColor Cyan
python -m streamlit run app.py
