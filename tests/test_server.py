"""API tests for the Flask server (server.py), using Flask's test client.

Each test builds a fresh app whose word lists have exactly one word per
difficulty, so the hidden word is known and games are predictable:
    easy -> "cat"   medium -> "planet"   hard -> "adventure"

Run from the project root:
    python3 -m unittest discover -s tests -t . -v
"""

import json
import pathlib
import tempfile
import unittest

from server import create_app
from word_manager import WordManager

WORDS = {"easy": "cat", "medium": "planet", "hard": "adventure"}
PUBLIC_FIELDS = {"game_id", "difficulty", "pattern", "guessed_letters",
                 "incorrect_letters", "remaining_guesses", "status"}


class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        words_dir = pathlib.Path(self._tmp.name)
        for difficulty, word in WORDS.items():
            (words_dir / f"{difficulty}.txt").write_text(word + "\n")
        self.app = create_app(WordManager(words_dir))
        self.client = self.app.test_client()

    def tearDown(self):
        self._tmp.cleanup()

    # ----- helpers --------------------------------------------------------

    def create(self, difficulty="easy"):
        response = self.client.post("/api/games", json={"difficulty": difficulty})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def guess(self, game_id, letter):
        return self.client.post(f"/api/games/{game_id}/guess", json={"letter": letter})

    def assert_error(self, response, status):
        self.assertEqual(response.status_code, status)
        self.assertTrue(response.is_json, response.data)
        body = response.get_json()
        self.assertIsInstance(body.get("error"), str)
        self.assertTrue(body["error"])
        return body

    def assert_word_hidden(self, response, word):
        body = response.get_json()
        self.assertEqual(body["status"], "playing")
        self.assertNotIn("word", body)
        self.assertNotIn(word, response.get_data(as_text=True))


class CreateGameTests(ApiTestCase):
    def test_create_game_for_each_difficulty(self):
        for difficulty, word in WORDS.items():
            with self.subTest(difficulty=difficulty):
                body = self.create(difficulty)
                self.assertEqual(set(body), PUBLIC_FIELDS)
                self.assertEqual(body["difficulty"], difficulty)
                self.assertEqual(body["pattern"], " ".join("_" * len(word)))
                self.assertEqual(body["guessed_letters"], [])
                self.assertEqual(body["incorrect_letters"], [])
                self.assertEqual(body["remaining_guesses"], 6)
                self.assertEqual(body["status"], "playing")

    def test_difficulty_is_case_insensitive(self):
        self.assertEqual(self.create(" HARD ")["difficulty"], "hard")

    def test_game_ids_are_unique(self):
        ids = {self.create()["game_id"] for _ in range(50)}
        self.assertEqual(len(ids), 50)

    def test_new_game_does_not_reveal_word(self):
        for difficulty, word in WORDS.items():
            with self.subTest(difficulty=difficulty):
                response = self.client.post("/api/games", json={"difficulty": difficulty})
                self.assert_word_hidden(response, word)

    def test_invalid_difficulty(self):
        for bad in ["expert", "", "  ", None, 3, ["easy"], {"x": 1}]:
            with self.subTest(difficulty=bad):
                response = self.client.post("/api/games", json={"difficulty": bad})
                body = self.assert_error(response, 400)
                self.assertIn("easy", body["error"])

    def test_missing_difficulty(self):
        response = self.client.post("/api/games", json={})
        self.assertIn("difficulty", self.assert_error(response, 400)["error"])

    def test_malformed_bodies(self):
        bad_bodies = ["{not json", "", "[]", '"easy"', "42", "null"]
        for raw in bad_bodies:
            with self.subTest(body=raw):
                response = self.client.post(
                    "/api/games", data=raw, content_type="application/json")
                self.assert_error(response, 400)

    def test_json_without_content_type_header_is_accepted(self):
        # e.g. curl -d '{"difficulty":"easy"}' without -H 'Content-Type: ...'
        response = self.client.post(
            "/api/games", data=json.dumps({"difficulty": "easy"}),
            content_type="application/x-www-form-urlencoded")
        self.assertEqual(response.status_code, 201)


