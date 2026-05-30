#!/usr/bin/env python3
"""
Train CNN model for alarm detection.
"""

import numpy as np                                                                                                                                                                     
from pathlib import Path                                                                                                                                                               
import sys                                                                                                                                                                             
                                                                                                                                                                                         
try:                                                                                                                                                                                   
    import torch                                                                                                                                                                       
    import torch.nn as nn                                                                                                                                                              
    import torch.optim as optim                                                                                                                                                        
    from torch.utils.data import Dataset, DataLoader, random_split                                                                                                                     
    from torch.utils.tensorboard import SummaryWriter                                                                                                                                  
except ImportError:                                                                                                                                                                    
    print("❌ PyTorch required. Install with:")                                                                                                                                        
    print("   pip3 install torch")                                                                                                                                                     
    print("   or: python3 -m pip install --upgrade torch")                                                                                                                             
    sys.exit(1) 


class SpectrogramDataset(Dataset):
    """Load spectrograms for training."""
    
    def __init__(self, data_dir, label):
        self.data_dir = Path(data_dir)
        self.label = label
        self.files = list(self.data_dir.glob("*.npy"))
    
    def __len__(self):
        return len(self.files)
    
    def __getitem__(self, idx):
        spec = np.load(self.files[idx]).astype(np.float32)
        
        # Ensure 3D: (1, 224, 224)
        if spec.ndim == 2:
            spec = spec[np.newaxis, :]
        
        return torch.from_numpy(spec), torch.tensor(self.label, dtype=torch.long)


class AlarmCNN(nn.Module):
    """Lightweight CNN for alarm detection."""
    
    def __init__(self):
        super().__init__()
        
        # Conv block 1: (1, 224, 224) → (16, 112, 112)
        self.conv1 = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.BatchNorm2d(16),
        )
        
        # Conv block 2: (16, 112, 112) → (32, 56, 56)
        self.conv2 = nn.Sequential(
            nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.BatchNorm2d(32),
        )
        
        # Conv block 3: (32, 56, 56) → (64, 28, 28)
        self.conv3 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.BatchNorm2d(64),
        )
        
        # Conv block 4: (64, 28, 28) → (128, 14, 14)
        self.conv4 = nn.Sequential(
            nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.BatchNorm2d(128),
        )
        
        # Global average pooling
        self.global_pool = nn.AdaptiveAvgPool2d((1, 1))
        
        # Classifier
        self.classifier = nn.Sequential(
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(32, 2),  # 2 classes: alarm, not-alarm
        )
    
    def forward(self, x):
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        x = self.global_pool(x)
        x = x.view(x.size(0), -1)
        x = self.classifier(x)
        return x


def train_epoch(model, loader, optimizer, criterion, device):
    """Train for one epoch."""
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0
    
    for batch_idx, (specs, labels) in enumerate(loader):
        specs = specs.to(device)
        labels = labels.to(device)
        
        # Forward pass
        optimizer.zero_grad()
        outputs = model(specs)
        loss = criterion(outputs, labels)
        
        # Backward pass
        loss.backward()
        optimizer.step()
        
        # Statistics
        total_loss += loss.item()
        _, predicted = outputs.max(1)
        correct += predicted.eq(labels).sum().item()
        total += labels.size(0)
        
        if (batch_idx + 1) % 5 == 0:
            print(f"  Batch {batch_idx+1}/{len(loader)}: Loss={loss.item():.4f}")
    
    accuracy = 100.0 * correct / total
    avg_loss = total_loss / len(loader)
    return avg_loss, accuracy


def evaluate(model, loader, criterion, device):
    """Evaluate model on test set."""
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0
    
    with torch.no_grad():
        for specs, labels in loader:
            specs = specs.to(device)
            labels = labels.to(device)
            
            outputs = model(specs)
            loss = criterion(outputs, labels)
            
            total_loss += loss.item()
            _, predicted = outputs.max(1)
            correct += predicted.eq(labels).sum().item()
            total += labels.size(0)
    
    accuracy = 100.0 * correct / total
    avg_loss = total_loss / len(loader)
    return avg_loss, accuracy


def main():
    print("=" * 70)
    print("🧠 CNN TRAINING FOR ALARM DETECTION")
    print("=" * 70)
    
    # Configuration
    batch_size = 16
    epochs = 30
    learning_rate = 0.001
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    print(f"\n⚙️  Configuration:")
    print(f"  Device: {device}")
    print(f"  Batch Size: {batch_size}")
    print(f"  Epochs: {epochs}")
    print(f"  Learning Rate: {learning_rate}\n")
    
    # Load datasets
    print("📁 Loading data...")
    alarm_dataset = SpectrogramDataset("train_spectrograms/alarm", label=1)
    noise_dataset = SpectrogramDataset("train_spectrograms/noise", label=0)
    
    # Combine and split
    full_dataset = torch.utils.data.ConcatDataset([alarm_dataset, noise_dataset])
    train_size = int(0.8 * len(full_dataset))
    test_size = len(full_dataset) - train_size
    train_dataset, test_dataset = random_split(full_dataset, [train_size, test_size])
    
    print(f"  Total samples: {len(full_dataset)}")
    print(f"  Train: {len(train_dataset)}, Test: {len(test_dataset)}\n")
    
    # Data loaders
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    
    # Model
    print("🧠 Building model...")
    model = AlarmCNN().to(device)
    print(f"  Parameters: {sum(p.numel() for p in model.parameters()):,}\n")
    
    # Optimizer and criterion
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.CrossEntropyLoss()
    
    # Training loop
    print("🚀 Starting training...\n")
    best_accuracy = 0.0
    best_model = None
    
    for epoch in range(epochs):
        print(f"Epoch {epoch+1}/{epochs}")
        
        # Train
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, criterion, device)
        print(f"  Train: Loss={train_loss:.4f}, Accuracy={train_acc:.1f}%")
        
        # Evaluate
        test_loss, test_acc = evaluate(model, test_loader, criterion, device)
        print(f"  Test:  Loss={test_loss:.4f}, Accuracy={test_acc:.1f}%")
        
        # Save best model
        if test_acc > best_accuracy:
            best_accuracy = test_acc
            best_model = model.state_dict()
            print(f"  💾 Saved best model (acc={best_accuracy:.1f}%)")
        
        print()
    
    # Save final model
    print("=" * 70)
    print("✅ TRAINING COMPLETE!")
    print("=" * 70)
    
    model_path = Path("models/alarm_detector.pt")
    model_path.parent.mkdir(exist_ok=True)
    
    if best_model is not None:
        model.load_state_dict(best_model)
    
    torch.save(model.state_dict(), model_path)
    print(f"\n💾 Model saved: {model_path.absolute()}")
    print(f"   Best Test Accuracy: {best_accuracy:.1f}%")
    
    # Print model info
    print(f"\n📊 Model Info:")
    print(f"  Architecture: AlarmCNN")
    print(f"  Parameters: {sum(p.numel() for p in model.parameters()):,}")
    print(f"  Output: 2 classes (alarm=1, noise=0)")


if __name__ == "__main__":
    main()
