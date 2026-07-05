(function keepServerAlive() {
  // Try to connect to the server
  try {
    const proto = location.protocol === "https:" ? "wss://" : "ws://"; // if https then wss, else ws
    new WebSocket(proto + location.host + "/ws");
  } catch (_) // Ignore errors
  {} // Do nothing if loss connection
})(); // Immediately Invoked Function Expression, called by itself


function getToken() { return localStorage.getItem("mm_token") || ""; }


// All files are located at same origin, so empty
const API = "";

async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  const res = await fetch(API + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const msg = (data && data.detail) || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}


function paintMode(mode) {
  const banner = document.getElementById("modeBanner");
  if (banner) {
    banner.dataset.mode = mode;
    banner.textContent = mode === "secure" ? "Secure mode" : "Insecure mode";
  }

  const sw = document.getElementById("modeSwitch");
  if (sw) {
    sw.dataset.mode = mode;
  
    const btn = document.getElementById("modeSwitchBtn");
    if (btn) btn.setAttribute("aria-checked", String(mode === "secure"));
  
    const label = document.getElementById("modeSwitchLabel");
    if (label) label.textContent = mode === "secure" ? "Secure" : "Insecure";
  }
}


function clearSession() {
  localStorage.removeItem("mm_token");
  localStorage.removeItem("mm_user");
}


const ModeToggle = {
  current: "insecure",
  // Initialize the mode toggle on page load
  async init() {
    try {
      const { mode } = await api("/api/mode");
      this.current = mode;
      paintMode(mode);
    } catch (_) {}
    const btn = document.getElementById("modeSwitchBtn");
    if (btn) btn.addEventListener("click", () => this.flip());
  },

  // Flip the mode between secure and insecure
  async flip() {
    const sw = document.getElementById("modeSwitch");
    const target = this.current === "secure" ? "insecure" : "secure";

    paintMode(target);
    if (sw) sw.classList.add("busy");
    try {
      const { mode } = await api("/api/mode", { method: "POST", body: { mode: target } });
      this.current = mode;
      clearSession();
      setTimeout(() => { window.location.href = "/"; }, 360); // Return login page
    } catch (err) {
      paintMode(this.current); // Revert
      if (sw) sw.classList.remove("busy");
    }
  },
};


// Kept for callers that only want the banner/toggle painted
async function showMode() {
  await ModeToggle.init();
}


function setSession(t, user) {
  localStorage.setItem("mm_token", t);
  localStorage.setItem("mm_user", user);
}


const Auth = {
  mode: "login",
  init() {
    showMode();
    if (getToken()) { window.location.href = "/dashboard"; return; }

    document.getElementById("loginRegisterSwitch").addEventListener("click", () => {
      this.mode = this.mode === "login" ? "register" : "login";
      this.render();
    });
    document.getElementById("authForm").addEventListener("submit", (e) => {
      e.preventDefault();
      this.submit();
    });
    const gbtn = document.getElementById("googleBtn");
    if (gbtn) gbtn.addEventListener("click", () => this.googleSignIn());
  },

  render() {
    const login = this.mode === "login";
    const oauth = document.getElementById("oauthBlock");
    if (oauth) oauth.classList.toggle("hidden", !login);
    document.getElementById("formTitle").textContent = login ? "Sign in" : "Create account";
    document.getElementById("formSub").textContent = login ? "Welcome back. Pick up where you left off." : "One account, one ledger. No email required.";
    document.getElementById("submitBtn").textContent = login ? "Sign in" : "Create account";
    document.getElementById("switchLine").innerHTML = login ? 'New here? <button type="button" id="loginRegisterSwitch">Create an account</button>' : 'Already have an account? <button type="button" id="loginRegisterSwitch">Sign in</button>';
    document.getElementById("password").autocomplete = login ? "current-password" : "new-password";
    document.getElementById("loginRegisterSwitch").addEventListener("click", () => {
      this.mode = this.mode === "login" ? "register" : "login";
      this.render();
    });
    this.notice("");
  },

  notice(msg, kind = "error") {
    const el = document.getElementById("notice");
    el.textContent = msg;
    el.className = "notice " + kind + (msg ? "" : " hidden");
  },

  async submit() {
    const username = document.getElementById("username").value.trim();
    const password = document.getElementById("password").value;
    const path = this.mode === "login" ? "/api/login" : "/api/register";
    try {
      const data = await api(path, { method: "POST", body: { username, password } });
      setSession(data.token, data.username);
      window.location.href = "/dashboard";
    } catch (err) {
      this.notice(err.message);
    }
  },

  // Shortcut for demo purposes
  async googleSignIn() {
    const btn = document.getElementById("googleBtn");
    const text = document.getElementById("googleBtnText");
    const original = text ? text.textContent : "";
    if (btn) btn.disabled = true;
    if (text) text.textContent = "Signing in…";
    this.notice("");
    try {
      const data = await api("/api/login", {
        method: "POST",
        body: { username: "jason", password: "password"},
      });
      setSession(data.token, data.username);
      window.location.href = "/dashboard";
    } catch (err) {
      if (btn) btn.disabled = false;
      if (text) text.textContent = original;
      this.notice("Wrong username or password. Please try again.");
    }
  },
};


