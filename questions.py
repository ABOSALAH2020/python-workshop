QUESTIONS = [
    {
        "id": "discord",
        "topic": "Discord bots",
        "text": "Why should a bot ignore messages sent by itself?",
        "choices": [
            "To avoid replying to its own replies in a loop",
            "To make its token last longer",
            "To save every message in a database",
        ],
        "answer": 0,
        "explanation": "A bot can receive its own messages. Ignoring them prevents an endless reply loop.",
    },
    {
        "id": "flask",
        "topic": "Flask",
        "text": "Which input attribute becomes the key in request.form?",
        "choices": ["class", "id", "name"],
        "answer": 2,
        "explanation": "The browser sends named form fields. The id is useful for labels and page scripting.",
    },
    {
        "id": "ai",
        "topic": "Machine learning",
        "text": "How should you check whether a classifier handles new images?",
        "choices": [
            "Test it only on the images used during training",
            "Use images that were not included in its training data",
            "Choose whichever prediction has the largest confidence number",
        ],
        "answer": 1,
        "explanation": "Unseen test images help reveal whether the model learned useful patterns beyond its training examples.",
    },
    {
        "id": "vision",
        "topic": "Computer vision",
        "text": "What does object detection add to image classification?",
        "choices": [
            "It always removes the background",
            "It translates text in the image",
            "It locates objects, often using bounding boxes",
        ],
        "answer": 2,
        "explanation": "Classification assigns a class. Detection also locates objects and can find several in one image.",
    },
    {
        "id": "nlp",
        "topic": "Natural language processing",
        "text": "What does word tokenization do?",
        "choices": [
            "Splits text into smaller units such as words",
            "Converts every word to its dictionary form",
            "Counts how many websites contain a sentence",
        ],
        "answer": 0,
        "explanation": "Tokenization splits text into units. Lemmatization is a separate step that finds base word forms.",
    },
]
