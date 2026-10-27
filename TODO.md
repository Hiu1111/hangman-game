# TODO — Hangman Web App (CSE 4095 Reduced Scope)

This file is the implementation roadmap for the CSE 4095 Hangman assignment.

The authoritative requirements are `SPECIFICATION.md`, reduced to the scope of the assignment:
a Python game engine, a Flask REST API, a browser client, tests, and cloud deployment.

## Implementation Rules

- Implement one phase at a time. Do not ask the agent to build the whole app in one prompt.
- Complete and verify every task in a phase before moving to the next.
- Check off a task only after it has been implemented **and** verified.
- Commit to GitHub at the end of each phase.
- Keep the game engine independent from Flask and the browser UI.
- The server is authoritative: the browser never decides whether a guess is correct.
- Never expose the hidden word while a game's status is `playing`.
- Add tests as each phase is built, not only at the end.
- Document any deviation from `SPECIFICATION.md` in the README.

## Design Decisions (settle before Phase 2)

The specification leaves these open. They are decided here so every phase uses the same contract.

| Question | Decision |
|---|---|
| Duplicate guesses | Rejected with HTTP `400`; game state unchanged |
| Invalid guesses (empty, multi-char, non-letter) | Rejected with HTTP `400`; game state unchanged |
| Guesses after game ends | Rejected with HTTP `400` |
| Letter case | Words and guesses normalized to lowercase |
| Pattern format | Letters separated by spaces, e.g. `"_ e _ _ e"` |
| Max incorrect guesses | 6 |
| Answer field | `word`, included **only** when status is `won` or `lost` |
| Status values | `playing`, `won`, `lost` |
| Game storage | In memory (resets on server restart) |
| Framework | Flask |

---

## Phase 0 — Project Setup

- [x] Create the project directory.
- [x] Add `SPECIFICATION.md` (original, unmodified).
- [x] Add this revised `TODO.md`.
- [x] Add `words/easy.txt`, `words/medium.txt`, `words/hard.txt`.
- [x] Add `.gitignore` (Python caches, virtualenvs, `.env`, `.DS_Store`).
- [x] Add `requirements.txt` (Flask).
- [x] Initialize a local git repository on branch `main` and make the initial commit.
- [ ] Create the GitHub repository, add it as `origin`, and push.

**Done when:** the repo is on GitHub with the spec, TODO, and word lists.

---

## Phase 1 — Game Engine

- [x] Create `game.py` with a `HangmanGame` class (no Flask imports).
- [x] Store the hidden word privately.
- [x] Track guessed letters and incorrect letters.
- [x] Track remaining incorrect guesses (max 6).
- [x] Validate guesses: single letter `a`–`z` only.
- [x] Reject duplicate guesses.
- [x] Generate the masked pattern.
- [x] Detect wins and losses.
- [x] Reject guesses after the game has ended.
- [x] Provide a client-safe state method (`pattern`, `guessed_letters`, `incorrect_letters`, `remaining_guesses`, `status`).
- [x] Include `word` in the state only after the game ends.
- [x] Write unit tests in `tests/test_game.py`.

**Done when:** a full game can be played and tested without any web server.

---

## Phase 2 — Word Management

- [x] Create a word-loading module (e.g. `word_manager.py`).
- [x] Load the Easy, Medium, and Hard lists.
- [x] Normalize to lowercase, skip blank lines, remove duplicates.
- [x] Reject non-alphabetic entries.
- [x] Select a random word by difficulty.
- [x] Raise a clear error for an invalid difficulty.
- [x] Write tests in `tests/test_word_manager.py`.

**Done when:** a random word can be requested reliably for each difficulty, and invalid difficulties are rejected.

---

## Phase 3 — Flask Server and REST API

- [x] Create `server.py` with a Flask app object named `app`.
- [x] Store active games in memory, keyed by a unique game ID.
- [x] `POST /api/games` — create a game from `{"difficulty": "easy|medium|hard"}`; return `201`.
- [x] `GET /api/games/{game_id}` — return the current state; `200`.
- [x] `POST /api/games/{game_id}/guess` — submit `{"letter": "e"}`; return updated state; `200`.
- [x] Validate difficulty and letter input (`400` on bad input).
- [x] Return `404` for unknown game IDs.
- [x] Return `400` for malformed or non-JSON request bodies.
- [x] Return JSON for every response, including errors (e.g. `{"error": "..."}`).
- [x] Confirm `word` never appears in any response while status is `playing`.
- [x] Write API tests in `tests/test_server.py` using Flask's test client.
- [x] Verify a full game can be played with `curl`.

> Note for the README (Phase 7): every game response returns the full state plus `game_id` and
> `difficulty`. This is a superset of the spec's example responses, so all three endpoints share one shape.

**Done when:** a complete game can be won or lost using only HTTP requests.

---

## Phase 4 — Browser Client

