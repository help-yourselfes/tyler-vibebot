import json
import os
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEXT_FILE = os.path.join(BASE_DIR, "text.json")

def get_random_motivation():
    try:
        with open(TEXT_FILE, 'r', encoding='utf-8') as f:
            texts = json.load(f)
        return random.choice(texts)
    except Exception:
        return "Ты — это поющее и танцующее дерьмо этого мира."
