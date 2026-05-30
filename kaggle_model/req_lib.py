# Core libraries
import tensorflow as tf
import tensorflow_hub as hub
import numpy as np
import librosa
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import csv
import urllib.request
import os

print(f"TensorFlow version: {tf.__version__}")
print(f"Librosa version: {librosa.__version__}")

# Set modern plotting style
plt.style.use('seaborn-v0_8-deep')  
sns.set_theme(style="whitegrid")  
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'