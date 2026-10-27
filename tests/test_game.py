"""Unit tests for the Hangman game engine (game.py).

Run from the project root:
    python3 -m unittest discover -s tests -t . -v
"""

import ast
import pathlib
import unittest

from game import (
    LOST,
    PLAYING,
    WON,
    DuplicateGuessError,
    GameOverError,
    HangmanGame,
    InvalidGuessError,
)


class NewGameTests(unittest.TestCase):
    def test_initial_state(self):
        game = HangmanGame("eagle")
        self.assertEqual(
            game.to_state(),
            {
                "pattern": "_ _ _ _ _",
                "guessed_letters": [],
                "incorrect_letters": [],
                "remaining_guesses": 6,
                "status": PLAYING,
            },
        )

    def test_word_is_normalized_to_lowercase(self):
        game = HangmanGame("  EaGLe ")
        for letter in "eagl":
            game.guess(letter)
        self.assertEqual(game.to_state()["word"], "eagle")

    def test_custom_max_incorrect(self):
        game = HangmanGame("cat", max_incorrect=3)
        self.assertEqual(game.remaining_guesses, 3)

    def test_invalid_words_are_rejected(self):
        for bad in ["", "   ", "two words", "abc1", "héllo", None, 42]:
            with self.subTest(word=bad):
                with self.assertRaises(ValueError):
                    HangmanGame(bad)

    def test_invalid_max_incorrect_is_rejected(self):
        for bad in [0, -1, "6", 2.5]:
            with self.subTest(max_incorrect=bad):
                with self.assertRaises(ValueError):
                    HangmanGame("cat", max_incorrect=bad)


class GuessTests(unittest.TestCase):
    def setUp(self):
        self.game = HangmanGame("eagle")

    def test_correct_guess_reveals_every_position(self):
        state = self.game.guess("e")
        self.assertEqual(state["pattern"], "e _ _ _ e")
        self.assertEqual(state["guessed_letters"], ["e"])
        self.assertEqual(state["incorrect_letters"], [])
        self.assertEqual(state["remaining_guesses"], 6)
        self.assertEqual(state["status"], PLAYING)

    def test_incorrect_guess_costs_a_life(self):
        state = self.game.guess("z")
        self.assertEqual(state["pattern"], "_ _ _ _ _")
        self.assertEqual(state["guessed_letters"], ["z"])
        self.assertEqual(state["incorrect_letters"], ["z"])
        self.assertEqual(state["remaining_guesses"], 5)

    def test_guesses_are_normalized_to_lowercase(self):
        state = self.game.guess("E")
        self.assertEqual(state["pattern"], "e _ _ _ e")
        self.assertEqual(state["guessed_letters"], ["e"])

    def test_surrounding_whitespace_is_ignored(self):
        state = self.game.guess(" a ")
        self.assertEqual(state["pattern"], "_ a _ _ _")

    def test_guessed_letters_keep_guess_order(self):
        for letter in "zea":
            self.game.guess(letter)
        self.assertEqual(self.game.guessed_letters, ["z", "e", "a"])
        self.assertEqual(self.game.incorrect_letters, ["z"])

    def test_guess_returns_same_dict_as_to_state(self):
        self.assertEqual(self.game.guess("g"), self.game.to_state())

    def test_returned_lists_are_copies(self):
        self.game.guess("z")
        state = self.game.to_state()
        state["guessed_letters"].append("q")
        state["incorrect_letters"].append("q")
        self.assertEqual(self.game.guessed_letters, ["z"])
        self.assertEqual(self.game.incorrect_letters, ["z"])


class InvalidGuessTests(unittest.TestCase):
    def setUp(self):
        self.game = HangmanGame("eagle")

    def assert_rejected_without_change(self, guess, error=InvalidGuessError):
        before = self.game.to_state()
        with self.assertRaises(error):
            self.game.guess(guess)
        self.assertEqual(self.game.to_state(), before)

    def test_invalid_guesses_are_rejected(self):
        for bad in ["", " ", "ab", "ee", "1", "!", "é", "_", None, 5, ["e"]]:
            with self.subTest(guess=bad):
                self.assert_rejected_without_change(bad)

    def test_duplicate_correct_guess_is_rejected(self):
        self.game.guess("e")
        self.assert_rejected_without_change("e", DuplicateGuessError)

    def test_duplicate_incorrect_guess_does_not_cost_a_life(self):
        self.game.guess("z")
        self.assert_rejected_without_change("z", DuplicateGuessError)
        self.assertEqual(self.game.remaining_guesses, 5)

    def test_duplicate_check_ignores_case(self):
        self.game.guess("e")
        self.assert_rejected_without_change("E", DuplicateGuessError)

    def test_error_types_share_a_base_class(self):
        self.assertTrue(issubclass(DuplicateGuessError, InvalidGuessError))
        self.assertTrue(issubclass(GameOverError, InvalidGuessError))
        self.assertTrue(issubclass(InvalidGuessError, ValueError))


