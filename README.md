# Hangman

A web-based Hangman game with a Python/Flask backend and an HTML/CSS/JavaScript frontend,
built for the CSE 4095 (Agentic Programming) assignment.

**Live app:** https://hangman-1xvr.onrender.com/

Pick Easy, Medium, or Hard, then guess the word one letter at a time by clicking the on-screen
keyboard or typing. Six wrong guesses and the figure is complete.

---

## How it works

The server is authoritative. The browser never knows the hidden word while a game is in
progress; it only sends guesses and draws whatever the server returns.

```
 Browser (static/app.js)                 Flask (server.py)              Game engine (game.py)
 ───────────────────────                 ─────────────────              ─────────────────────
 click "E" or press E
   └─ fetch POST /api/games/<id>/guess ─▶ guess() route
        body: {"letter": "e"}               validates the request
                                            looks up the game ─────────▶ HangmanGame.guess("e")
                                                                         updates guesses/lives,
                                            JSON state ◀──────────────── returns to_state()
   render() ◀── 200 + JSON state ────────   ("word" only once won/lost)
   redraws word, lives, letters,
   keyboard, and the drawing
```

| File | Role |
|---|---|
| `game.py` | Game rules: validation, pattern, lives, win/loss. No Flask or UI code. |
| `word_manager.py` | Loads `words/*.txt` and picks a random word by difficulty. |
| `server.py` | Flask app: REST API, in-memory game store, serves the web page. |
| `static/` | Browser client: `index.html`, `style.css`, `app.js`. |
| `words/` | Word lists: `easy.txt` (4–6 letters), `medium.txt` (5–8), `hard.txt` (8–11). |
| `tests/` | Unit, API, browser, and deployment tests. |
| `render.yaml`, `.python-version` | Render deployment configuration. |
| `SPECIFICATION.md`, `TODO.md` | Original spec and the reduced-scope implementation plan. |

---

## Run it locally

Requires Python 3.10 or newer (deployed on 3.13).

```bash
git clone <your-repo-url> hangman
cd hangman
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 server.py
```

Open **http://127.0.0.1:5000**. A game starts automatically.

- Change the port: `PORT=8000 python3 server.py`
- Turn on Flask debug mode for local development only: `FLASK_DEBUG=1 python3 server.py`
- Run it the way production does: `gunicorn --bind 127.0.0.1:5000 --workers 1 --threads 4 server:app`

---

## Run the tests

```bash
python3 -m unittest discover -s tests -t . -v
```

This runs 122 tests:

| File | Covers |
|---|---|
| `tests/test_game.py` | Engine rules, duplicate/invalid guesses, win/loss, answer hidden during play |
| `tests/test_word_manager.py` | Loading, cleaning, and validating word lists; random selection |
| `tests/test_server.py` | All endpoints, status codes, malformed requests, request limits |
| `tests/test_browser_client.py` | Page is served; `app.js` uses `fetch()` and contains no words |
| `tests/test_e2e_browser.py` | A real Chromium plays full games through the page |
| `tests/test_deploy.py` | Gunicorn and Render configuration |

The 14 browser tests need Playwright, which is not in `requirements.txt`. Without it they are
skipped and everything else still runs. To include them:

```bash
pip install playwright
python3 -m playwright install chromium
```

---

## REST API

All endpoints take and return JSON. Every game response has the same shape. `word` appears
only after the game is won or lost.

| Method | Endpoint | Body | Success |
|---|---|---|---|
| `POST` | `/api/games` | `{"difficulty": "easy" \| "medium" \| "hard"}` | `201` new game |
| `GET` | `/api/games/{game_id}` | — | `200` current state |
| `POST` | `/api/games/{game_id}/guess` | `{"letter": "e"}` | `200` updated state |

### Create a game

```bash
curl -X POST http://127.0.0.1:5000/api/games \
  -H "Content-Type: application/json" -d '{"difficulty":"medium"}'
```

```json
{
  "game_id": "c6dd9e21fa0340af85ec348ce4dd6445",
  "difficulty": "medium",
  "pattern": "_ _ _ _ _ _",
  "guessed_letters": [],
  "incorrect_letters": [],
  "remaining_guesses": 6,
  "status": "playing"
}
```

### Guess a letter

```bash
curl -X POST http://127.0.0.1:5000/api/games/c6dd9e21fa0340af85ec348ce4dd6445/guess \
  -H "Content-Type: application/json" -d '{"letter":"a"}'
```

