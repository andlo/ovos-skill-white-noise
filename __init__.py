"""
skill OVOS White Noise
Copyright (C) 2026  Andreas Lorensen

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

---

An ambient noise machine - "play white noise" for sleep/focus. Only
white, pink, and brown noise are supported, ALL GENERATED, not
recorded. This is a deliberate scope decision, not a limitation to
apologize for:

WHY NO RAIN/OCEAN/FAN SOUNDS
------------------------------------
The original brief mentioned rain and ocean waves too. Those need
genuinely LOOPABLE recordings (a hard seam or click at the loop point
would be very noticeable in a sustained ambient track, unlike the
short one-shot clips ovos-skill-sound-like uses) - a stricter sourcing
requirement than anything else built in this project family so far,
and a real one to solve properly rather than rush. White/pink/brown
noise sidesteps the whole problem: since noise has no coherent
waveform pattern for the ear to lock onto, a generated clip looping
back to its own start is inherently seamless, with no seam-finding or
recording-quality concerns at all. Rain/ocean are tracked as a future
enhancement requiring real recordings, not built here.

WHY "STOP" DOESN'T STOP INSTANTLY
--------------------------------------
Same underlying reason as ovos-skill-tuning-fork: play_audio() has no
reliable way to interrupt an already-playing sound. Noise is looped by
repeatedly re-triggering a fixed-length generated clip
(CLIP_DURATION_SECONDS) from a background thread - "stop" sets a flag
that prevents the NEXT clip from being queued, but the clip already
playing rings out to its natural end (up to CLIP_DURATION_SECONDS).
This is different from ovos-skill-metronome/ovos-skill-rhythm-box,
where "stop" takes effect before the next short beat/step (a much
smaller worst-case delay) - here the worst case is the full clip
length, and that's disclosed rather than glossed over.

NOISE GENERATION
-----------------
- White: uniform random samples (flat spectrum).
- Pink: Paul Kellet's well-known economy IIR filter approximation
  (1/f spectrum) - a standard, publicly documented DSP technique, not
  sourced from any particular audio library or author.
- Brown/red: a clamped random walk (1/f^2 spectrum) - each sample
  nudges from the previous one and is clamped to [-1, 1] to prevent
  drifting out of range over a long clip.

All three use a FIXED random seed, so regenerating a given noise type
produces byte-identical audio - deterministic and reproducible, same
philosophy as everything else generated in this project (clicks,
tones, drum hits), even though the underlying content is "random".
"""

import json
import random
import re
import struct
import tempfile
import threading
import wave
from pathlib import Path

from ovos_utils.ocp import MediaEntry, MediaType, PlaybackType
from ovos_workshop.decorators import intent_handler
from ovos_workshop.decorators.ocp import ocp_play, ocp_search
from ovos_workshop.skills.common_play import OVOSCommonPlaybackSkill

SAMPLE_RATE = 44100
CLIP_DURATION_SECONDS = 20
NOISE_SEED = 42  # fixed - see module docstring on determinism

CACHE_DIR = Path(tempfile.gettempdir()) / "ovos-skill-white-noise"

NOISE_TYPES = ["white", "pink", "brown"]
DEFAULT_NOISE = "white"


def _generate_white_samples(n, rng):
    return [rng.uniform(-1, 1) for _ in range(n)]


def _generate_pink_samples(n, rng):
    """Paul Kellet's economy pink-noise filter - a well-known, public
    IIR approximation of a 1/f spectrum, three cascaded one-pole
    filters applied to white noise."""
    b0 = b1 = b2 = 0.0
    out = []
    for _ in range(n):
        s = rng.uniform(-1, 1)
        b0 = 0.99765 * b0 + s * 0.0990460
        b1 = 0.96300 * b1 + s * 0.2965164
        b2 = 0.57000 * b2 + s * 1.0526913
        pink = (b0 + b1 + b2 + s * 0.1848) * 0.11  # gain compensation
        out.append(max(-1.0, min(1.0, pink)))
    return out


