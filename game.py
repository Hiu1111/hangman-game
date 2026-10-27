"""Hangman game engine.

This module holds all Hangman rules. It has no dependency on Flask or any
user interface, so it can be used and tested on its own.

Design decisions (see TODO.md):
- Words and guesses are normalized to lowercase.
- A guess must be a single letter a-z.
- Duplicate guesses, invalid guesses, and guesses after the game ends are
  rejected with an exception and do not change the game state.
- The pattern shows letters separated by spaces, e.g. "_ e _ _ e".
- The hidden word appears in the state only after the game is won or lost.
"""

import string

PLAYING = "playing"
WON = "won"
LOST = "lost"

DEFAULT_MAX_INCORRECT = 6
ALPHABET = set(string.ascii_lowercase)


class InvalidGuessError(ValueError):
    """Raised when a guess is not allowed. Game state is left unchanged."""


class DuplicateGuessError(InvalidGuessError):
    """Raised when a letter has already been guessed."""


class GameOverError(InvalidGuessError):
    """Raised when a guess is made after the game has ended."""


class HangmanGame:
    """One game of Hangman for a single hidden word."""

    def __init__(self, word, max_incorrect=DEFAULT_MAX_INCORRECT):
        if not isinstance(word, str):
            raise ValueError("word must be a string")
        word = word.strip().lower()
        if not word or not all(ch in ALPHABET for ch in word):
            raise ValueError("word must contain only letters a-z")
        if not isinstance(max_incorrect, int) or max_incorrect < 1:
            raise ValueError("max_incorrect must be a positive integer")

        self._word = word
        self._max_incorrect = max_incorrect
        self._guessed = []  # every accepted guess, in the order it was made
        self._incorrect = []  # accepted guesses that are not in the word

    # ----- read-only properties -------------------------------------------

    @property
    def max_incorrect(self):
        return self._max_incorrect

    @property
    def guessed_letters(self):
        return list(self._guessed)

    @property
    def incorrect_letters(self):
        return list(self._incorrect)

    @property
    def remaining_guesses(self):
        return self._max_incorrect - len(self._incorrect)

    @property
    def pattern(self):
        return " ".join(ch if ch in self._guessed else "_" for ch in self._word)

    @property
    def status(self):
        if all(ch in self._guessed for ch in self._word):
            return WON
        if self.remaining_guesses <= 0:
            return LOST
        return PLAYING

    @property
    def is_over(self):
        return self.status != PLAYING

    # ----- actions ---------------------------------------------------------

    def guess(self, letter):
        """Apply one letter guess and return the updated client-safe state.

        Raises InvalidGuessError (or a subclass) if the guess is not allowed.
        A rejected guess never changes the game state.
        """
        if self.is_over:
            raise GameOverError("the game is already over")
        if not isinstance(letter, str):
            raise InvalidGuessError("guess must be a single letter a-z")

        letter = letter.strip().lower()
        if len(letter) != 1 or letter not in ALPHABET:
            raise InvalidGuessError("guess must be a single letter a-z")
        if letter in self._guessed:
            raise DuplicateGuessError(f"'{letter}' has already been guessed")

        self._guessed.append(letter)
        if letter not in self._word:
            self._incorrect.append(letter)
        return self.to_state()

    def to_state(self):
        """Return a dict that is safe to send to a client.

        The hidden word is included only when the game is won or lost.
        """
        state = {
            "pattern": self.pattern,
            "guessed_letters": self.guessed_letters,
            "incorrect_letters": self.incorrect_letters,
            "remaining_guesses": self.remaining_guesses,
            "status": self.status,
        }
        if self.is_over:
            state["word"] = self._word
        return state
