"""Tests for the noise generation itself - deterministic (fixed seed),
no mocking needed."""
import random

import pytest


def test_white_noise_is_deterministic_with_fixed_seed():
    import whitenoise_skill as m
    a = m._generate_white_samples(1000, random.Random(m.NOISE_SEED))
    b = m._generate_white_samples(1000, random.Random(m.NOISE_SEED))
    assert a == b


def test_pink_noise_is_deterministic_with_fixed_seed():
    import whitenoise_skill as m
    a = m._generate_pink_samples(1000, random.Random(m.NOISE_SEED))
    b = m._generate_pink_samples(1000, random.Random(m.NOISE_SEED))
    assert a == b


def test_brown_noise_is_deterministic_with_fixed_seed():
    import whitenoise_skill as m
    a = m._generate_brown_samples(1000, random.Random(m.NOISE_SEED))
    b = m._generate_brown_samples(1000, random.Random(m.NOISE_SEED))
    assert a == b


def test_all_three_noise_types_produce_different_content():
    """Guards against a copy-paste bug where two generators
    accidentally produce identical output."""
    import whitenoise_skill as m
    white = m._generate_white_samples(1000, random.Random(m.NOISE_SEED))
    pink = m._generate_pink_samples(1000, random.Random(m.NOISE_SEED))
    brown = m._generate_brown_samples(1000, random.Random(m.NOISE_SEED))
    assert white != pink
    assert pink != brown
    assert white != brown


def test_all_samples_stay_within_valid_range():
    import whitenoise_skill as m
    for name, gen in m.NOISE_GENERATORS.items():
        samples = gen(2000, random.Random(m.NOISE_SEED))
        assert all(-1.0 <= s <= 1.0 for s in samples), f"{name} exceeded [-1,1]"


def test_brown_noise_has_less_sample_to_sample_variation_than_white():
    """Sanity check that brown noise is actually 'smoother' than white
    noise, not just a differently-seeded copy of the same algorithm -
    a rough proxy for '1/f^2 spectrum vs flat spectrum' without doing
    a full FFT in the test suite."""
    import whitenoise_skill as m
    white = m._generate_white_samples(5000, random.Random(m.NOISE_SEED))
    brown = m._generate_brown_samples(5000, random.Random(m.NOISE_SEED))

    def avg_abs_diff(samples):
        diffs = [abs(samples[i] - samples[i - 1]) for i in range(1, len(samples))]
        return sum(diffs) / len(diffs)

    assert avg_abs_diff(brown) < avg_abs_diff(white)
