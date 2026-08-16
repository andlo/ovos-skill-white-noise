"""Tests for alias resolution and intent handlers - start/stop tests
use a monkeypatched short CLIP_DURATION_SECONDS so the real background
thread finishes quickly, same real-timing-not-mocked approach as
ovos-skill-metronome/ovos-skill-rhythm-box."""
import time
from unittest.mock import MagicMock

import pytest


def test_resolve_noise_exact_match(skill):
    assert skill._resolve_noise("white", "en-us") == "white"
    assert skill._resolve_noise("brun", "da-dk") == "brown"


def test_resolve_noise_no_fuzzy_match(skill):
    assert skill._resolve_noise("whitish", "en-us") is None


def test_resolve_noise_unknown_returns_none(skill):
    assert skill._resolve_noise("rain", "en-us") is None


def test_start_and_stop(skill, monkeypatch):
    import whitenoise_skill as m
    monkeypatch.setattr(m, "CLIP_DURATION_SECONDS", 0.05)
    skill.play_audio = MagicMock()
    skill._start("white")
    assert skill._is_running()
    time.sleep(0.02)
    skill._stop()
    assert not skill._is_running()
    skill.play_audio.assert_called()


def test_stop_prevents_further_loop_iterations(skill, monkeypatch):
    """Confirms stop() actually halts re-triggering, not just that
    the thread object stops existing - counts play_audio() calls
    before and after stop() to make sure no more happen."""
    import whitenoise_skill as m
    monkeypatch.setattr(m, "CLIP_DURATION_SECONDS", 0.03)
    skill.play_audio = MagicMock()
    skill._start("white")
    time.sleep(0.1)  # let a few iterations happen
    skill._stop()
    count_after_stop = skill.play_audio.call_count
    time.sleep(0.1)  # if the loop were still running, more calls would appear
    assert skill.play_audio.call_count == count_after_stop


def test_starting_new_noise_type_stops_old_one(skill, monkeypatch):
    import whitenoise_skill as m
    monkeypatch.setattr(m, "CLIP_DURATION_SECONDS", 0.05)
    skill.play_audio = MagicMock()
    skill._start("white")
    first_thread = skill._thread
    skill._start("pink")
    assert skill._thread is not first_thread
    skill._stop()


def test_handle_set_noise_valid_type(skill, monkeypatch):
    import whitenoise_skill as m
    monkeypatch.setattr(m, "CLIP_DURATION_SECONDS", 0.05)
    skill.play_audio = MagicMock()
    skill.speak_dialog = MagicMock()
    message = MagicMock()
    message.data = {"noise": "pink"}
    skill.handle_set_noise(message)
    assert skill._is_running()
    assert skill._last_noise_type == "pink"
    skill.speak_dialog.assert_called_once_with("noise_started", {"noise": "pink"})


def test_handle_set_noise_unknown_type(skill):
    skill.play_audio = MagicMock()
    skill.speak_dialog = MagicMock()
    message = MagicMock()
    message.data = {"noise": "rain"}
    skill.handle_set_noise(message)
    assert not skill._is_running()
    skill.speak_dialog.assert_called_once_with("noise_not_understood", {"noise": "rain"})


def test_handle_start_noise_defaults_to_white(skill, monkeypatch):
    import whitenoise_skill as m
    monkeypatch.setattr(m, "CLIP_DURATION_SECONDS", 0.05)
    skill.play_audio = MagicMock()
    skill.speak_dialog = MagicMock()
    message = MagicMock()
    skill.handle_start_noise(message)
    from whitenoise_skill import DEFAULT_NOISE
    assert skill._last_noise_type == DEFAULT_NOISE
    skill.speak_dialog.assert_called_once_with("noise_started", {"noise": DEFAULT_NOISE})


def test_handle_stop_noise_when_not_running(skill):
    skill.speak_dialog = MagicMock()
    message = MagicMock()
    skill.handle_stop_noise(message)
    skill.speak_dialog.assert_called_once_with("noise_not_running")


def test_handle_stop_noise_when_running(skill, monkeypatch):
    import whitenoise_skill as m
    monkeypatch.setattr(m, "CLIP_DURATION_SECONDS", 0.05)
    skill.play_audio = MagicMock()
    skill.speak_dialog = MagicMock()
    skill._start("white")
    message = MagicMock()
    skill.handle_stop_noise(message)
    assert not skill._is_running()
    skill.speak_dialog.assert_called_once_with("noise_stopped")