class WinLossTests(unittest.TestCase):
    def test_win(self):
        game = HangmanGame("eagle")
        for letter in "eag":
            self.assertEqual(game.guess(letter)["status"], PLAYING)
        state = game.guess("l")
        self.assertEqual(state["status"], WON)
        self.assertEqual(state["pattern"], "e a g l e")
        self.assertEqual(state["word"], "eagle")
        self.assertTrue(game.is_over)

    def test_win_with_misses_keeps_remaining_count(self):
        game = HangmanGame("cat")
        for letter in "xyzcat":
            game.guess(letter)
        state = game.to_state()
        self.assertEqual(state["status"], WON)
        self.assertEqual(state["remaining_guesses"], 3)

    def test_win_on_last_life(self):
        game = HangmanGame("cat")
        for letter in "bdefg":  # five misses, one life left
            game.guess(letter)
        for letter in "ca":
            game.guess(letter)
        state = game.guess("t")
        self.assertEqual(state["status"], WON)
        self.assertEqual(state["remaining_guesses"], 1)

    def test_loss_after_six_misses(self):
        game = HangmanGame("eagle")
        for letter in "bcdfh":
            self.assertEqual(game.guess(letter)["status"], PLAYING)
        state = game.guess("i")
        self.assertEqual(state["status"], LOST)
        self.assertEqual(state["remaining_guesses"], 0)
        self.assertEqual(state["incorrect_letters"], list("bcdfhi"))
        self.assertEqual(state["word"], "eagle")

    def test_loss_respects_custom_max_incorrect(self):
        game = HangmanGame("cat", max_incorrect=2)
        game.guess("x")
        self.assertEqual(game.guess("y")["status"], LOST)

    def test_no_guesses_after_win(self):
        game = HangmanGame("ox")
        game.guess("o")
        game.guess("x")
        with self.assertRaises(GameOverError):
            game.guess("a")
        self.assertEqual(game.guessed_letters, ["o", "x"])

    def test_no_guesses_after_loss(self):
        game = HangmanGame("ox", max_incorrect=1)
        game.guess("z")
        before = game.to_state()
        with self.assertRaises(GameOverError):
            game.guess("o")
        self.assertEqual(game.to_state(), before)


class AnswerDisclosureTests(unittest.TestCase):
    def test_word_hidden_during_play(self):
        game = HangmanGame("eagle")
        self.assertNotIn("word", game.to_state())
        for letter in "eagz":  # still missing "l"
            state = game.guess(letter)
            self.assertEqual(state["status"], PLAYING)
            self.assertNotIn("word", state)
            self.assertNotIn("eagle", repr(state))

    def test_word_hidden_one_letter_from_winning(self):
        game = HangmanGame("eagle")
        for letter in "eag":
            game.guess(letter)
        state = game.to_state()
        self.assertEqual(state["pattern"], "e a g _ e")
        self.assertNotIn("word", state)

    def test_word_hidden_one_miss_from_losing(self):
        game = HangmanGame("eagle")
        for letter in "bcdfh":
            game.guess(letter)
        state = game.to_state()
        self.assertEqual(state["remaining_guesses"], 1)
        self.assertNotIn("word", state)

    def test_state_has_exactly_the_public_fields_during_play(self):
        self.assertEqual(
            set(HangmanGame("eagle").to_state()),
            {"pattern", "guessed_letters", "incorrect_letters",
             "remaining_guesses", "status"},
        )


class IndependenceTests(unittest.TestCase):
    def test_game_module_does_not_import_flask(self):
        source = pathlib.Path(__file__).resolve().parents[1] / "game.py"
        tree = ast.parse(source.read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertNotIn("flask", imported)


if __name__ == "__main__":
    unittest.main()
