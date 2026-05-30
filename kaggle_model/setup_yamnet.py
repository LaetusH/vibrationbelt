def setup_yamnet():
    """
    Setup YAMNet model and load class labels
    Returns:
        tuple: (model, class_names)
    """
    # Download class map if not exists
    class_map_path = 'yamnet_class_map.csv'
    if not os.path.exists(class_map_path):
        print("Downloading YAMNet class map...")
        urllib.request.urlretrieve(
            'https://raw.githubusercontent.com/tensorflow/models/master/research/audioset/yamnet/yamnet_class_map.csv',
            class_map_path)

    # Load class names
    class_names = []
    with open(class_map_path) as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            class_names.append(row['display_name'])

    print("Loading YAMNet model...")
    model = hub.load('https://tfhub.dev/google/yamnet/1')
    print(f"Model loaded successfully! Total classes: {len(class_names)}")
    
    return model, class_names

# Load model and class names
model, class_names = setup_yamnet()