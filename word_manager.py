"""Word list loading and random word selection.

Word lists live in words/<difficulty>.txt, one word per line.

Loading rules:
- Words are stripped and normalized to lowercase.
- Blank lines are skipped.
- Duplicates are removed (first occurrence kept).
- Any entry that is not purely a-z raises WordListError, naming the file
  and line, so a bad list is caught when the server starts rather than in
  the middle of a game.
- An empty or missing list also raises WordListError.

This module does not depend on Flask or game.py.
"""

import pathlib
import random
import string

DIFFICULTIES = ("easy", "medium", "hard")
DEFAULT_WORDS_DIR = pathlib.Path(__file__).resolve().parent / "words"
_ALPHABET = set(string.ascii_lowercase)


class InvalidDifficultyError(ValueError):
    """Raised when a difficulty is not one of DIFFICULTIES."""


class WordListError(ValueError):
    """Raised when a word list file is missing, empty, or malformed."""


def normalize_difficulty(difficulty):
    """Return the canonical difficulty name, or raise InvalidDifficultyError.

    Accepts any case and surrounding whitespace, e.g. " Medium ".
    """
    if isinstance(difficulty, str):
        name = difficulty.strip().lower()
        if name in DIFFICULTIES:
            return name
    raise InvalidDifficultyError(
        f"difficulty must be one of: {', '.join(DIFFICULTIES)}"
    )


def load_word_file(path):
    """Load one word list file and return its words as a list."""
    path = pathlib.Path(path)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        raise WordListError(f"word list not found: {path}") from None

    words = []
    seen = set()
    for line_number, line in enumerate(lines, start=1):
        word = line.strip().lower()
        if not word:
            continue
        if not all(ch in _ALPHABET for ch in word):
            raise WordListError(
                f"{path.name} line {line_number}: {line.strip()!r} "
                "must contain only letters a-z"
            )
        if word not in seen:
            seen.add(word)
            words.append(word)

    if not words:
        raise WordListError(f"word list is empty: {path}")
    return words


class WordManager:
    """Holds the Easy, Medium, and Hard word lists and picks random words."""

    def __init__(self, words_dir=DEFAULT_WORDS_DIR, rng=None):
        self._words_dir = pathlib.Path(words_dir)
        self._rng = rng if rng is not None else random.Random()
        self._lists = {
            difficulty: tuple(load_word_file(self._words_dir / f"{difficulty}.txt"))
            for difficulty in DIFFICULTIES
        }

    def words(self, difficulty):
        """Return all words for a difficulty as a tuple."""
        return self._lists[normalize_difficulty(difficulty)]

    def random_word(self, difficulty):
        """Return a random word from the list for the given difficulty."""
        return self._rng.choice(self.words(difficulty))