```json
{
  "game_id": "c6dd9e21fa0340af85ec348ce4dd6445",
  "difficulty": "medium",
  "pattern": "_ _ _ _ a _",
  "guessed_letters": ["a"],
  "incorrect_letters": [],
  "remaining_guesses": 6,
  "status": "playing"
}
```

When the game ends, `status` becomes `"won"` or `"lost"` and the answer is included:

```json
{
  "game_id": "c6dd9e21fa0340af85ec348ce4dd6445",
  "difficulty": "medium",
  "pattern": "_ _ i t a r",
  "guessed_letters": ["a", "e", "t", "o", "i", "n", "s", "r", "h", "d"],
  "incorrect_letters": ["e", "o", "n", "s", "h", "d"],
  "remaining_guesses": 0,
  "status": "lost",
  "word": "guitar"
}
```

### Get the current state

```bash
curl http://127.0.0.1:5000/api/games/c6dd9e21fa0340af85ec348ce4dd6445
```

Returns the same shape as a guess response.

### Errors

Errors are JSON too: `{"error": "<message>"}`. A rejected guess never changes the game.

| Status | When | Example message |
|---|---|---|
| `400` | Invalid difficulty | `difficulty must be one of: easy, medium, hard` |
| `400` | Missing field | `missing field: letter` |
| `400` | Body is not a JSON object | `request body must be a JSON object` |
| `400` | Guess is not one letter a–z | `guess must be a single letter a-z` |
| `400` | Letter already guessed | `'e' has already been guessed` |
| `400` | Game already won or lost | `the game is already over` |
| `404` | Unknown game ID or route | `game not found` |
| `405` | Wrong HTTP method | `The method is not allowed for the requested URL.` |
| `413` | Request body over 1 KB | `The data value transmitted exceeds the capacity limit.` |
| `500` | Unexpected server error | `internal server error` |

---

## Game rules

- One letter (a–z) per guess. Uppercase and surrounding spaces are accepted.
- Six wrong guesses are allowed. Correct guesses don't cost a life.
- Repeated guesses are rejected (`400`) and don't cost a life.
- The pattern shows letters separated by spaces, for example `"_ e _ _ e"`.
- No guesses are accepted after a game is won or lost.

---

## Deployment (Render)

The app runs on Render's free plan from this GitHub repo using the Blueprint in `render.yaml`.

1. Push the repo to GitHub.
2. In the Render dashboard: **New → Blueprint**, connect GitHub, pick the repo, **Apply**.
3. Render builds with `pip install -r requirements.txt` and starts:

   ```
   gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 4 --access-logfile - server:app
   ```

4. Every push to `main` redeploys automatically.

**Why exactly one worker.** Games are stored in the memory of one Python process. With several
Gunicorn workers, each has its own separate store, so a guess can reach a worker that never
saw the game. In a local test with 3 workers, 8 of 30 first guesses failed with
`game not found`. Threads share memory, so `--threads 4` serves several players at once safely;
`server.py` protects the store with a lock.

---

## Known limitations

- **Free tier sleeps.** Render's free plan stops the service after 15 minutes without traffic.
  The next visit takes about a minute while it starts up again.
- **Games are kept in memory.** A restart, redeploy, or sleep ends every game in progress. If
  that happens mid-game, the page says so and asks the player to start a new game.
- **Refreshing the page starts a new game.** The current game ID isn't saved in the browser.
- **Game store is capped** at 10,000 games; past that, the oldest game is dropped.
- **Font needs the internet.** The handwritten font (Kalam) loads from Google Fonts. Offline, a
  fallback font is used.

---

## Scope and deviations from the specification

`SPECIFICATION.md` describes a larger system. For this assignment, only the game engine, Flask
REST API, browser client, tests, and deployment are implemented. These parts of the spec are
**out of scope**: the terminal client, automated bots, evaluation mode, scoring, leaderboard,
anti-cheating safeguards, and logging/replay.

Where this implementation differs from or adds to the spec:

- **One response shape.** Every game response, including create, returns the full state plus
  `game_id` and `difficulty`. The spec's create example shows fewer fields.
- **Duplicate guesses are rejected** with `400`. The spec allowed "ignored or rejected".
- **The answer field is named `word`** and appears only when `status` is `won` or `lost`.
- **Added protections for a public server:** request bodies over 1 KB are rejected (`413`), and
  the in-memory game store is capped.
- **Word lists are original** and follow the same difficulty bands (easy 4–6 letters,
  medium 5–8, hard 8–11).

---

## Built with

Python 3.13, Flask, Gunicorn, HTML/CSS/JavaScript, Playwright (tests), Render, and an AI coding
agent (Claude), working phase by phase through `TODO.md`.
