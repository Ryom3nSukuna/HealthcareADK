const API_URL = "http://localhost:8000/chat";
const SESSION_KEY = "healthcareadk_session_id";
const API_KEY_STORAGE = "healthcareadk_api_key";

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("chat-input");

let sessionId = localStorage.getItem(SESSION_KEY) || null;

function getApiKey() {
  let key = localStorage.getItem(API_KEY_STORAGE);
  if (!key) {
    key = window.prompt("Enter your HealthcareADK API key (set via HEALTHCAREADK_API_KEY in .env):");
    if (key) localStorage.setItem(API_KEY_STORAGE, key.trim());
  }
  return key ? key.trim() : "";
}

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

function renderMarkdown(text) {
  // marked.js does not sanitize its output, and chat responses are rendered via
  // innerHTML — sanitize with DOMPurify first so a response can't inject a script tag.
  return DOMPurify.sanitize(marked.parse(text));
}

function appendMessage(role, html) {
  const el = document.createElement("div");
  el.className = `message ${role}`;
  el.innerHTML = html;
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return el;
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = inputEl.value.trim();
  if (!message) return;

  appendMessage("user", escapeHtml(message));
  inputEl.value = "";
  inputEl.disabled = true;
  const pending = appendMessage("assistant", "<em>Thinking...</em>");

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": getApiKey() },
      body: JSON.stringify({ message, session_id: sessionId }),
    });
    if (!res.ok) {
      throw new Error(`Request failed: ${res.status}`);
    }
    const data = await res.json();
    sessionId = data.session_id;
    localStorage.setItem(SESSION_KEY, sessionId);

    const agentTag = data.agents && data.agents.length
      ? `<div class="agent-tag">${escapeHtml(data.agents.join(", "))}</div>`
      : "";
    pending.innerHTML = agentTag + renderMarkdown(data.response);
  } catch (err) {
    pending.innerHTML = `<span class="error">Error: ${escapeHtml(err.message)}</span>`;
  } finally {
    inputEl.disabled = false;
    inputEl.focus();
  }
});
