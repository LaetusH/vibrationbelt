"""
Template Builder - Create proper alarm templates from real audio data.

IMPORTANT: This system requires real alarm audio for training!

Without training data, template matching is unreliable:
- Cosine similarity between spectrograms is not a good alarm detector
- Will have false positives AND false negatives
- Solution: Train a CNN with real alarm data

See: models/cnn_trainer.py for proper training approach
"""

import numpy as np
import os
import pickle
from pathlib import Path
from typing import Dict, List, Optional


class TemplateBuilder:
    """Build and manage alarm templates."""
    
    def __init__(self, template_dir: Optional[str] = None):
        """
        Args:
            template_dir: Where to store templates (default: ./templates/)
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        
        self.template_dir = Path(template_dir)
        self.template_dir.mkdir(exist_ok=True)
        
        self.templates: Dict[str, np.ndarray] = {}
        self._load_existing()
    
    def _load_existing(self):
        """Load any existing templates from disk."""
        template_file = self.template_dir / "alarm_templates.pkl"
        if template_file.exists():
            with open(template_file, 'rb') as f:
                self.templates = pickle.load(f)
            print(f"✓ Loaded {len(self.templates)} existing templates")
    
    def add_sample(self, spectrogram: np.ndarray, label: str = "alarm"):
        """
        Add a single spectrogram as a sample.
        
        Args:
            spectrogram: (224, 224) spectrogram array
            label: 'alarm' or 'silence' or other label
        """
        if spectrogram.shape != (224, 224):
            raise ValueError(f"Expected (224, 224), got {spectrogram.shape}")
        
        key = f"{label}_sample_{len(self.templates)}"
        self.templates[key] = spectrogram.astype(np.float32)
    
    def create_canonical_template(self, label: str = "alarm", 
                                   samples_min: int = 3) -> Optional[np.ndarray]:
        """
        Create a canonical (averaged) template from multiple samples.
        
        Args:
            label: Which samples to average
            samples_min: Minimum number of samples needed
            
        Returns:
            Canonical template (224, 224) or None if not enough samples
        """
        # Find all samples for this label
        samples = [spec for key, spec in self.templates.items() 
                   if key.startswith(label)]
        
        if len(samples) < samples_min:
            print(f"⚠ Need at least {samples_min} samples for '{label}', have {len(samples)}")
            return None
        
        # Average them
        canonical = np.mean(np.array(samples), axis=0).astype(np.float32)
        
        # Normalize
        canonical = (canonical - canonical.min()) / (canonical.max() - canonical.min() + 1e-10)
        
        return canonical
    
    def save_templates(self) -> Path:
        """Save all templates to disk."""
        template_file = self.template_dir / "alarm_templates.pkl"
        
        with open(template_file, 'wb') as f:
            pickle.dump(self.templates, f)
        
        print(f"✓ Saved {len(self.templates)} templates to {template_file}")
        return template_file
    
    def get_stats(self) -> Dict:
        """Get statistics about templates."""
        if not self.templates:
            return {"count": 0, "labels": []}
        
        labels = {}
        for key in self.templates:
            label = key.rsplit('_', 1)[0]
            labels[label] = labels.get(label, 0) + 1
        
        return {
            "total": len(self.templates),
            "by_label": labels,
        }


class SilenceTemplate:
    """Creates a silence/baseline template."""
    
    @staticmethod
    def create_from_audio(audio: np.ndarray, sr: int = 16000) -> np.ndarray:
        """
        Create a silence template from quiet audio.
        
        Args:
            audio: Audio samples (should be quiet/silent)
            sr: Sample rate
            
        Returns:
            Spectrogram (224, 224)
        """
        from ..spectrogram.generator import SpectrogramGenerator
        
        gen = SpectrogramGenerator(sr=sr)
        spec = gen.generate(audio, normalize=True)
        
        return spec.astype(np.float32)
    
    @staticmethod
    def create_synthetic() -> np.ndarray:
        """Create a neutral silence template (all zeros)."""
        spec = np.zeros((224, 224), dtype=np.float32)
        return spec


class AlarmTemplate:
    """Creates an alarm template."""
    
    @staticmethod
    def create_from_audio(audio: np.ndarray, sr: int = 16000) -> np.ndarray:
        """
        Create an alarm template from actual alarm audio.
        
        Args:
            audio: Audio samples (should contain alarm)
            sr: Sample rate
            
        Returns:
            Spectrogram (224, 224)
        """
        from ..spectrogram.generator import SpectrogramGenerator
        
        gen = SpectrogramGenerator(sr=sr)
        spec = gen.generate(audio, normalize=True)
        
        return spec.astype(np.float32)
    
    @staticmethod
    def create_synthetic() -> np.ndarray:
        """
        Create a synthetic alarm template (PLACEHOLDER).
        
        ⚠ WARNING: This is unreliable without real training data!
        
        Returns a uniform noise pattern that is unlikely to match
        anything specific, so we can use very high threshold
        to avoid false positives.
        """
        # Very low uniform noise - won't match much
        spec = np.ones((224, 224), dtype=np.float32) * 0.001
        return spec


def create_default_templates() -> Dict[str, np.ndarray]:
    """
    Create default templates for bootstrapping.
    
    IMPORTANT: These are PLACEHOLDERS only!
    
    For production, you MUST:
    1. Collect real alarm audio samples
    2. Convert to spectrograms
    3. Train a CNN or create proper templates
    
    See: models/cnn_trainer.py
    """
    return {
        'silence_baseline': SilenceTemplate.create_synthetic(),
        'alarm_placeholder': AlarmTemplate.create_synthetic(),
    }


if __name__ == "__main__":
    print("Creating placeholder templates...")
    templates = create_default_templates()
    
    builder = TemplateBuilder()
    for name, spec in templates.items():
        builder.templates[name] = spec
    
    builder.save_templates()
    print(f"✓ Created {len(templates)} placeholder templates")
    print("\n⚠️  NOTE: These are PLACEHOLDERS only!")
    print("   For real alarm detection, train a CNN with real data.")
