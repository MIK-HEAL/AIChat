import os

# Project root (assumes this file is in src/)
ROOT = os.path.dirname(os.path.dirname(__file__))

MODEL_PATH = os.path.join(ROOT, 'hiyori_free_zh', 'hiyori_free_zh', 'runtime', 'hiyori_free_t08.model3.json')
FPS = 60

DATA_DIR = os.path.join(ROOT, 'data')
USER_SETTINGS_PATH = os.path.join(DATA_DIR, 'user_settings.json')
AI_PROMPTS_PATH = os.path.join(DATA_DIR, 'ai_prompts.json')
EXPRESSIONS_PATH = os.path.join(DATA_DIR, 'expressions.json')
VISION_DIR = os.path.join(DATA_DIR, 'vision')
