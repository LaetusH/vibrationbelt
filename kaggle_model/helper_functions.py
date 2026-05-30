def load_and_process_audio(file_path, target_sr=16000):
    """
    Load and preprocess audio file for YAMNet analysis
    
    Args:
        file_path (str): Path to audio file
        target_sr (int): Target sample rate (YAMNet requires 16kHz)
    
    Returns:
        numpy.ndarray: Processed audio data
    """
    print(f"Loading audio file: {file_path}")
    
    # Load audio file
    audio, sr = librosa.load(file_path, sr=target_sr)
    
    # Ensure audio is mono
    if len(audio.shape) > 1:
        print("Converting stereo to mono...")
        audio = np.mean(audio, axis=1)
    
    print(f"Audio duration: {len(audio)/target_sr:.2f} seconds")
    return audio

def analyze_audio(audio_data, model, class_names, confidence_threshold=0.1):
    """
    Analyze audio data using YAMNet and return predictions
    
    Args:
        audio_data (numpy.ndarray): Audio data to analyze
        model: YAMNet model
        class_names (list): List of class names
        confidence_threshold (float): Minimum confidence score to include
    
    Returns:
        tuple: (results, scores)
    """
    # Get model predictions
    scores, embeddings, spectrogram = model(audio_data)
    scores = scores.numpy()
    
    # Get top predictions
    top_indices = np.argsort(scores.mean(axis=0))[-5:][::-1]
    
    results = []
    for idx in top_indices:
        score = scores.mean(axis=0)[idx]
        if score > confidence_threshold:
            results.append({
                'class': class_names[idx],
                'confidence': score
            })
    
    return results, scores

def plot_audio_analysis(audio_data, results, sample_rate=16000):
    """
    Create a comprehensive visualization of audio analysis
    
    Args:
        audio_data (numpy.ndarray): Audio data
        results (list): Analysis results
        sample_rate (int): Audio sample rate
    """
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
    
    # Plot waveform
    time = np.arange(len(audio_data)) / sample_rate
    ax1.plot(time, audio_data)
    ax1.set_title('Audio Waveform')
    ax1.set_xlabel('Time (seconds)')
    ax1.set_ylabel('Amplitude')
    ax1.grid(True)
    
    # Plot predictions
    pred_df = pd.DataFrame(results)
    
    sns.barplot(data=pred_df, x='confidence', y='class', ax=ax2)
    ax2.set_title('Top Sound Classifications')
    ax2.set_xlabel('Confidence Score')
    
    plt.tight_layout()
    plt.show()

def plot_spectrogram(audio_data, sample_rate=16000):
    """
    Plot the spectrogram of the audio data
    """
    plt.figure(figsize=(12, 8))
    D = librosa.amplitude_to_db(np.abs(librosa.stft(audio_data)), ref=np.max)
    librosa.display.specshow(D, sr=sample_rate, x_axis='time', y_axis='hz')
    plt.colorbar(format='%+2.0f dB')
    plt.title('Audio Spectrogram')
    plt.show()

def plot_detection_summary(summary_df):
    """
    Plot detection rate summary
    
    Args:
        summary_df (pandas.DataFrame): Summary dataframe
    """
    plt.figure(figsize=(10, 6))
    plot_data = summary_df.groupby('category')['emergency_detected'].mean().reset_index()
    sns.barplot(data=plot_data, x='category', y='emergency_detected')
    plt.title('Emergency Sound Detection Rate by Category')
    plt.xlabel('Category')
    plt.ylabel('Detection Rate')
    plt.xticks(rotation=45)
    plt.tight_layout()