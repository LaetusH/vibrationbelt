# Analysis Engine - Signal Processing Pipeline

High-level audio analysis for VibrationBelt alarm detection.

## Architecture

```
Audio Input (2 Microphones)
    ↓
┌─────────────────────────────────────┐
│ 1. DOA Estimator                    │  ← TDOA-based direction
│    Input: dual mic audio            │
│    Output: 0-360° angle             │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 2. Spectrogram Generator            │  ← Mel-scaled image
│    Input: single mic audio          │
│    Output: 224×224 normalized image │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 3. Alarm Recognizer                 │  ← Template/CNN
│    Input: spectrogram               │
│    Output: confidence (0-1)         │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 4. Motor Mapper                     │  ← DOA → Motor
│    Input: angle + confidence        │
│    Output: motor index (0-3)        │
└─────────────────────────────────────┘
    ↓
Output: {doa, alarm_confidence, motor_prediction, spectrogram}
```

## Quick Start

### 1. Basic Pipeline Usage

```python
from analysis_engine import AudioAnalysisPipeline

# Initialize
pipeline = AudioAnalysisPipeline(
    mic_distance=0.05,        # 5cm between mics
    sample_rate=16000,
    use_template_only=True,   # Start with template matching
)

# Analyze audio
result = pipeline.analyze(
    audio_mic1=audio_chunk_1,
    audio_mic2=audio_chunk_2,
    debug=True
)

print(f"Direction: {result['doa_degrees']}°")
print(f"Alarm: {result['is_alarm']} (confidence: {result['alarm_confidence']:.0%})")
print(f"Motor: {result['predicted_motor']}")
```

### 2. Individual Components

```python
from analysis_engine import DOAEstimator, SpectrogramGenerator, AlarmRecognizer, MotorMapper

# DOA Estimation
doa = DOAEstimator(mic_distance=0.05)
angle = doa.estimate(audio_mic1, audio_mic2)
# Returns: 0-360 degrees

# Spectrogram Generation
spec_gen = SpectrogramGenerator()
spectrogram = spec_gen.generate(audio)
# Returns: (224, 224) normalized image

# Alarm Recognition
recognizer = AlarmRecognizer(use_template_only=True)
result = recognizer.recognize(spectrogram)
# Returns: {'is_alarm': bool, 'confidence': float, 'method': str}

# Motor Mapping
motor = MotorMapper.get_motor(angle)
# Returns: 0-3 (front, right, back, left)

intensities = MotorMapper.angle_to_motor_intensity(angle)
# Returns: {0: 0.8, 1: 0.2, 2: 0.0, 3: 0.0}
```

## Components

### DOA Estimator (`doa/estimator.py`)

**Time Difference of Arrival (TDOA) based direction estimation.**

- Input: Audio from 2+ microphones
- Output: Angle in degrees (0-360°)
- Coordinate system:
  - 0° = Front
  - 90° = Right
  - 180° = Back
  - 270° = Left

```python
doa = DOAEstimator(
    mic_distance=0.05,      # 5cm between mics
    sample_rate=16000
)

angle = doa.estimate(mic1_audio, mic2_audio)
# Returns angle or None if estimation failed
```

### Spectrogram Generator (`spectrogram/generator.py`)

**Convert audio to Mel-scaled visual representation.**

- Input: Raw audio samples
- Output: 224×224 normalized image (0-1)
- Features:
  - Mel frequency scaling (128 bands)
  - Power-to-dB conversion
  - Resizing to CNN-friendly 224×224

```python
spec_gen = SpectrogramGenerator(sr=16000, n_mels=128)

spectrogram = spec_gen.generate(audio)
# Returns (224, 224) array

# Convert to visualization
dataurl = spec_gen.spectrogram_to_dataurl(spectrogram)
# For HTML display
```

### Alarm Recognizer (`recognizers/alarm_recognizer.py`)

**Detect alarms using template matching or CNN.**

**Template Matching (default):**
- Compares input spectrogram with stored templates
- Uses cosine similarity
- Fast, no training required
- Good starting point

**CNN (when trained):**
- Uses MobileNet v2 backbone
- Requires training data
- Better accuracy
- Can learn complex patterns

```python
recognizer = AlarmRecognizer(
    use_template_only=True,  # Start with templates
    model_path=None          # Path to CNN model when available
)

result = recognizer.recognize(spectrogram, debug=False)
# Returns:
# {
#     'is_alarm': bool,
#     'confidence': float (0-1),
#     'method': 'template' or 'cnn',
#     'details': dict (if debug=True)
# }

# Add a new template during calibration
recognizer.add_template('alarm_1', spectrogram)
recognizer.save_templates('alarm_templates.pkl')
```

