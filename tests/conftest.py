"""Shared pytest fixtures for the white-noise skill test suite."""
import importlib.util
import sys
import threading
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_INIT_PATH = Path(__file__).resolve().parents[1] / "__init__.py"
_spec = importlib.util.spec_from_file_location("whitenoise_skill", _INIT_PATH)
_module = importlib.util.module_from_spec(_spec)
sys.modules["whitenoise_skill"] = _module
_spec.loader.exec_module(_module)

WhiteNoise = _module.WhiteNoise


@pytest.fixture
def skill(monkeypatch):
    s = WhiteNoise.__new__(WhiteNoise)
    s.log = MagicMock()
    s.skill_id = "ovos-skill-white-noise.test"
    s.status = MagicMock()
    s._bus = MagicMock()
    monkeypatch.setattr(WhiteNoise, "lang", "en-us", raising=False)
    s.res_dir = str(Path(__file__).resolve().parents[1])
    s._lang_resources = {}
    s._noise_stop = threading.Event()
    s._voc_cache = {}  # needed by voc_list(), bypassed by __new__()
    s.skill_icon = ""
    s._thread = None
    s._last_noise_type = None
    yield s
    s._stop()
