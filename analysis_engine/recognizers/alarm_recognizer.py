"""
Alarm Recognizer - CNN and Template-based detection

Supports:
  1. Template Matching (fast, no training required)
  2. CNN Model (better accuracy, requires training)
"""

import numpy as np
from typing import Optional, Dict
import os
import pickle


class AlarmRecognizer:
    """
    Alarm detection using CNN or template matching.
    
    Starts with template matching (template_only=True).
    Can be upgraded to CNN when trained model is available.
    """

    def __init__(self, model_path: Optional[str] = None, use_template_only: bool = True):
        """
        Args:
            model_path: Path to trained CNN model (optional)
            use_template_only: If True, use template matching instead of CNN
        """
        self.model_path = model_path
        self.use_template_only = use_template_only
        self.model = None
        self.templates = {}
        
        # Load model if provided
        if model_path and os.path.exists(model_path) and not use_template_only:
            self._load_cnn_model(model_path)
        
        # Load or initialize templates
        self._load_templates()

    def recognize(self, spectrogram: np.ndarray, debug: bool = False) -> Dict:
        """
        Recognize if spectrogram contains an alarm.
        
        Args:
            spectrogram: Mel-spectrogram (224, 224) normalized to 0-1
            debug: Return additional debug info
            
        Returns:
            {
                'is_alarm': bool,
                'confidence': float (0-1),
                'method': str ('template' or 'cnn'),
                'details': dict (if debug=True)
            }
        """
        if spectrogram is None or spectrogram.size == 0:
            return {
                'is_alarm': False,
                'confidence': 0.0,
                'method': 'none',
            }
        
        # Ensure correct shape and type
        spectrogram = np.asarray(spectrogram, dtype=np.float32)
        if spectrogram.shape != (224, 224):
            return {
                'is_alarm': False,
                'confidence': 0.0,
                'method': 'invalid_shape',
            }
        
        # Use CNN or template matching
        if self.model and not self.use_template_only:
            result = self._recognize_cnn(spectrogram, debug)
        else:
            result = self._recognize_template(spectrogram, debug)
        
        return result

    def _recognize_template(self, spec: np.ndarray, debug: bool = False) -> Dict:
        """Template-based recognition using cosine similarity."""
        if not self.templates:
            return {
                'is_alarm': False,
                'confidence': 0.0,
                'method': 'template',
                'details': {'reason': 'no_templates_loaded'} if debug else {},
            }
        
        # Flatten for comparison
        spec_flat = spec.flatten()
        
        # Compare with all templates
        max_similarity = 0.0
        best_template = None
        similarities = {}
        
        for name, template in self.templates.items():
            sim = self._cosine_similarity(spec_flat, template.flatten())
            similarities[name] = sim
            
            if sim > max_similarity:
                max_similarity = sim
                best_template = name
        
        # Threshold for alarm detection
        threshold = 0.6
        is_alarm = max_similarity > threshold
        
        result = {
            'is_alarm': is_alarm,
            'confidence': float(max_similarity),
            'method': 'template',
        }
        
        if debug:
            result['details'] = {
                'best_match': best_template,
                'all_similarities': similarities,
                'threshold': threshold,
            }
        
        return result

    def _recognize_cnn(self, spec: np.ndarray, debug: bool = False) -> Dict:
        """CNN-based recognition."""
        if self.model is None:
            return {
                'is_alarm': False,
                'confidence': 0.0,
                'method': 'cnn',
                'details': {'reason': 'model_not_loaded'} if debug else {},
            }
        
        try:
            import torch
            
            # Prepare input
            tensor = torch.from_numpy(spec).unsqueeze(0).unsqueeze(0)  # (1, 1, 224, 224)
            
            # Forward pass
            with torch.no_grad():
                logits = self.model(tensor)
                probs = torch.softmax(logits, dim=1)
                confidence = probs[0, 1].item()  # Probability of alarm class
            
            # Threshold
            threshold = 0.5
            is_alarm = confidence > threshold
            
            result = {
                'is_alarm': is_alarm,
                'confidence': float(confidence),
                'method': 'cnn',
            }
            
            if debug:
                result['details'] = {
                    'logits': logits[0].cpu().numpy().tolist(),
                    'threshold': threshold,
                }
            
            return result
        
        except Exception as e:
            return {
                'is_alarm': False,
                'confidence': 0.0,
                'method': 'cnn',
                'details': {'error': str(e)} if debug else {},
            }

    def _load_cnn_model(self, model_path: str):
        """Load trained PyTorch model."""
        try:
            import torch
            self.model = torch.load(model_path, map_location='cpu')
            self.model.eval()
            print(f"✓ Loaded CNN model from {model_path}")
        except Exception as e:
            print(f"⚠ Failed to load CNN model: {e}")
            self.model = None

    def _load_templates(self):
        """Load stored alarm templates."""
        # For now, create synthetic templates from captured alarm data
        # TODO: Load from saved templates directory
        
        # Placeholder: create a dummy template
        self.templates['alarm_baseline'] = np.random.rand(224, 224).astype(np.float32) * 0.3

    def add_template(self, name: str, spectrogram: np.ndarray):
        """Add a new template (for calibration/training)."""
        spectrogram = np.asarray(spectrogram, dtype=np.float32)
        if spectrogram.shape != (224, 224):
            raise ValueError(f"Expected shape (224, 224), got {spectrogram.shape}")
        
        self.templates[name] = spectrogram

    def save_templates(self, path: str):
        """Save templates to disk."""
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump(self.templates, f)
        print(f"✓ Saved {len(self.templates)} templates to {path}")

    def load_templates_from_file(self, path: str):
        """Load templates from disk."""
        if os.path.exists(path):
            with open(path, 'rb') as f:
                self.templates = pickle.load(f)
            print(f"✓ Loaded {len(self.templates)} templates from {path}")

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        a = a.astype(np.float32)
        b = b.astype(np.float32)
        
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0
        
        return dot_product / (norm_a * norm_b)

    def get_config(self) -> dict:
        """Return configuration"""
        return {
            'method': 'cnn' if (self.model and not self.use_template_only) else 'template',
            'model_path': self.model_path,
            'num_templates': len(self.templates),
            'use_template_only': self.use_template_only,
        }
