"""OCP: "play white noise" is taken by the OCP pipeline before padatious,
so the skill answers OCP's search itself and plays via @ocp_play (#2)."""
from unittest.mock import MagicMock

import pytest
from ovos_utils.ocp import MediaType, PlaybackType

import whitenoise_skill as wn


@pytest.fixture(autouse=True)
def _no_entity_autoregister(monkeypatch):
    # ovos-workshop >= 9.8 auto-registers entity files on load_lang(),
    # needing attributes __new__() bypasses; there are no entity files here
    monkeypatch.setattr(wn.WhiteNoise, "_auto_register_entity_files",
                        lambda *a, **k: None, raising=False)


@pytest.mark.parametrize("phrase,noise,conf", [
    ("white noise", "white", 100),
    ("pink noise", "pink", 100),
    ("some brown noise for sleep", "brown", 100),
    ("red noise", "brown", 100),
    ("some background noise", "white", 90),
])
def test_search_answers_noise_phrases(skill, phrase, noise, conf):
    [r] = skill.search_noise(phrase, MediaType.MUSIC)
    assert r.uri == f"/{skill.skill_id}/{noise}"
    assert not r.uri.startswith("file:")  # files extractor would make it AUDIO
    assert r.match_confidence == conf
    assert r.playback == PlaybackType.SKILL
    assert r.media_type == MediaType.MUSIC  # echoed, so OCP's filter keeps it


@pytest.mark.parametrize("phrase", [
    "white noise by the noise band",   # something else is asked for
    "the beatles",
    "white christmas",
    "",
])
def test_search_ignores_other_phrases(skill, phrase):
    assert skill.search_noise(phrase, MediaType.MUSIC) == []


def test_search_danish(skill, monkeypatch):
    monkeypatch.setattr(wn.WhiteNoise, "lang", "da-dk", raising=False)
    [r] = skill.search_noise("noget hvid støj", MediaType.AUDIO)
    assert r.uri.endswith("/white") and r.match_confidence == 100


def test_ocp_play_starts_the_right_noise(skill, monkeypatch):
    started = []
    monkeypatch.setattr(skill, "_start", started.append)
    msg = MagicMock()
    msg.data = {"uri": "/ovos-skill-white-noise.andlo/pink"}
    skill.play_noise(msg)
    msg.data = {"uri": "/ovos-skill-white-noise.andlo/../../etc/passwd"}
    skill.play_noise(msg)
    assert started == ["pink", "white"]


def test_stop_ends_noise_and_reports_it(skill, monkeypatch):
    monkeypatch.setattr(skill, "play_audio", MagicMock())
    monkeypatch.setattr(wn, "_noise_clip_path", lambda t: f"/tmp/{t}.wav")
    assert skill.stop() is False
    skill._start("white")
    assert skill.can_stop() is True
    assert skill.stop() is True
    assert not skill._is_running()