def _generate_brown_samples(n, rng):
    """Clamped random walk (1/f^2 spectrum) - each sample nudges from
    the previous one, clamped to [-1, 1] to prevent long-run drift."""
    brown = 0.0
    out = []
    for _ in range(n):
        s = rng.uniform(-1, 1)
        brown += s * 0.02
        brown = max(-1.0, min(1.0, brown))
        out.append(brown)
    return out


NOISE_GENERATORS = {
    "white": _generate_white_samples,
    "pink": _generate_pink_samples,
    "brown": _generate_brown_samples,
}


def _write_wav(path, samples, sample_rate=SAMPLE_RATE):
    with wave.open(str(path), "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(sample_rate)
        clamped = (max(-1.0, min(1.0, s)) for s in samples)
        f.writeframes(b"".join(struct.pack("<h", int(s * 32767)) for s in clamped))


def _noise_clip_path(noise_type):
    """Cached per noise type - generated once, reused for every
    subsequent loop iteration and every future request for the same
    type (fixed seed means it would be identical anyway)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"{noise_type}.wav"
    if not path.exists():
        rng = random.Random(NOISE_SEED)
        n = int(SAMPLE_RATE * CLIP_DURATION_SECONDS)
        samples = NOISE_GENERATORS[noise_type](n, rng)
        _write_wav(path, samples)
    return str(path)


SKILL_ROOT = Path(__file__).resolve().parent
LOCALE_DIR = SKILL_ROOT / "locale"


def _load_noise_aliases_from_disk():
    """locale/<lang>/noise_aliases.json - {spoken form: key in
    NOISE_GENERATORS}. Same JSON-in-locale convention as the rest of
    this project family."""
    merged = {}
    if not LOCALE_DIR.is_dir():
        return merged
    for lang_dir in sorted(LOCALE_DIR.iterdir()):
        if not lang_dir.is_dir():
            continue
        alias_file = lang_dir / "noise_aliases.json"
        if not alias_file.exists():
            continue
        with open(alias_file, encoding="utf-8") as f:
            aliases = json.load(f)
        lang = lang_dir.name.lower()
        merged[lang] = {k: v for k, v in aliases.items() if not k.startswith("_")}
    return merged


NOISE_ALIASES = _load_noise_aliases_from_disk()

# "play ..." is taken by the OCP pipeline before padatious ever sees it,
# so the skill also answers OCP's search (issue #2). OCP only asks skills
# that support the media type it guessed; for "play white noise" that can
# be AUDIO, MUSIC or GENERIC, so all three are accepted, and the result
# echoes the query's type so OCP's media-type filter keeps it.
OCP_MEDIA = [MediaType.AUDIO, MediaType.MUSIC, MediaType.GENERIC]
OCP_CONF_COLOUR = 100   # "white noise", "pink noise" - clearly ours
OCP_CONF_GENERIC = 90   # "some noise", "background noise"


class WhiteNoise(OVOSCommonPlaybackSkill):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, supported_media=OCP_MEDIA,
                         skill_icon=str(SKILL_ROOT / "icon.png"), **kwargs)

    def initialize(self):
        # NB: not self._noise_stop - OVOSCommonPlaybackSkill uses that
        # name for its search, and sets it whenever an OCP search stops.
        self._noise_stop = threading.Event()
        self._thread = None
        self._last_noise_type = None

    def _noise_aliases_for(self, lang):
        lang = lang.lower()
        return NOISE_ALIASES.get(lang) or NOISE_ALIASES.get("en-us", {})

    def _resolve_noise(self, raw, lang):
        """Exact match only, no fuzzy matching - same reasoning as
        every other alias resolver in this project family."""
        if not raw:
            return None
        return self._noise_aliases_for(lang).get(raw.strip().lower())

    def _loop(self, noise_type):
        path = _noise_clip_path(noise_type)
        while not self._noise_stop.is_set():
            self.play_audio(path, instant=True)
            # Event.wait() returns AS SOON AS the event is set, not
            # after the full timeout - this is what lets "stop" take
            # effect promptly rather than only being checked once per
            # full clip length.
            self._noise_stop.wait(CLIP_DURATION_SECONDS)

    def _start(self, noise_type):
        self._stop()
        self._last_noise_type = noise_type
        self._noise_stop.clear()
        self._thread = threading.Thread(target=self._loop, args=(noise_type,), daemon=True)
        self._thread.start()

    def _stop(self):
        self._noise_stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None

    def _is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def shutdown(self):
        self._stop()

    # ------------------------------------------------------------------
    # Global "stop" and OCP's stop
    # ------------------------------------------------------------------

    def can_stop(self, message=None) -> bool:
        return self._is_running()

    def stop(self):
        if not self._is_running():
            return False
        self._stop()
        return True

    # ------------------------------------------------------------------
    # OCP: "play white noise" (issue #2)
    # ------------------------------------------------------------------

    def _ocp_match(self, phrase, lang):
        """(noise_type, confidence) when the phrase asks for noise and
        nothing else, e.g. "white noise", "some pink noise for sleep".
        Anything left over ("white noise by some band") is not ours."""
        words = re.findall(r"\w+", (phrase or "").lower())
        noise_words = {w.lower() for w in self.voc_list("noise", lang)}
        if not noise_words.intersection(words):
            return None
        aliases = self._noise_aliases_for(lang)
        filler = {w.lower() for w in self.voc_list("filler", lang)}
        colour = next((aliases[w] for w in words if w in aliases), None)
        rest = [w for w in words
                if w not in noise_words and w not in aliases and w not in filler]
        if rest:
            return None
        if colour:
            return colour, OCP_CONF_COLOUR
        return self._last_noise_type or DEFAULT_NOISE, OCP_CONF_GENERIC

    @ocp_search()
    def search_noise(self, phrase, media_type=MediaType.GENERIC):
        match = self._ocp_match(phrase, self.lang)
        if not match:
            return []
        noise_type, confidence = match
        return [MediaEntry(
            uri=f"file://{CACHE_DIR / noise_type}.wav",  # generated on play
            title=f"{noise_type.capitalize()} noise",
            artist="White Noise",
            media_type=media_type if media_type in OCP_MEDIA else MediaType.AUDIO,
            playback=PlaybackType.SKILL,
            match_confidence=confidence,
            skill_icon=self.skill_icon,
            skill_id=self.skill_id,
        )]

    @ocp_play()
    def play_noise(self, message=None):
        """OCP picked our search result - play it ourselves."""
        uri = (message.data.get("uri") if message else "") or ""
        noise_type = Path(uri).stem
        if noise_type not in NOISE_GENERATORS:
            noise_type = DEFAULT_NOISE
        self._start(noise_type)

    @intent_handler("set_noise.intent")
    def handle_set_noise(self, message):
        noise_raw = message.data.get("noise")
        noise_type = self._resolve_noise(noise_raw, self.lang) if noise_raw else None
        if noise_raw and noise_type is None:
            self.speak_dialog("noise_not_understood", {"noise": noise_raw})
            return
        noise_type = noise_type or DEFAULT_NOISE
        self._start(noise_type)
        self.speak_dialog("noise_started", {"noise": noise_raw or noise_type})

    @intent_handler("start_noise.intent")
    def handle_start_noise(self, message):
        noise_type = self._last_noise_type or DEFAULT_NOISE
        self._start(noise_type)
        self.speak_dialog("noise_started", {"noise": noise_type})

    @intent_handler("stop_noise.intent")
    def handle_stop_noise(self, message):
        if not self._is_running():
            self.speak_dialog("noise_not_running")
            return
        self._stop()
        self.speak_dialog("noise_stopped")
