"""Unit tests for word loading and random word selection (word_manager.py).

Run from the project root:
    python3 -m unittest discover -s tests -t . -v
"""

import pathlib
import random
import tempfile
import unittest

from game import HangmanGame
from word_manager import (
    DEFAULT_WORDS_DIR,
    DIFFICULTIES,
    InvalidDifficultyError,
    WordListError,
    WordManager,
    load_word_file,
    normalize_difficulty,
)


class TempWordsMixin:
    """Creates a temporary words/ folder for each test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, text):
        path = self.dir / name
        path.write_text(text, encoding="utf-8")
        return path

    def write_all(self, easy="cat\ndog\n", medium="planet\nrocket\n",
                  hard="adventure\nxylophone\n"):
        self.write("easy.txt", easy)
        self.write("medium.txt", medium)
        self.write("hard.txt", hard)


class LoadWordFileTests(TempWordsMixin, unittest.TestCase):
    def test_loads_one_word_per_line(self):
        path = self.write("easy.txt", "cat\ndog\nfish\n")
        self.assertEqual(load_word_file(path), ["cat", "dog", "fish"])

    def test_normalizes_case_and_whitespace(self):
        path = self.write("easy.txt", "  Cat \nDOG\n\tfish\t\n")
        self.assertEqual(load_word_file(path), ["cat", "dog", "fish"])

    def test_skips_blank_lines(self):
        path = self.write("easy.txt", "\ncat\n\n   \ndog\n\n")
        self.assertEqual(load_word_file(path), ["cat", "dog"])

    def test_removes_duplicates_keeping_first(self):
        path = self.write("easy.txt", "cat\ndog\ncat\nCAT\ndog\nfish\n")
        self.assertEqual(load_word_file(path), ["cat", "dog", "fish"])

    def test_handles_windows_line_endings(self):
        path = self.dir / "easy.txt"
        path.write_bytes(b"cat\r\ndog\r\n")
        self.assertEqual(load_word_file(path), ["cat", "dog"])

    def test_handles_missing_final_newline(self):
        path = self.write("easy.txt", "cat\ndog")
        self.assertEqual(load_word_file(path), ["cat", "dog"])

    def test_rejects_non_alphabetic_entries(self):
        for bad in ["c4t", "ice cream", "e-mail", "don't", "café", "a_b", "x."]:
            with self.subTest(entry=bad):
                path = self.write("easy.txt", f"cat\n{bad}\ndog\n")
                with self.assertRaises(WordListError) as ctx:
                    load_word_file(path)
                self.assertIn("line 2", str(ctx.exception))
                self.assertIn("easy.txt", str(ctx.exception))

    def test_rejects_empty_file(self):
        for text in ["", "\n\n", "   \n  \n"]:
            with self.subTest(text=text):
                path = self.write("easy.txt", text)
                with self.assertRaises(WordListError):
                    load_word_file(path)

    def test_rejects_missing_file(self):
        with self.assertRaises(WordListError):
            load_word_file(self.dir / "nope.txt")


class NormalizeDifficultyTests(unittest.TestCase):
    def test_accepts_valid_difficulties(self):
        cases = {"easy": "easy", "Medium": "medium", " HARD ": "hard"}
        for given, expected in cases.items():
            with self.subTest(difficulty=given):
                self.assertEqual(normalize_difficulty(given), expected)

    def test_rejects_invalid_difficulties(self):
        for bad in ["", "expert", "easyy", "e", "1", None, 1, ["easy"]]:
            with self.subTest(difficulty=bad):
                with self.assertRaises(InvalidDifficultyError):
                    normalize_difficulty(bad)

    def test_error_is_a_value_error_and_lists_options(self):
        with self.assertRaises(ValueError) as ctx:
            normalize_difficulty("expert")
        for name in DIFFICULTIES:
            self.assertIn(name, str(ctx.exception))


class WordManagerTests(TempWordsMixin, unittest.TestCase):
    def test_loads_all_three_lists(self):
        self.write_all()
        manager = WordManager(self.dir)
        self.assertEqual(manager.words("easy"), ("cat", "dog"))
        self.assertEqual(manager.words("medium"), ("planet", "rocket"))
        self.assertEqual(manager.words("hard"), ("adventure", "xylophone"))

    def test_random_word_comes_from_the_right_list(self):
        self.write_all()
        manager = WordManager(self.dir)
        for difficulty in DIFFICULTIES:
            for _ in range(50):
                with self.subTest(difficulty=difficulty):
                    self.assertIn(manager.random_word(difficulty),
                                  manager.words(difficulty))

    def test_random_word_accepts_any_case(self):
        self.write_all()
        manager = WordManager(self.dir)
        self.assertIn(manager.random_word(" Hard "), ("adventure", "xylophone"))

    def test_random_word_rejects_invalid_difficulty(self):
        self.write_all()
        manager = WordManager(self.dir)
        for bad in ["expert", "", None]:
            with self.subTest(difficulty=bad):
                with self.assertRaises(InvalidDifficultyError):
                    manager.random_word(bad)

    def test_random_word_eventually_returns_every_word(self):
        self.write_all(easy="cat\ndog\nfish\nbird\n")
        manager = WordManager(self.dir, rng=random.Random(0))
        seen = {manager.random_word("easy") for _ in range(200)}
        self.assertEqual(seen, {"cat", "dog", "fish", "bird"})

    def test_seeded_rng_is_reproducible(self):
        self.write_all(easy="cat\ndog\nfish\nbird\nfrog\n")
        a = WordManager(self.dir, rng=random.Random(42))
        b = WordManager(self.dir, rng=random.Random(42))
        self.assertEqual([a.random_word("easy") for _ in range(20)],
                         [b.random_word("easy") for _ in range(20)])

    def test_missing_difficulty_file_fails_at_startup(self):
        self.write("easy.txt", "cat\n")
        self.write("medium.txt", "planet\n")
        with self.assertRaises(WordListError):
            WordManager(self.dir)

    def test_bad_entry_fails_at_startup(self):
        self.write_all(medium="planet\nr0cket\n")
        with self.assertRaises(WordListError) as ctx:
            WordManager(self.dir)
        self.assertIn("medium.txt", str(ctx.exception))

    def test_word_lists_cannot_be_modified_by_callers(self):
        self.write_all()
        manager = WordManager(self.dir)
        self.assertIsInstance(manager.words("easy"), tuple)


class ProjectWordListTests(unittest.TestCase):
    """Checks the real words/ folder shipped with the project."""

    @classmethod
    def setUpClass(cls):
        cls.manager = WordManager(DEFAULT_WORDS_DIR)

    def test_default_folder_loads(self):
        for difficulty in DIFFICULTIES:
            with self.subTest(difficulty=difficulty):
                self.assertGreater(len(self.manager.words(difficulty)), 0)

    def test_every_word_starts_a_valid_game(self):
        for difficulty in DIFFICULTIES:
            for word in self.manager.words(difficulty):
                with self.subTest(word=word):
                    state = HangmanGame(word).to_state()
                    self.assertEqual(state["status"], "playing")
                    self.assertEqual(state["pattern"].count("_"), len(word))

    def test_random_word_from_each_difficulty_starts_a_game(self):
        for difficulty in DIFFICULTIES:
            with self.subTest(difficulty=difficulty):
                word = self.manager.random_word(difficulty)
                self.assertIn(word, self.manager.words(difficulty))
                HangmanGame(word)

    def test_harder_lists_have_longer_words_on_average(self):
        avg = {d: sum(map(len, self.manager.words(d))) / len(self.manager.words(d))
               for d in DIFFICULTIES}
        self.assertLess(avg["easy"], avg["medium"])
        self.assertLess(avg["medium"], avg["hard"])


if __name__ == "__main__":
    unittest.main()