class GetGameTests(ApiTestCase):
    def test_get_returns_current_state(self):
        created = self.create("medium")
        self.guess(created["game_id"], "a")
        self.guess(created["game_id"], "z")
        response = self.client.get(f"/api/games/{created['game_id']}")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["game_id"], created["game_id"])
        self.assertEqual(body["pattern"], "_ _ a _ _ _")
        self.assertEqual(body["guessed_letters"], ["a", "z"])
        self.assertEqual(body["incorrect_letters"], ["z"])
        self.assertEqual(body["remaining_guesses"], 5)

    def test_get_matches_last_guess_response(self):
        game_id = self.create()["game_id"]
        guess_body = self.guess(game_id, "c").get_json()
        self.assertEqual(self.client.get(f"/api/games/{game_id}").get_json(), guess_body)

    def test_get_does_not_reveal_word_during_play(self):
        game_id = self.create("hard")["game_id"]
        self.guess(game_id, "a")
        self.assert_word_hidden(self.client.get(f"/api/games/{game_id}"), "adventure")

    def test_unknown_game_id(self):
        for bad in ["nope", "0" * 32, "abc123"]:
            with self.subTest(game_id=bad):
                self.assert_error(self.client.get(f"/api/games/{bad}"), 404)


class GuessTests(ApiTestCase):
    def test_correct_guess(self):
        game_id = self.create("medium")["game_id"]
        response = self.guess(game_id, "e")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["pattern"], "_ _ _ _ e _")
        self.assertEqual(body["guessed_letters"], ["e"])
        self.assertEqual(body["incorrect_letters"], [])
        self.assertEqual(body["remaining_guesses"], 6)
        self.assertEqual(body["status"], "playing")

    def test_incorrect_guess(self):
        game_id = self.create("medium")["game_id"]
        body = self.guess(game_id, "z").get_json()
        self.assertEqual(body["incorrect_letters"], ["z"])
        self.assertEqual(body["remaining_guesses"], 5)

    def test_uppercase_guess_is_accepted(self):
        game_id = self.create()["game_id"]
        self.assertEqual(self.guess(game_id, "C").get_json()["pattern"], "c _ _")

    def test_invalid_letters(self):
        game_id = self.create()["game_id"]
        for bad in ["", "ab", "1", "!", "é", None, 5, ["a"], {"a": 1}]:
            with self.subTest(letter=bad):
                self.assert_error(self.guess(game_id, bad), 400)
        state = self.client.get(f"/api/games/{game_id}").get_json()
        self.assertEqual(state["guessed_letters"], [])
        self.assertEqual(state["remaining_guesses"], 6)

    def test_duplicate_guess(self):
        game_id = self.create()["game_id"]
        self.guess(game_id, "z")
        body = self.assert_error(self.guess(game_id, "z"), 400)
        self.assertIn("already", body["error"])
        self.assert_error(self.guess(game_id, "Z"), 400)
        state = self.client.get(f"/api/games/{game_id}").get_json()
        self.assertEqual(state["remaining_guesses"], 5)

    def test_missing_letter(self):
        game_id = self.create()["game_id"]
        self.assertIn("letter", self.assert_error(
            self.client.post(f"/api/games/{game_id}/guess", json={}), 400)["error"])

    def test_malformed_guess_bodies(self):
        game_id = self.create()["game_id"]
        for raw in ["{oops", "", "[]", '"a"']:
            with self.subTest(body=raw):
                response = self.client.post(f"/api/games/{game_id}/guess",
                                            data=raw, content_type="application/json")
                self.assert_error(response, 400)

    def test_guess_on_unknown_game(self):
        self.assert_error(self.guess("nope", "a"), 404)

    def test_word_hidden_until_last_correct_letter(self):
        game_id = self.create("hard")["game_id"]  # adventure
        for letter in "advent":
            self.assert_word_hidden(self.guess(game_id, letter), "adventure")
        response = self.guess(game_id, "u")
        self.assert_word_hidden(response, "adventure")  # still missing "r"
        final = self.guess(game_id, "r").get_json()
        self.assertEqual(final["status"], "won")
        self.assertEqual(final["word"], "adventure")


