# AlphaBIST AI MVP

BIST hisseleri için Alpha Score, şirket kaydı ve gecikmeli Yahoo Finance piyasa verisini tek ekranda birleştiren Streamlit uygulaması.

## Windows kurulumu

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run main.py
```

## Test

```powershell
pytest -q
```

Yahoo Finance verileri gecikmeli olabilir.
