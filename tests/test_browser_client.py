"""Tests that the browser client is served correctly and holds no game logic.

Run from the project root:
    python3 -m unittest discover -s tests -t . -v
"""

import pathlib
import re
import unittest

from server import create_app
from word_manager import DEFAULT_WORDS_DIR, DIFFICULTIES, load_word_file

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


class ServesClientTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    def get(self, url):
        response = self.client.get(url)
        self.addCleanup(response.close)
        return response

    def test_index_is_served_at_root(self):
        response = self.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)
        html = response.get_data(as_text=True)
        for element_id in ["new-game-form", "new-game", "word", "lives-count",
                           "guessed", "missed", "message", "keyboard", "drawing"]:
            with self.subTest(element_id=element_id):
                self.assertIn(f'id="{element_id}"', html)

    def test_index_has_all_three_difficulties(self):
        html = self.get("/").get_data(as_text=True)
        for difficulty in DIFFICULTIES:
            self.assertIn(f'value="{difficulty}"', html)

    def test_index_links_css_and_js(self):
        html = self.get("/").get_data(as_text=True)
        self.assertIn('href="/static/style.css"', html)
        self.assertIn('src="/static/app.js"', html)

    def test_static_assets_are_served(self):
        for path, content_type in [("/static/style.css", "text/css"),
                                   ("/static/app.js", "javascript")]:
            with self.subTest(path=path):
                response = self.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(content_type, response.content_type)

    def test_drawing_has_six_parts(self):
        html = self.get("/").get_data(as_text=True)
        parts = re.findall(r'data-part="(\d)"', html)
        self.assertEqual(sorted(parts), ["1", "2", "3", "4", "5", "6"])

    def test_viewport_meta_for_mobile(self):
        self.assertIn('name="viewport"', self.get("/").get_data(as_text=True))

    def test_unknown_non_api_page_is_404(self):
        self.assertEqual(self.get("/nope").status_code, 404)


class ClientHasNoGameLogicTests(unittest.TestCase):
    """The browser must rely on the server and never hold the hidden word."""

    @classmethod
    def setUpClass(cls):
        cls.js = (STATIC / "app.js").read_text(encoding="utf-8")

    def test_uses_fetch_and_the_rest_endpoints(self):
        self.assertIn("fetch(", self.js)
        self.assertIn('"/api/games"', self.js)
        self.assertIn("/guess", self.js)

    def test_does_not_load_word_lists(self):
        for needle in ["words/", ".txt", "easy.txt", "medium.txt", "hard.txt"]:
            self.assertNotIn(needle, self.js)

    def test_contains_no_words_from_the_lists(self):
        all_words = set()
        for difficulty in DIFFICULTIES:
            all_words.update(load_word_file(DEFAULT_WORDS_DIR / f"{difficulty}.txt"))
        literals = set(re.findall(r'["\'`]([a-z]+)["\'`]', self.js))
        dom_vocabulary = {"button"}  # e.g. key.type = "button" (also in medium.txt)
        self.assertEqual((literals - dom_vocabulary) & all_words, set())

    def test_reads_word_only_after_game_ends(self):
        # Every use of game.word must be inside a won/lost branch.
        for line in self.js.splitlines():
            if "game.word" in line:
                self.assertTrue(
                    "lost" in line or "won" in line or "Solved" in line or "Out of guesses" in line,
                    f"game.word used outside an end-of-game branch: {line.strip()}",
                )


if __name__ == "__main__":
    unittest.main()