- [ ] Create `static/index.html`, `static/style.css`, `static/app.js`.
- [ ] Serve `index.html` from Flask at `/`.
- [ ] Add a difficulty selector (Easy / Medium / Hard).
- [ ] Add a New Game button.
- [ ] Display the masked pattern.
- [ ] Display guessed letters and incorrect letters.
- [ ] Display remaining incorrect guesses.
- [ ] Add an on-screen A–Z keyboard.
- [ ] Support physical keyboard input.
- [ ] Disable letters that have already been guessed.
- [ ] Use `fetch()` for every game action; update the page from the JSON response.
- [ ] Draw the hangman (SVG or HTML) and add one part per incorrect guess.
- [ ] Show a win or loss message, including the revealed word.
- [ ] Disable guessing after the game ends.
- [ ] Start a new game without reloading the page.
- [ ] Show API errors to the user instead of failing silently.
- [ ] Make the layout usable on desktop and mobile widths.
- [ ] Confirm no hidden word is stored in browser JavaScript during play.

**Done when:** a full game can be played in the browser, and all game decisions come from the server.

---

## Phase 5 — Testing and Local Verification

Automated:

- [ ] Run the full test suite and confirm everything passes.
- [ ] Test starting games at all three difficulties.
- [ ] Test correct and incorrect guesses.
- [ ] Test duplicate and invalid guesses.
- [ ] Test win and loss paths.
- [ ] Test starting a new game after one ends.
- [ ] Test invalid API requests (bad difficulty, bad letter, unknown ID, malformed JSON).
- [ ] Test that `word` is hidden during play and revealed after the game ends.

Manual (browser):

- [ ] Play several full games locally, including at least one win and one loss.
- [ ] Verify the drawing, letters, and messages update after each guess.
- [ ] In Chrome DevTools (Network tab), inspect a guess request and its JSON response.
- [ ] Be able to explain the flow: click → `fetch()` → Flask → JSON → page update.
- [ ] Fix any bugs found and re-run the tests.

**Done when:** all automated tests pass, and manual browser testing finds no open bugs.

---

## Phase 6 — Cloud Deployment

- [ ] Add `gunicorn` to `requirements.txt`.
- [ ] Make sure production does not run with `debug=True`.
- [ ] Test locally: `gunicorn --bind 127.0.0.1:5000 --workers 1 server:app`.
- [ ] Add deployment config (e.g. `render.yaml`) or record the Render dashboard settings.
- [ ] Push to GitHub.
- [ ] Create the Render web service from the GitHub repo:
  - Build: `pip install -r requirements.txt`
  - Start: `gunicorn --bind 0.0.0.0:$PORT --workers 1 server:app`
- [ ] Open the public HTTPS URL and play a complete game.
- [ ] Verify the API endpoints work on the deployed URL.
- [ ] Note free-tier limits (sleep after idle, cold starts, in-memory reset) in the README.

**Done when:** the app is playable at a public HTTPS URL, with no local server running.

---

## Phase 7 — Documentation and Submission

- [ ] Write `README.md`:
  - Project overview
  - Local install and run instructions
  - REST API summary with example requests and responses
  - How to run the tests
  - Deployed URL
  - Known limitations and deviations from the specification
- [ ] Confirm the repo contains: engine, server, frontend, word lists, original spec, updated TODO, dependency and deploy config, tests, and README.
- [ ] Confirm no credentials or secrets are committed.
- [ ] Write the 1–2 page development report (PDF):
  - Process
  - Implementation
  - Testing
  - Deployment
  - Challenges
  - Reflection
  - 2–3 representative prompts
- [ ] Record a 2–3 minute demo showing:
  - The deployed site
  - A full game played to a win or loss
  - Starting a new game
  - A DevTools request and its JSON response
- [ ] Submit the repo URL, deployed URL, report, and video on HuskyCT.

**Done when:** everything is submitted and the deployed app stays reachable for grading.

---

## Out of Scope for This Assignment

These items from the original `SPECIFICATION.md` / `TODO.md` are intentionally **not** implemented:

- Human terminal client (`terminal_client.py`)
- Automated bots (random, frequency, dictionary) and the bot runner
- Evaluation mode and evaluation API endpoints
- Official scoring system
- Leaderboard (API and browser view)
- Evaluation integrity and anti-cheating safeguards (rate limiting, idle timeouts, event logs)
- Game logging and replay endpoints and utility
- Optional future phases: persistent storage, accounts and authentication, tournaments, advanced bot analysis, multiplayer

---

## Suggested Schedule

| Day | Phases |
|---|---|
| Day 1 | Phase 0 (and review of this plan) |
| Day 2 | Phases 1–2 |
| Day 3 | Phase 3 |
| Day 4 | Phase 4 |
| Day 5 | Phase 5 |
| Day 6 | Phase 6 |
| Day 7 | Phase 7 |
