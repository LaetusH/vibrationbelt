"""
CNN Model Training - AlarmDetectorCNN

Train a neural network to recognize alarm patterns from spectrograms.

Dataset structure expected:
  data/
    ├── alarm/          (positive samples - spectrograms as .npy)
    ├── noise/          (negative samples - knocks, silence, etc.)
    └── background/     (negative samples - ambient sounds)
"""

import numpy as np
from pathlib import Path
from typing import Tuple, Optional

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader, random_split
    import torchvision.models as models
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class AlarmSpectrogramDataset(Dataset):
    """Load spectrograms from disk and train CNN."""

    def __init__(self, data_dir: str, transform=None):
        """
        Args:
            data_dir: Root directory containing 'alarm' and 'negative' subdirs
            transform: Optional transforms
        """
        self.data_dir = Path(data_dir)
        self.transform = transform
        self.samples = []
        self.labels = []
        
        self._load_samples()

    def _load_samples(self):
        """Load spectrograms from disk."""
        # Load positive samples (alarms)
        alarm_dir = self.data_dir / 'alarm'
        if alarm_dir.exists():
            for npy_file in alarm_dir.glob('*.npy'):
                self.samples.append(npy_file)
                self.labels.append(1)  # Alarm
        
        # Load negative samples (non-alarms)
        for neg_dir in ['noise', 'background']:
            neg_path = self.data_dir / neg_dir
            if neg_path.exists():
                for npy_file in neg_path.glob('*.npy'):
                    self.samples.append(npy_file)
                    self.labels.append(0)  # Not alarm

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        spec = np.load(self.samples[idx]).astype(np.float32)
        
        if self.transform:
            spec = self.transform(spec)
        
        # Add channel dimension if missing
        if spec.ndim == 2:
            spec = spec[np.newaxis, :]  # (1, 224, 224)
        
        label = self.labels[idx]
        
        return torch.from_numpy(spec), torch.tensor(label, dtype=torch.long)


class AlarmDetectorCNN(nn.Module):
    """Lightweight CNN for alarm detection."""

    def __init__(self, pretrained: bool = True):
        super().__init__()
        
        # Use MobileNet v2 as backbone (lightweight, fast)
        if pretrained:
            self.backbone = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
        else:
            self.backbone = models.mobilenet_v2(weights=None)
        
        # Replace classifier
        in_features = self.backbone.classifier[1].in_features
        self.backbone.classifier = nn.Sequential(
            nn.Dropout(0.2),
            nn.Linear(in_features, 128),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(128, 2),  # 2 classes: alarm vs not-alarm
        )

    def forward(self, x):
        return self.backbone(x)


class AlarmCNNTrainer:
    """Train alarm detection CNN."""

    def __init__(self, model_save_path: str = 'models/alarm_detector_cnn.pt'):
        if not TORCH_AVAILABLE:
            raise RuntimeError("PyTorch not installed. Install with: pip install torch torchvision")
        
        self.model_save_path = model_save_path
        self.model = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    def train(
        self,
        data_dir: str,
        epochs: int = 50,
        batch_size: int = 32,
        learning_rate: float = 1e-3,
        val_split: float = 0.2,
    ):
        """
        Train the CNN model.
        
        Args:
            data_dir: Root directory with 'alarm' and 'negative' subdirs
            epochs: Number of training epochs
            batch_size: Batch size
            learning_rate: Learning rate
            val_split: Validation split ratio
        """
        print(f"🔧 Loading dataset from {data_dir}...")
        dataset = AlarmSpectrogramDataset(data_dir)
        
        if len(dataset) == 0:
            raise ValueError(f"No spectrograms found in {data_dir}")
        
        print(f"✓ Loaded {len(dataset)} samples")
        
        # Split train/val
        val_size = int(len(dataset) * val_split)
        train_size = len(dataset) - val_size
        train_set, val_set = random_split(dataset, [train_size, val_size])
        
        train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_set, batch_size=batch_size)
        
        # Initialize model
        print(f"📦 Initializing CNN model on {self.device}...")
        self.model = AlarmDetectorCNN(pretrained=True)
        self.model.to(self.device)
        
        # Optimizer and loss
        optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        criterion = nn.CrossEntropyLoss()
        
        # Training loop
        print(f"\n🚀 Training for {epochs} epochs...\n")
        for epoch in range(epochs):
            # Train phase
            self.model.train()
            train_loss = 0.0
            train_acc = 0.0
            
            for batch_idx, (specs, labels) in enumerate(train_loader):
                specs = specs.to(self.device)
                labels = labels.to(self.device)
                
                # Forward pass
                optimizer.zero_grad()
                logits = self.model(specs)
                loss = criterion(logits, labels)
                
                # Backward pass
                loss.backward()
                optimizer.step()
                
                # Metrics
                train_loss += loss.item()
                preds = torch.argmax(logits, dim=1)
                train_acc += (preds == labels).sum().item() / len(labels)
            
            # Validation phase
            self.model.eval()
            val_loss = 0.0
            val_acc = 0.0
            
            with torch.no_grad():
                for specs, labels in val_loader:
                    specs = specs.to(self.device)
                    labels = labels.to(self.device)
                    
                    logits = self.model(specs)
                    loss = criterion(logits, labels)
                    
                    val_loss += loss.item()
                    preds = torch.argmax(logits, dim=1)
                    val_acc += (preds == labels).sum().item() / len(labels)
            
            # Average metrics
            train_loss /= len(train_loader)
            train_acc /= len(train_loader)
            val_loss /= len(val_loader)
            val_acc /= len(val_loader)
            
            # Print progress
            if (epoch + 1) % max(1, epochs // 10) == 0:
                print(f"Epoch {epoch+1}/{epochs}")
                print(f"  Train: loss={train_loss:.4f}, acc={train_acc:.4f}")
                print(f"  Val:   loss={val_loss:.4f}, acc={val_acc:.4f}\n")
        
        # Save model
        self.save_model()
        print(f"✓ Training complete! Model saved to {self.model_save_path}")

    def save_model(self):
        """Save trained model to disk."""
        Path(self.model_save_path).parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.model, self.model_save_path)

    def evaluate(self, data_dir: str, batch_size: int = 32):
        """Evaluate model on a dataset."""
        if self.model is None:
            raise RuntimeError("Model not loaded. Train first or load from file.")
        
        dataset = AlarmSpectrogramDataset(data_dir)
        loader = DataLoader(dataset, batch_size=batch_size)
        
        self.model.eval()
        correct = 0
        total = 0
        
        with torch.no_grad():
            for specs, labels in loader:
                specs = specs.to(self.device)
                labels = labels.to(self.device)
                
                logits = self.model(specs)
                preds = torch.argmax(logits, dim=1)
                
                correct += (preds == labels).sum().item()
                total += len(labels)
        
        accuracy = correct / total
        print(f"✓ Evaluation: {accuracy*100:.2f}% accuracy ({correct}/{total})")
        
        return accuracy


# CLI usage example
if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', required=True, help='Data directory')
    parser.add_argument('--epochs', type=int, default=50)
    parser.add_argument('--batch-size', type=int, default=32)
    parser.add_argument('--lr', type=float, default=1e-3)
    parser.add_argument('--output', default='models/alarm_detector_cnn.pt')
    
    args = parser.parse_args()
    
    trainer = AlarmCNNTrainer(args.output)
    trainer.train(
        data_dir=args.data,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
    )
