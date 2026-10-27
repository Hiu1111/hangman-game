// Hangman browser client.
//
// This file has no game rules. Every action is a fetch() call to the Flask
// REST API, and the page is redrawn from the JSON the server sends back.
// The hidden word is never known here while a game is in progress: the
// server only includes `word` once the status is "won" or "lost".

"use strict";

const API = "/api/games";
const LETTERS = "abcdefghijklmnopqrstuvwxyz".split("");

const els = {
  sheet: document.querySelector(".sheet"),
  form: document.getElementById("new-game-form"),
  newGame: document.getElementById("new-game"),
  meta: document.getElementById("meta"),
  word: document.getElementById("word"),
  lives: document.getElementById("lives"),
  livesCount: document.getElementById("lives-count"),
  livesLabel: document.getElementById("lives-label"),
  guessed: document.getElementById("guessed"),
  missed: document.getElementById("missed"),
  message: document.getElementById("message"),
  keyboard: document.getElementById("keyboard"),
  parts: Array.from(document.querySelectorAll(".part")),
};

let game = null;   // latest game state from the server
let busy = false;  // true while a new game is being created

// Guesses are sent one at a time, in the order they were made. Letters
// typed while a request is in flight wait here instead of being dropped.
const pending = [];
let sending = false;

// ----- API -----------------------------------------------------------------