const fmt = (n) => {
  const x = Math.abs(n).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return x;
};


const Dashboard = {
  txType: "expense",
  init() {
    showMode();
    if (!getToken()) { window.location.href = "/"; return; }
    document.getElementById("whoami").textContent = localStorage.getItem("mm_user") || "you";
    document.getElementById("date").value = new Date().toISOString().slice(0, 10);

    document.getElementById("logoutBtn").addEventListener("click", async () => {
      try { await api("/api/logout", { method: "POST" }); } catch (_) {}
      clearSession();
      window.location.href = "/";
    });

    document.querySelectorAll(".seg button").forEach((b) => {
      b.addEventListener("click", () => {
        this.txType = b.dataset.type;
        document.querySelectorAll(".seg button").forEach((x) =>
          x.setAttribute("aria-pressed", String(x === b))
        );
      });
    });

    document.getElementById("txForm").addEventListener("submit", (e) => {
      e.preventDefault();
      this.addTx();
    });

    this.refresh();
  },

  formNotice(msg, kind = "error") {
    const el = document.getElementById("formNotice");
    el.textContent = msg;
    el.className = "notice " + kind + (msg ? "" : " hidden");
  },

  async refresh() {
    await Promise.all([this.loadSummary(), this.loadLedger()]);
  },

  async loadSummary() {
    try {
      const s = await api("/api/summary");
      const bal = document.getElementById("balance");
      const sign = s.balance < 0 ? "−" : "";
      bal.textContent = sign + fmt(s.balance);
      bal.classList.toggle("neg", s.balance < 0);
      document.getElementById("incomeTotal").textContent = "+" + fmt(s.income);
      document.getElementById("expenseTotal").textContent = "−" + fmt(s.expense);
      const d = new Date(s.month + "-01T00:00:00");
      document.getElementById("monthLabel").textContent = d.toLocaleString("en-US", { month: "long", year: "numeric" });
    } catch (err) {
      if (this.handleAuthError(err)) return;
    }
  },

  async loadLedger() {
    const ledger = document.getElementById("ledger");
    try {
      const txs = await api("/api/transactions");
      document.getElementById("txCount").textContent = txs.length + (txs.length === 1 ? " entry" : " entries");
      if (txs.length === 0) {
        ledger.innerHTML =
          '<div class="empty"><h3>No transactions yet</h3>' +
          "<p>Add your first one above to start your ledger.</p></div>";
        return;
      }
      ledger.innerHTML = txs.map((t) => this.row(t)).join("");
      ledger.querySelectorAll(".del").forEach((btn) => {
        btn.addEventListener("click", () => this.delTx(btn.dataset.id));
      });
    } catch (err) {
      if (this.handleAuthError(err)) return;
      ledger.innerHTML = '<div class="empty"><p>' + err.message + "</p></div>";
    }
  },

  row(t) {
    const d = new Date(t.date + "T00:00:00");
    const day = d.toLocaleString("en-US", { month: "short", day: "2-digit" });
    const sign = t.type === "income" ? "+" : "−";
    const note = t.note
      ? `<div class="note">${escapeHtml(t.note)}</div>`
      : "";
    return `
      <div class="tx">
        <div class="day">${day}</div>
        <div class="desc">
          <span class="cat">${escapeHtml(t.category)}</span><span class="tag">${t.type}</span>
          ${note}
        </div>
        <div class="right">
          <span class="figure ${t.type}">${sign}${fmt(t.amount)}</span>
          <button class="del" data-id="${t.id}" title="Delete" aria-label="Delete transaction">✕</button>
        </div>
      </div>`;
  },

  async addTx() {
    const amount = parseFloat(document.getElementById("amount").value);
    const category = document.getElementById("category").value.trim();
    const note = document.getElementById("note").value.trim();
    const date = document.getElementById("date").value;
    if (!(amount > 0)) { this.formNotice("Enter an amount greater than zero."); return; }
    try {
      await api("/api/transactions", {
        method: "POST",
        body: { amount, type: this.txType, category, note, date },
      });
      document.getElementById("amount").value = "";
      document.getElementById("note").value = "";
      this.formNotice("");
      this.refresh();
    } catch (err) {
      if (this.handleAuthError(err)) return;
      this.formNotice(err.message);
    }
  },

  async delTx(id) {
    try {
      await api("/api/transactions/" + id, { method: "DELETE" });
      this.refresh();
    } catch (err) {
      if (this.handleAuthError(err)) return;
      this.formNotice(err.message);
    }
  },
  
  handleAuthError(err) {
    if (/401|not authenticated/i.test(err.message)) {
      clearSession();
      window.location.href = "/";
      return true;
    }
    return false;
  },
};

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

window.Auth = Auth;
window.Dashboard = Dashboard;
