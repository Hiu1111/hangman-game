"""End-to-end browser tests: a real Chromium plays Hangman through the page.

These start a real HTTP server with one known word per difficulty:
    easy -> "cat"   medium -> "planet"   hard -> "adventure"

They need Playwright (optional, not in requirements.txt):
    python3 -m pip install playwright
    python3 -m playwright install chromium

If Playwright is not installed, these tests are skipped.
"""

import logging
import pathlib
import tempfile
import threading
import unittest

from werkzeug.serving import make_server

from server import create_app
from word_manager import WordManager

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

WORDS = {"easy": "cat", "medium": "planet", "hard": "adventure"}


@unittest.skipIf(sync_playwright is None, "Playwright is not installed")
class BrowserGameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        words_dir = pathlib.Path(cls._tmp.name)
        for difficulty, word in WORDS.items():
            (words_dir / f"{difficulty}.txt").write_text(word + "\n")
        app = create_app(WordManager(words_dir))

        logging.getLogger("werkzeug").setLevel(logging.ERROR)  # no per-request lines in test output
        cls.server = make_server("127.0.0.1", 0, app, threaded=True)
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls._tmp.cleanup()

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 1200, "height": 900})
        # Skip web fonts so tests do not depend on the internet.
        self.context.route("https://fonts.googleapis.com/**", lambda r: r.abort())
        self.context.route("https://fonts.gstatic.com/**", lambda r: r.abort())
        self.page = self.context.new_page()
        self.console_errors = []
        self.page.on("pageerror", lambda e: self.console_errors.append(str(e)))
        self.page.goto(self.base_url + "/")
        expect(self.page.locator("#word .tile")).to_have_count(3)  # easy game auto-starts

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.console_errors, [], "JavaScript errors on the page")

    # ----- helpers --------------------------------------------------------

    def key(self, letter):
        return self.page.locator(f'.key[data-letter="{letter}"]')

    def tiles_text(self):
        # inner_text applies CSS text-transform, so compare in lowercase.
        return [t.strip().lower() for t in self.page.locator("#word .tile").all_inner_texts()]

    def shown_parts(self):
        return self.page.locator(".part.shown").count()

    def new_game(self, difficulty):
        self.page.locator(f'.difficulty input[value="{difficulty}"]').check()
        self.page.click("#new-game")
        expect(self.page.locator("#word .tile")).to_have_count(len(WORDS[difficulty]))
        expect(self.page.locator("#lives-count")).to_have_text("6")

    # ----- tests ----------------------------------------------------------

    def test_page_starts_a_game_automatically(self):
        expect(self.page.locator("#meta")).to_have_text("Easy word, 3 letters")
        expect(self.page.locator("#lives-count")).to_have_text("6")
        expect(self.page.locator("#guessed")).to_have_text("None yet")
        self.assertEqual(self.page.locator(".key:enabled").count(), 26)
        self.assertEqual(self.shown_parts(), 0)

    def test_start_games_at_every_difficulty(self):
        for difficulty, word in WORDS.items():
            with self.subTest(difficulty=difficulty):
                self.new_game(difficulty)
                expect(self.page.locator("#meta")).to_have_text(
                    f"{difficulty.capitalize()} word, {len(word)} letters")

    def test_click_correct_letter(self):
        self.key("c").click()
        expect(self.page.locator("#word .tile").first).to_have_text("c")
        expect(self.key("c")).to_be_disabled()
        expect(self.key("c")).to_have_class("key hit")
        expect(self.page.locator("#guessed")).to_have_text("C")
        expect(self.page.locator("#lives-count")).to_have_text("6")

    def test_type_wrong_letter_draws_a_part(self):
        self.page.keyboard.press("z")
        expect(self.page.locator("#missed")).to_have_text("Z")
        expect(self.page.locator("#lives-count")).to_have_text("5")
        expect(self.key("z")).to_have_class("key miss")
        expect(self.page.locator(".part.shown")).to_have_count(1)

    def test_repeat_key_press_is_ignored(self):
        self.page.keyboard.press("z")
        expect(self.page.locator("#lives-count")).to_have_text("5")
        self.page.keyboard.press("z")
        self.page.keyboard.press("Z")
        self.page.wait_for_timeout(200)
        expect(self.page.locator("#lives-count")).to_have_text("5")
        expect(self.page.locator("#message")).to_have_text("")

    def test_guess_is_a_fetch_that_returns_json(self):
        with self.page.expect_response(lambda r: r.url.endswith("/guess")) as info:
            self.key("a").click()
        response = info.value
        self.assertEqual(response.request.method, "POST")
        self.assertEqual(response.request.post_data_json, {"letter": "a"})
        self.assertEqual(response.status, 200)
        body = response.json()
        self.assertEqual(body["pattern"], "_ a _")
        self.assertNotIn("word", body)
        expect(self.page.locator("#word .tile").nth(1)).to_have_text("a")

    def test_win_then_new_game_without_reload(self):
        for letter in "zcat":
            self.page.keyboard.press(letter)
        message = self.page.locator("#message")
        expect(message).to_contain_text("Solved!")
        expect(message).to_contain_text("cat")
        self.assertEqual(self.page.locator(".key:enabled").count(), 0)
        expect(self.page.locator("#lives-count")).to_have_text("5")

        # Typing letters after the game ends does nothing.
        self.page.keyboard.press("q")
        expect(self.page.locator("#guessed")).to_have_text("Z C A T")

        # Enter starts a new game on the same page.
        self.page.evaluate("window.__sameDocument = true")
        self.page.keyboard.press("Enter")
        expect(self.page.locator("#guessed")).to_have_text("None yet")
        expect(self.page.locator("#message")).to_have_text("")
        self.assertEqual(self.page.locator(".key:enabled").count(), 26)
        self.assertEqual(self.shown_parts(), 0)
        self.assertTrue(self.page.evaluate("window.__sameDocument === true"))

    def test_loss_reveals_word_and_draws_whole_figure(self):
        self.new_game("medium")  # planet
        for letter in "bcdfgh":
            self.page.keyboard.press(letter)
        expect(self.page.locator("#message")).to_contain_text("Out of guesses")
        expect(self.page.locator("#message")).to_contain_text("planet")
        expect(self.page.locator(".part.shown")).to_have_count(6)
        expect(self.page.locator("#lives-count")).to_have_text("0")
        self.assertEqual(self.tiles_text(), list("planet"))
        expect(self.page.locator(".tile.revealed")).to_have_count(6)
        self.assertEqual(self.page.locator(".key:enabled").count(), 0)

    def test_word_not_in_page_during_play(self):
        self.new_game("hard")  # adventure
        for letter in "adventu":
            self.page.keyboard.press(letter)
        expect(self.page.locator("#guessed")).to_have_text("A D V E N T U")
        self.assertNotIn("adventure", self.page.content())
        page_state = self.page.evaluate("JSON.stringify(window.performance.getEntries())")
        self.assertNotIn("adventure", page_state)
        self.page.keyboard.press("r")
        expect(self.page.locator("#message")).to_contain_text("adventure")

    def test_server_error_is_shown_to_the_user(self):
        self.page.route("**/guess", lambda route: route.fulfill(
            status=400, content_type="application/json",
            body='{"error": "guess must be a single letter a-z"}'))
        self.key("c").click()
        expect(self.page.locator("#message")).to_have_text("guess must be a single letter a-z")
        expect(self.page.locator("#message")).to_have_class("message error")

    def test_lost_game_on_server_is_explained(self):
        self.page.route("**/guess", lambda route: route.fulfill(
            status=404, content_type="application/json", body='{"error": "game not found"}'))
        self.key("c").click()
        expect(self.page.locator("#message")).to_contain_text("Start a new game")

    def test_network_failure_is_shown(self):
        self.page.route("**/guess", lambda route: route.abort())
        self.key("c").click()
        expect(self.page.locator("#message")).to_contain_text("Can't reach the server")

    def test_long_word_stays_on_one_line_on_small_screens(self):
        self.new_game("hard")  # adventure, 9 letters
        for width in [320, 375, 1200]:
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 800})
                tops = {round(box["y"]) for box in (
                    t.bounding_box() for t in self.page.locator("#word .tile").all())}
                self.assertEqual(len(tops), 1, f"tiles wrap onto {len(tops)} lines")

    def test_mobile_layout_has_no_horizontal_scroll(self):
        for width in [320, 375, 414, 768]:
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": 800})
                overflow = self.page.evaluate(
                    "document.documentElement.scrollWidth - document.documentElement.clientWidth")
                self.assertLessEqual(overflow, 0)
                box = self.key("z").bounding_box()
                self.assertGreaterEqual(box["height"], 44)  # comfortable tap target


if __name__ == "__main__":
    unittest.main()
