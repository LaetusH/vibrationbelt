# Audio Analysis Pipeline - Implementation Plan

## Scope
Build a production-ready audio analysis pipeline in Python:
1. Load WAV files from repository
2. Compute FFT (frequency domain analysis)
3. Generate spectrograms
4. Detect loudness anomalies (audio too loud)
5. Match frequencies against known alarm signals (sirens, smoke detectors, warning tones)
6. Handle real, noisy audio robustly

## Architecture

```
processing/
├── audio_analyzer/
│   ├── __init__.py
│   ├── loader.py          # WAV file I/O
│   ├── fft.py             # FFT computation, frequency analysis
│   ├── spectrogram.py     # Spectrogram generation
│   ├── loudness.py        # Loudness detection (LUFS, peak)
│   ├── alarm_detector.py  # Frequency matching against known patterns
│   └── utils.py           # Common utilities
├── tests/
│   ├── __init__.py
│   ├── test_loader.py
│   ├── test_fft.py
│   ├── test_loudness.py
│   ├── test_alarm_detector.py
│   └── conftest.py        # Test fixtures, sample audio
├── requirements.txt       # Dependencies
├── pytest.ini            # Pytest config
├── examples/             # Example scripts
└── data/
    └── sample_audio/     # Test WAV files
```

## Known Alarm Patterns
- **Sirens (Feuerwehr):** 800-1200 Hz, pulsing, ~1-2 sec cycles
- **Smoke Detectors:** 2.5-3.5 kHz, rapid chirps, ~85-90 dB
- **Industrial Warnings:** 1-2 kHz, steady tone or sweeping
- General rule: Narrow bands, periodic structure, distinct from speech/music

## Implementation Steps (incremental, git-commitfähig)

### Phase 1: Core Infrastructure
- [ ] **Step 1.1:** Project setup (requirements.txt, directory structure)
- [ ] **Step 1.2:** Audio loader (read WAV, validate, return numpy array)
- [ ] **Step 1.3:** Add basic tests + fixtures

### Phase 2: Frequency Analysis
- [ ] **Step 2.1:** FFT computation (power spectrum, frequency bins)
- [ ] **Step 2.2:** Spectrogram generation (STFT)
- [ ] **Step 2.3:** Tests for both

### Phase 3: Loudness Detection
- [ ] **Step 3.1:** Implement LUFS + peak loudness measurement
- [ ] **Step 3.2:** Threshold-based alerting
- [ ] **Step 3.3:** Tests

### Phase 4: Alarm Pattern Matching
- [ ] **Step 4.1:** Define alarm signatures (frequency, duration, intensity)
- [ ] **Step 4.2:** Implement pattern matcher (peak detection, band energy, periodicity)
- [ ] **Step 4.3:** Robustness for noisy signals
- [ ] **Step 4.4:** Tests

### Phase 5: Integration + Polish
- [ ] **Step 5.1:** High-level Pipeline class
- [ ] **Step 5.2:** Example scripts
- [ ] **Step 5.3:** Documentation

## Testing Strategy
- Unit tests for each module
- Integration tests with sample audio
- Edge cases: silence, noise, clipped signals, short files
- Fixtures: generate synthetic alarm tones + noise

## Git Commits
Each step → one commit, clear message, runnable tests.

Example:
```
git add audio_analyzer/loader.py tests/test_loader.py
git commit -m "feat: Add WAV loader with validation + tests"
```

---

Status: Ready to start Phase 1