### Motor Mapper (`motor_mapper.py`)

**Convert DOA angle to motor activation.**

Coordinate system (4 motors):
- Motor 0: Front (0-90°)
- Motor 1: Right (90-180°)
- Motor 2: Back (180-270°)
- Motor 3: Left (270-360°)

```python
# Get primary motor
motor = MotorMapper.get_motor(doa_degrees=45)
# Returns: 1 (Right)

# Get motor intensities (for smooth/gradual activation)
intensities = MotorMapper.angle_to_motor_intensity(doa_degrees=45, spread=30)
# Returns: {0: 0.3, 1: 0.8, 2: 0.0, 3: 0.0}
# Motor 1 is strongest, Motor 0 has some spillover
```

## Training CNN Model

### Prepare Dataset

```
data/
├── alarm/              # Positive samples (spectrogram .npy files)
│   ├── alarm_0001.npy
│   ├── alarm_0002.npy
│   └── ...
├── noise/              # Negative samples (non-alarms)
│   ├── knock_0001.npy
│   └── ...
└── background/         # Negative samples (ambient)
    ├── ambient_0001.npy
    └── ...
```

### Train Model

```bash
cd analysis_engine

python models/cnn_trainer.py \
    --data ./data \
    --epochs 50 \
    --batch-size 32 \
    --lr 1e-3 \
    --output models/alarm_detector_cnn.pt
```

### Use Trained Model

```python
from analysis_engine import AudioAnalysisPipeline

pipeline = AudioAnalysisPipeline(
    model_path='analysis_engine/models/alarm_detector_cnn.pt',
    use_template_only=False  # Use CNN instead of templates
)

result = pipeline.analyze(mic1, mic2)
# Now uses trained CNN for detection
```

## Testing

Run the test suite:

```bash
python analysis_engine/test_pipeline.py
```

Tests cover:
- DOA estimation
- Spectrogram generation
- Alarm recognition
- Motor mapping
- Full pipeline
- Batch processing

## Integration with DebugClient

The C# `DebugClient` (Blazor) will:

1. **Capture** dual-mic audio from ESP32
2. **Call** Python analysis pipeline (via subprocess or REST API)
3. **Receive** analysis results (DOA, alarm confidence, motor prediction)
4. **Visualize** on dashboard (compass, spectrogram, motor indicator)
5. **Display** real-time motor activation preview

See `DebugClient/Services/AudioAnalysisService.cs` for integration details.

## Configuration

All components are configurable:

```python
pipeline.get_config()
# Returns:
# {
#     'sample_rate_hz': 16000,
#     'doa': {...},
#     'spectrogram': {...},
#     'recognizer': {...},
#     'motor_map': {...}
# }

pipeline.get_status()
# Returns runtime status of all components
```

## Performance

- DOA: ~0.5ms per chunk
- Spectrogram: ~2ms per chunk
- Template Recognition: ~1ms per chunk
- **Total: ~3-4ms per analysis** (real-time capable)

With CNN: ~10-15ms per chunk (depends on hardware)

## File Structure

```
analysis_engine/
├── __init__.py                    # Main entry point
├── README.md                      # This file
├── test_pipeline.py              # Test suite
├── pipeline.py                   # Full orchestration
│
├── doa/
│   ├── __init__.py
│   └── estimator.py              # TDOA-based DOA
│
├── spectrogram/
│   ├── __init__.py
│   └── generator.py              # Mel-spectrogram
│
├── recognizers/
│   ├── __init__.py
│   └── alarm_recognizer.py       # Template/CNN detection
│
└── models/
    ├── __init__.py
    ├── cnn_trainer.py            # Training script
    └── (alarm_detector_cnn.pt)   # Trained model (not in repo)
```

## Next Steps

1. **Integrate with DebugClient** - C# services to call Python pipeline
2. **Collect training data** - Record alarms + non-alarms as spectrograms
3. **Train CNN model** - Use `cnn_trainer.py` with your data
4. **Benchmark** - Compare template vs CNN accuracy on real data
5. **Optimize** - Fine-tune thresholds based on false positive/negative rates

## Dependencies

```
numpy
scipy
matplotlib
(optional) torch, torchvision  # For CNN training
```

Install:
```bash
pip install numpy scipy matplotlib
pip install torch torchvision  # For CNN support
```

## License

Part of VibrationBelt project.
