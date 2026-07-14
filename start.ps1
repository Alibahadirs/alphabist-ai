if (-Not (Test-Path ".venv")) {
    py -m venv .venv
}

Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run main.py