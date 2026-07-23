from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_start_script_uses_virtual_environment_python():
    content = (PROJECT_ROOT / "start.ps1").read_text(encoding="utf-8")

    assert '".venv\\Scripts\\python.exe"' in content
    assert "& $VenvPython -m pip install" in content
    assert "& $VenvPython -m streamlit run" in content
    assert "py -m streamlit" not in content
    assert "\nstreamlit run" not in content


def test_start_script_runs_preflight_before_streamlit():
    content = (PROJECT_ROOT / "start.ps1").read_text(encoding="utf-8")

    preflight_position = content.index("-m app.core.preflight")
    streamlit_position = content.index("-m streamlit run")

    assert preflight_position < streamlit_position
    assert "server.headless true" in content


def test_start_script_avoids_duplicate_server_processes():
    content = (PROJECT_ROOT / "start.ps1").read_text(encoding="utf-8")

    assert "http://localhost:8501/_stcore/health" in content
    assert "AlphaBIST AI zaten çalışıyor" in content
    assert "exit 0" in content


def test_start_script_caches_requirements_installation():
    content = (PROJECT_ROOT / "start.ps1").read_text(encoding="utf-8")

    assert "Get-FileHash" in content
    assert ".requirements.sha256" in content
    assert "$DependenciesReady" in content
