"""Flask server and REST API for Hangman.

The server is authoritative: it picks the word, applies every guess through
the game engine (game.py), and sends back only client-safe state. The hidden
word is included only after a game is won or lost.

Endpoints:
    POST /api/games                   create a game   {"difficulty": "easy"}
    GET  /api/games/<game_id>         current state
    POST /api/games/<game_id>/guess   guess a letter  {"letter": "e"}

Every /api response is JSON, including errors: {"error": "<message>"}.

Run locally:
    python3 server.py
"""

import os
import threading
import uuid

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from game import HangmanGame, InvalidGuessError
from word_manager import InvalidDifficultyError, WordManager


def json_error(message, status):
    return jsonify({"error": message}), status


def create_app(word_manager=None):
    """Build a Flask app with its own in-memory game store.

    Tests pass a WordManager with a seeded random generator or a small word
    list. The default loads the real words/ folder.
    """
    app = Flask(__name__)
    app.json.sort_keys = False  # keep response fields in a readable order

    words = word_manager if word_manager is not None else WordManager()
    games = {}  # game_id -> {"game": HangmanGame, "difficulty": str}
    lock = threading.Lock()  # guards games and every guess

    def game_response(game_id):
        entry = games[game_id]
        return {
            "game_id": game_id,
            "difficulty": entry["difficulty"],
            **entry["game"].to_state(),
        }

    def read_json_object():
        """Return the request body as a dict, or None if it is not one."""
        body = request.get_json(force=True, silent=True)
        return body if isinstance(body, dict) else None

    # ----- routes ------------------------------------------------------------

    @app.post("/api/games")
    def create_game():
        body = read_json_object()
        if body is None:
            return json_error("request body must be a JSON object", 400)
        if "difficulty" not in body:
            return json_error("missing field: difficulty", 400)
        try:
            word = words.random_word(body["difficulty"])
        except InvalidDifficultyError as exc:
            return json_error(str(exc), 400)

        game_id = uuid.uuid4().hex
        with lock:
            games[game_id] = {
                "game": HangmanGame(word),
                "difficulty": body["difficulty"].strip().lower(),
            }
            response = game_response(game_id)
        return jsonify(response), 201

    @app.get("/api/games/<game_id>")
    def get_game(game_id):
        with lock:
            if game_id not in games:
                return json_error("game not found", 404)
            return jsonify(game_response(game_id)), 200

    @app.post("/api/games/<game_id>/guess")
    def guess(game_id):
        body = read_json_object()
        with lock:
            if game_id not in games:
                return json_error("game not found", 404)
            if body is None:
                return json_error("request body must be a JSON object", 400)
            if "letter" not in body:
                return json_error("missing field: letter", 400)
            try:
                games[game_id]["game"].guess(body["letter"])
            except InvalidGuessError as exc:
                return json_error(str(exc), 400)
            return jsonify(game_response(game_id)), 200

    # ----- JSON errors for unknown routes, wrong methods, crashes -------------

    @app.errorhandler(HTTPException)
    def handle_http_error(exc):
        if request.path.startswith("/api/"):
            return json_error(exc.description, exc.code)
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        app.logger.exception("unhandled error")
        return json_error("internal server error", 500)

    return app


app = create_app()


if __name__ == "__main__":
    # Local development only. Production runs under Gunicorn (see TODO Phase 6).
    port = int(os.environ.get("PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG") == "1"
    app.run(host="127.0.0.1", port=port, debug=debug)
