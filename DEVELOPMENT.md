# Development

## Setup
```bash
git clone https://github.com/andlo/ovos-skill-white-noise.git
cd ovos-skill-white-noise
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-test.txt
```

## Running tests
```bash
pytest tests/ -v
```
`tests/test_noise_generation.py` checks the generators directly
(determinism via fixed seed, range clamping, that the three types are
genuinely different from each other, and a rough "brown is smoother
than white" sanity check via average sample-to-sample difference -
not a full FFT, just enough to catch an obviously broken filter).
`tests/test_intents.py` covers start/stop/alias-resolution with REAL
threads and REAL (short) waits - `CLIP_DURATION_SECONDS` is
monkeypatched down to ~0.05s per test so the suite stays fast without
mocking away the actual timing behavior, same approach as
`ovos-skill-metronome`/`ovos-skill-rhythm-box`.

## Adding rain/ocean/other recorded ambient sounds

Not implemented (see README) - the real blocker is finding a
genuinely loopable recording, not writing the playback code (which
would reuse the exact same `_loop()`/`_start()`/`_stop()` pattern
already here, just pointing at a bundled file instead of a generated
one). Before attempting this:
1. Confirm the source is actually seamlessly loopable - listen
   carefully at the loop point, don't just assume a "10 minute rain"
   recording loops cleanly at its own end.
2. Confirm the license permits redistribution (same CC0/CC-BY
   diligence as `ovos-skill-sound-like`'s `CREDITS.md`).
3. File size matters more here than for the short one-shot sounds in
   `ovos-skill-sound-like` - a genuinely long, high-quality loop can
   be several MB; consider whether a shorter loop (30-60s) with a
   carefully crossfaded seam is more practical than trying to source
   a naturally-loopable multi-minute recording.

## Adjusting noise character

`NOISE_SEED`, `CLIP_DURATION_SECONDS`, and the per-type generator
functions (`_generate_white_samples`, `_generate_pink_samples`,
`_generate_brown_samples`) are all in `__init__.py`. The pink/brown
filter coefficients are standard published DSP constants (Paul
Kellet's economy method, a clamped random walk) - changing them
changes the noise "color", worth understanding the underlying
technique before tweaking rather than guessing at numbers.

## Versioning

`version.py` follows `VERSION_MAJOR.VERSION_MINOR.VERSION_BUILD[aVERSION_ALPHA]`.

## Releasing

Releases are tag-triggered (`v*`):
```bash
git add version.py
git commit -m "chore: bump version to 0.0.X"
git tag vX.Y.Z
git push && git push --tags
```
Triggers `.github/workflows/test.yml` then `.github/workflows/publish.yml`
(PyPI via trusted publishing - see `ovos-skill-convert`'s
DEVELOPMENT.md for the one-time PyPI setup needed before the first
tagged release).

## Style / conventions

- License: GPL-3.0-or-later (matches the other `andlo` skill repos).
- `locale/<lang-code>/` layout, `skill.json` inside each locale folder.
- Alias JSON in locale (`noise_aliases.json`) - same JSON-in-locale
  convention as the rest of this project family.
- Present design changes for review before implementing.
