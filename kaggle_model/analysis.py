target_classes = [
    'Emergency vehicle', 'Siren', 'Police car (siren)',
    'Ambulance (siren)', 'Fire engine, fire truck (siren)'
]

# Load and analyze example file
example_file = '/kaggle/input/emergency-vehicle-siren-sounds/sounds/ambulance/sound_1.wav'
print("\n🔍 Analyzing example audio file...")

audio_data = load_and_process_audio(example_file)
results, all_scores = analyze_audio(audio_data, model, class_names)

# Visualize results
print("\n📈 Generating visualizations...")
plot_audio_analysis(audio_data, results)
plot_spectrogram(audio_data)

# Print detailed results
print("\n🎯 Analysis Results:")
for r in results:
    print(f"Class: {r['class']:<30} Confidence: {r['confidence']:.3f}")