class FullGameTests(ApiTestCase):
    def test_win(self):
        game_id = self.create()["game_id"]
        self.guess(game_id, "c")
        self.guess(game_id, "a")
        body = self.guess(game_id, "t").get_json()
        self.assertEqual(body["status"], "won")
        self.assertEqual(body["pattern"], "c a t")
        self.assertEqual(body["word"], "cat")
        self.assertEqual(self.client.get(f"/api/games/{game_id}").get_json()["word"], "cat")

    def test_loss(self):
        game_id = self.create()["game_id"]
        for letter in "bdefg":
            self.assert_word_hidden(self.guess(game_id, letter), "cat")
        body = self.guess(game_id, "h").get_json()
        self.assertEqual(body["status"], "lost")
        self.assertEqual(body["remaining_guesses"], 0)
        self.assertEqual(body["word"], "cat")

    def test_no_guesses_after_game_ends(self):
        game_id = self.create()["game_id"]
        for letter in "cat":
            self.guess(game_id, letter)
        body = self.assert_error(self.guess(game_id, "z"), 400)
        self.assertIn("over", body["error"])
        self.assertEqual(self.client.get(f"/api/games/{game_id}").get_json()["status"], "won")

    def test_new_game_after_finishing_one(self):
        first = self.create()["game_id"]
        for letter in "cat":
            self.guess(first, letter)
        second = self.create()
        self.assertNotEqual(second["game_id"], first)
        self.assertEqual(second["status"], "playing")
        self.assertEqual(second["guessed_letters"], [])
        self.assertEqual(self.guess(second["game_id"], "c").status_code, 200)

    def test_games_are_independent(self):
        a = self.create()["game_id"]
        b = self.create()["game_id"]
        self.guess(a, "z")
        self.guess(a, "c")
        state_b = self.client.get(f"/api/games/{b}").get_json()
        self.assertEqual(state_b["guessed_letters"], [])
        self.assertEqual(state_b["remaining_guesses"], 6)
        self.assertEqual(self.guess(b, "c").status_code, 200)  # not a duplicate in b


class ProtocolTests(ApiTestCase):
    def test_wrong_method_returns_json_405(self):
        self.assert_error(self.client.get("/api/games"), 405)
        game_id = self.create()["game_id"]
        self.assert_error(self.client.delete(f"/api/games/{game_id}"), 405)
        self.assert_error(self.client.get(f"/api/games/{game_id}/guess"), 405)

    def test_unknown_api_route_returns_json_404(self):
        self.assert_error(self.client.get("/api/nothing"), 404)

    def test_every_api_response_is_json(self):
        game_id = self.create()["game_id"]
        responses = [
            self.client.get(f"/api/games/{game_id}"),
            self.guess(game_id, "c"),
            self.guess(game_id, "c"),
            self.client.get("/api/games/missing"),
            self.client.post("/api/games", data="x"),
        ]
        for response in responses:
            with self.subTest(status=response.status_code):
                self.assertTrue(response.is_json)


class RealWordListTests(unittest.TestCase):
    def test_default_app_loads_real_lists(self):
        from server import app
        client = app.test_client()
        for difficulty in ["easy", "medium", "hard"]:
            with self.subTest(difficulty=difficulty):
                response = client.post("/api/games", json={"difficulty": difficulty})
                self.assertEqual(response.status_code, 201)
                self.assertNotIn("word", response.get_json())


if __name__ == "__main__":
    unittest.main()