async function request(url, options = {}) {
  let response;
  try {
    response = await fetch(url, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch {
    throw new Error("Can't reach the server. Check your connection and try again.");
  }

  let body = null;
  try {
    body = await response.json();
  } catch {
    // fall through with body = null
  }

  if (!response.ok) {
    const reason = body && body.error ? body.error : `Request failed (HTTP ${response.status}).`;
    const error = new Error(reason);
    error.status = response.status;
    throw error;
  }
  return body;
}

function createGame(difficulty) {
  return request(API, { method: "POST", body: JSON.stringify({ difficulty }) });
}

function sendGuess(gameId, letter) {
  return request(`${API}/${encodeURIComponent(gameId)}/guess`, {
    method: "POST",
    body: JSON.stringify({ letter }),
  });
}

// ----- actions -------------------------------------------------------------

function selectedDifficulty() {
  const checked = els.form.querySelector("input[name=difficulty]:checked");
  return checked ? checked.value : "easy";
}

async function startGame() {
  if (busy) return;
  setBusy(true);
  pending.length = 0;  // drop guesses meant for the old game
  showMessage("");
  try {
    game = await createGame(selectedDifficulty());
    render();
  } catch (error) {
    showMessage(error.message, "error");
  } finally {
    setBusy(false);
  }
}

function guess(letter) {
  if (busy || !game || game.status !== "playing") return;
  if (game.guessed_letters.includes(letter) || pending.includes(letter)) return;

  pending.push(letter);
  markPending(letter);
  processQueue();
}

async function processQueue() {
  if (sending) return;
  sending = true;

  while (pending.length) {
    const letter = pending[0];
    // The game may have ended while this letter was waiting.
    if (!game || game.status !== "playing" || game.guessed_letters.includes(letter)) {
      pending.shift();
      continue;
    }
    const gameId = game.game_id;
    try {
      const updated = await sendGuess(gameId, letter);
      // Ignore the reply if a new game was started while it was in flight.
      if (!game || game.game_id !== gameId) continue;
      game = updated;
      pending.shift();
      showMessage("");
    } catch (error) {
      if (!game || game.game_id !== gameId) continue;
      pending.length = 0;
      if (error.status === 404) {
        // The server restarted or the game expired.
        game = null;
        showMessage("This game is no longer on the server. Start a new game to keep playing.", "error");
      } else {
        showMessage(error.message, "error");
      }
    }
    render();
  }

  sending = false;
}

function markPending(letter) {
  const key = els.keyboard.querySelector(`.key[data-letter="${letter}"]`);
  if (key) key.disabled = true;
}

// ----- rendering -----------------------------------------------------------

function setBusy(value) {
  busy = value;
  els.newGame.disabled = value;
  els.sheet.setAttribute("aria-busy", String(value));
}

function showMessage(text, kind = "") {
  els.message.textContent = text;
  els.message.className = `message ${kind}`.trim();
}

function renderWord() {
  els.word.replaceChildren();
  if (!game) return;

  const slots = game.pattern.split(" ");
  const answer = game.status === "lost" ? game.word : null;
  els.word.style.setProperty("--len", slots.length);

  slots.forEach((slot, i) => {
    const tile = document.createElement("span");
    tile.className = "tile";
    if (slot !== "_") {
      tile.textContent = slot;
    } else if (answer) {
      tile.textContent = answer[i];
      tile.classList.add("revealed");
    }
    els.word.appendChild(tile);
  });

  const spoken = slots.map((s) => (s === "_" ? "blank" : s)).join(" ");
  els.word.setAttribute("aria-label", `Word: ${spoken}`);
}

function renderLetters() {
  const guessed = game ? game.guessed_letters : [];
  const missed = game ? game.incorrect_letters : [];
  setLetterList(els.guessed, guessed);
  setLetterList(els.missed, missed);
}

function setLetterList(el, letters) {
  el.textContent = letters.length ? letters.join(" ").toUpperCase() : "None yet";
  el.classList.toggle("empty", letters.length === 0);
}

function renderLives() {
  const left = game ? game.remaining_guesses : 6;
  els.livesCount.textContent = left;
  els.livesLabel.textContent = left === 1 ? "wrong guess left" : "wrong guesses left";
  els.lives.classList.toggle("low", left <= 2);
}

function renderDrawing() {
  const misses = game ? game.incorrect_letters.length : 0;
  els.parts.forEach((part) => {
    part.classList.toggle("shown", Number(part.dataset.part) <= misses);
  });
}

function renderKeyboard() {
  const guessed = game ? new Set(game.guessed_letters) : new Set();
  const missed = game ? new Set(game.incorrect_letters) : new Set();
  const over = !game || game.status !== "playing";

  for (const key of els.keyboard.children) {
    const letter = key.dataset.letter;
    const isHit = guessed.has(letter) && !missed.has(letter);
    const isMiss = missed.has(letter);
    key.classList.toggle("hit", isHit);
    key.classList.toggle("miss", isMiss);
    key.disabled = over || guessed.has(letter) || pending.includes(letter);
    const state = isHit ? ", in the word" : isMiss ? ", not in the word" : "";
    key.setAttribute("aria-label", `${letter.toUpperCase()}${state}`);
  }
}

function renderStatus() {
  els.sheet.classList.toggle("won", !!game && game.status === "won");
  els.sheet.classList.toggle("lost", !!game && game.status === "lost");

  if (!game) {
    els.meta.textContent = "No game in progress.";
    return;
  }

  const level = game.difficulty.charAt(0).toUpperCase() + game.difficulty.slice(1);
  const length = game.pattern.split(" ").length;
  els.meta.textContent = `${level} word, ${length} letters`;

  if (game.status === "won") {
    showMessage(`Solved! The word was “${game.word}”. Press Enter or New game to play again.`, "win");
  } else if (game.status === "lost") {
    showMessage(`Out of guesses. The word was “${game.word}”. Press Enter or New game to try another.`, "loss");
  }
}

function render() {
  renderWord();
  renderLetters();
  renderLives();
  renderDrawing();
  renderKeyboard();
  renderStatus();
}

// ----- setup ---------------------------------------------------------------

function buildKeyboard() {
  for (const letter of LETTERS) {
    const key = document.createElement("button");
    key.type = "button";
    key.className = "key";
    key.textContent = letter;
    key.dataset.letter = letter;
    key.disabled = true;
    els.keyboard.appendChild(key);
  }
}

els.keyboard.addEventListener("click", (event) => {
  const key = event.target.closest(".key");
  if (key && !key.disabled) guess(key.dataset.letter);
});

els.form.addEventListener("submit", (event) => {
  event.preventDefault();
  startGame();
});

document.addEventListener("keydown", (event) => {
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  const key = event.key.toLowerCase();

  if (key.length === 1 && key >= "a" && key <= "z") {
    event.preventDefault();
    guess(key);
  } else if (event.key === "Enter" && game && game.status !== "playing") {
    // Let Enter on a focused button do its own thing.
    if (event.target instanceof HTMLButtonElement) return;
    event.preventDefault();
    startGame();
  }
});

buildKeyboard();
render();
startGame();
