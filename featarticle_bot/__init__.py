import nltk
import os

from .featarticle_bot import main
from . import main

if not os.path.exists("nltk_data"):
    nltk.download("punkt", download_dir="nltk_data/")