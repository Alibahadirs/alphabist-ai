if (-Not (Test-Path ".venv")) {
    py -m venv .venv
}

Set-ExecutionPolicy -Scope Process Bypass -Force
& ".\.venv\Scripts\Activate.ps1"

py -m pip install --upgrade pip
py -m pip install -r requirements.txt
py -m streamlit run main.py