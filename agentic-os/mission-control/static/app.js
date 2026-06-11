const PAGES = {
  '/': { title: 'Overview', sub: 'Agentic OS at a glance' },
  '/command': { title: 'Command', sub: 'Talk to Hermes — assign tasks, request work, delegate to Pantheon' },
  '/projects': { title: 'Projects', sub: 'Registered repositories — import and assign work by project' },
  '/hermes': { title: 'Hermes Agent', sub: 'Orchestrator status, gateway, MCP, profiles' },
  '/pantheon': { title: 'Pantheon', sub: 'Delegated personas — create, view, and assign to Hermes' },
  '/bridge': { title: 'Claude OS Bridge', sub: 'Shared memory across Cursor, Claude Code, and Hermes' },
  '/memory': { title: 'Memory', sub: 'SOUL, user profile, agent memories, Obsidian' },
  '/growth': { title: 'Growth Engine', sub: 'hotproductsdot SEO pipeline status' },
  '/cron': { title: 'Cron Jobs', sub: 'Scheduled automations' },
  '/skills': { title: 'Skills', sub: 'Hermes procedural memory' },
};

const Pantheon = {
  async create(ev) {
    ev.preventDefault();
    const name = document.getElementById('persona-name')?.value?.trim();
    const system_prompt = document.getElementById('persona-prompt')?.value?.trim();
    const tone = document.getElementById('persona-tone')?.value?.trim();
    const style = document.getElementById('persona-style')?.value?.trim();
    const status = document.getElementById('persona-status');
    const btn = document.getElementById('persona-create-btn');
    if (!name || !system_prompt) return;
    if (status) status.textContent = 'Creating persona…';
    if (btn) btn.disabled = true;
    try {
      const r = await fetch('/api/pantheon', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, system_prompt, tone, style }),
      });
      const data = await r.json();
      if (data.ok) {
        if (status) {
          status.textContent = data.warning
            ? `Created ${data.persona.name} (sync warning: ${data.warning})`
            : `Created ${data.persona.name} and synced to Hermes`;
        }
        document.getElementById('persona-form')?.reset();
        App.refresh();
      } else if (status) {
        status.textContent = data.error || 'Create failed';
      }
    } catch (e) {
      if (status) status.textContent = e.message;
    }
    if (btn) btn.disabled = false;
  },
};

const Projects = {
  async importRepo(ev) {
    ev.preventDefault();
    const url = document.getElementById('import-url')?.value?.trim();
    const branch = document.getElementById('import-branch')?.value?.trim();
    const name = document.getElementById('import-name')?.value?.trim();
    const status = document.getElementById('import-status');
    const btn = document.getElementById('import-btn');
    if (!url) return;
    if (status) status.textContent = 'Cloning repository…';
    if (btn) btn.disabled = true;
    try {
      const r = await fetch('/api/projects/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, branch: branch || null, name: name || null }),
      });
      const data = await r.json();
      if (data.ok) {
        if (status) status.textContent = `Imported ${data.project.name}`;
        document.getElementById('import-form')?.reset();
        App.refresh();
      } else {
        if (status) status.textContent = data.error || 'Import failed';
      }
    } catch (e) {
      if (status) status.textContent = e.message;
    }
    if (btn) btn.disabled = false;
  },

  async registerLocal(ev) {
    ev.preventDefault();
    const local_path = document.getElementById('local-path')?.value?.trim();
    const name = document.getElementById('local-name')?.value?.trim();
    const status = document.getElementById('import-status');
    if (!local_path) return;
    if (status) status.textContent = 'Registering path…';
    try {
      const r = await fetch('/api/projects/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ local_path, name: name || null }),
      });
      const data = await r.json();
      if (status) status.textContent = data.ok ? `Registered ${data.project.name}` : (data.error || 'Failed');
      if (data.ok) { document.getElementById('local-form')?.reset(); App.refresh(); }
    } catch (e) {
      if (status) status.textContent = e.message;
    }
  },

  async pull(id) {
    const r = await fetch(`/api/projects/${id}/pull`, { method: 'POST' });
    const data = await r.json();
    alert(data.ok ? (data.output || 'Pulled') : (data.error || 'Pull failed'));
    if (data.ok) App.refresh();
  },

  async remove(id, primary) {
    if (primary) return alert('Cannot remove primary project');
    if (!confirm('Remove this project from the registry?')) return;
    const delete_files = confirm('Also delete cloned files from agentic-os/projects/? (only for imported repos)');
    await fetch(`/api/projects/${id}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ delete_files }),
    });
    App.refresh();
  },

  askHermes(id) {
    const p = (App.state?.projects || []).find(x => x.id === id);
    if (!p) return;
    const msg = `Work on project "${p.name}" at ${p.path}. What should we tackle first?`;
    document.getElementById('command-input').value = msg;
    document.getElementById('command-panel')?.classList.remove('collapsed');
    App.navigate('/command');
    document.getElementById('command-page-input')?.focus();
  },
};

const Command = {
  messages: [],
  sessionId: null,
  busy: false,
  collapsed: localStorage.getItem('mc_cmd_collapsed') === '1',

  init() {
    const panel = document.getElementById('command-panel');
    const toggle = document.getElementById('command-toggle');
    const form = document.getElementById('command-form');
    const input = document.getElementById('command-input');
    const persona = document.getElementById('command-persona');
    const newBtn = document.getElementById('command-new');

    if (this.collapsed) panel.classList.add('collapsed');
    else panel.classList.remove('collapsed');

    toggle?.addEventListener('click', () => {
      panel.classList.toggle('collapsed');
      localStorage.setItem('mc_cmd_collapsed', panel.classList.contains('collapsed') ? '1' : '0');
    });

    form?.addEventListener('submit', e => {
      e.preventDefault();
      this.send(input.value, persona.value);
      input.value = '';
    });

    input?.addEventListener('keydown', e => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        form.requestSubmit();
      }
    });

    newBtn?.addEventListener('click', () => this.newSession());

    document.querySelectorAll('.command-quick button').forEach(btn => {
      btn.addEventListener('click', () => {
        panel.classList.remove('collapsed');
        localStorage.setItem('mc_cmd_collapsed', '0');
        this.send(btn.dataset.cmd, persona.value);
      });
    });

    this.loadHistory();
  },

  async loadHistory() {
    try {
      const r = await fetch('/api/chat');
      const data = await r.json();
      this.messages = data.messages || [];
      this.sessionId = data.session_id || null;
      this.renderMessages(document.getElementById('command-messages'));
      this.updateSessionLabel();
    } catch (_) { /* ignore */ }
  },

  updateSessionLabel() {
    const el = document.getElementById('command-session');
    if (el) {
      el.textContent = this.sessionId
        ? `session ${this.sessionId.slice(-8)}`
        : 'new session';
    }
  },

  async newSession() {
    if (this.busy) return;
    await fetch('/api/chat', { method: 'DELETE' });
    this.messages = [];
    this.sessionId = null;
    this.renderMessages(document.getElementById('command-messages'));
    this.renderMessages(document.getElementById('command-messages-page'));
    this.updateSessionLabel();
  },

  async send(message, personality) {
    message = (message || '').trim();
    if (!message || this.busy) return;

    this.busy = true;
    const sendBtn = document.getElementById('command-send');
    const pageSendBtn = document.getElementById('command-page-send');
    if (sendBtn) sendBtn.disabled = true;
    if (pageSendBtn) pageSendBtn.disabled = true;

    this.messages.push({ role: 'user', content: message, personality, ts: new Date().toISOString() });
    this.renderMessages(document.getElementById('command-messages'));
    this.renderMessages(document.getElementById('command-messages-page'));
    this.showThinking(true);

    try {
      const r = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message,
          personality: personality || null,
          session_id: this.sessionId,
        }),
      });
      const data = await r.json();
      if (data.session_id) this.sessionId = data.session_id;
      if (data.history) {
        this.messages = data.history;
      } else {
        this.messages.push({
          role: 'assistant',
          content: data.response || data.error || 'No response',
          ok: data.ok,
          duration_s: data.duration_s,
          ts: new Date().toISOString(),
        });
      }
    } catch (e) {
      this.messages.push({ role: 'assistant', content: `Error: ${e.message}`, ok: false, ts: new Date().toISOString() });
    }

    this.showThinking(false);
    this.busy = false;
    if (sendBtn) sendBtn.disabled = false;
    if (pageSendBtn) pageSendBtn.disabled = false;
    this.renderMessages(document.getElementById('command-messages'));
    this.renderMessages(document.getElementById('command-messages-page'));
    this.updateSessionLabel();
  },

  showThinking(on) {
    ['command-messages', 'command-messages-page'].forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      const existing = el.querySelector('.msg-thinking');
      if (on && !existing) {
        const d = document.createElement('div');
        d.className = 'msg-thinking';
        d.textContent = 'Hermes is working…';
        el.appendChild(d);
        el.scrollTop = el.scrollHeight;
      } else if (!on && existing) {
        existing.remove();
      }
    });
  },

  renderMessages(container) {
    if (!container) return;
    container.innerHTML = this.messages.map(m => {
      const cls = m.role === 'user' ? 'user' : `assistant${m.ok === false ? ' error' : ''}`;
      const meta = m.role === 'assistant' && m.duration_s
        ? `<div class="msg-meta">${m.duration_s}s</div>`
        : m.personality
          ? `<div class="msg-meta">${esc(m.personality)}</div>`
          : '';
      return `<div class="msg ${cls}">${esc(m.content)}${meta}</div>`;
    }).join('') || '<p class="muted" style="padding:8px">No messages yet. Ask Hermes to run a task.</p>';
    container.scrollTop = container.scrollHeight;
  },

  renderPage() {
    const names = App.state?.pantheon_names || ['mercury', 'labyrinth', 'philosopher', 'oracle'];
    const personaOpts = [''].concat(names)
      .map(p => `<option value="${esc(p)}">${p ? esc(p.charAt(0).toUpperCase() + p.slice(1)) : 'Default'}</option>`).join('');
    return `
      <div class="command-page">
        <div class="banner" style="background:#1e1b4b;border-color:#4338ca;margin-bottom:16px">
          Commands run via <code>hermes chat</code> with Pantheon, bridge, and growth-engine skills.
          Long tasks may take several minutes.
        </div>
        <div class="grid">
          ${card('Session', `
            <p class="muted">ID: <code>${esc(this.sessionId || 'none')}</code></p>
            <p class="muted mt">${this.messages.length} messages</p>
            <button class="mt" onclick="Command.newSession()" style="padding:8px 14px;border-radius:8px;border:1px solid var(--border);background:var(--card);color:var(--text);cursor:pointer">New session</button>
          `)}
          ${card('Quick tasks', `
            <button onclick="Command.send('Give me a morning brief with growth-engine status.', 'mercury')" style="display:block;width:100%;margin-bottom:6px;padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);cursor:pointer;text-align:left">☿ Mercury — Morning brief</button>
            <button onclick="Command.send('Run growth-engine status check and report deals, content plan, publish log.', 'mercury')" style="display:block;width:100%;margin-bottom:6px;padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);cursor:pointer;text-align:left">📈 Growth engine status</button>
            <button onclick="Command.send('Research top SEO opportunities for hotproductsdot kitchen category.', 'labyrinth')" style="display:block;width:100%;margin-bottom:6px;padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);cursor:pointer;text-align:left">🌀 Labyrinth — SEO research</button>
            <button onclick="Command.send('What should I prioritize this week for hotproductsdot growth?', 'philosopher')" style="display:block;width:100%;padding:8px;border-radius:6px;border:1px solid var(--border);background:var(--card);color:var(--text);cursor:pointer;text-align:left">🏛 Philosopher — Strategy</button>
          `)}
        </div>
        <div class="command-messages-page" id="command-messages-page"></div>
        <form class="command-form-page" onsubmit="event.preventDefault(); Command.send(document.getElementById('command-page-input').value, document.getElementById('command-page-persona').value); document.getElementById('command-page-input').value='';">
          <select id="command-page-persona">${personaOpts}</select>
          <textarea id="command-page-input" placeholder="Assign a task to Hermes…"></textarea>
          <button type="submit" id="command-page-send" style="padding:12px 20px;border-radius:8px;border:none;background:var(--accent);color:#fff;font-weight:600;cursor:pointer">Send</button>
        </form>
      </div>`;
  },
};

const App = {
  state: null,
  route: '/',

  init() {
    Command.init();
    document.querySelectorAll('.nav a[data-route]').forEach(a => {
      a.addEventListener('click', e => {
        e.preventDefault();
        this.navigate(a.dataset.route);
      });
    });
    document.querySelectorAll('#nav-external a[data-kind="desktop"]').forEach(a => {
      a.addEventListener('click', e => this.launchDesktop(e, a));
    });
    window.addEventListener('popstate', () => this.navigate(location.pathname, false));
    this.navigate(location.pathname || '/', false);
    setInterval(() => this.refresh(), 60000);
  },

  navigate(path, push = true) {
    path = path.replace(/\/+$/, '') || '/';
    if (!PAGES[path]) path = '/';
    this.route = path;
    if (push) history.pushState({}, '', path);
    document.querySelectorAll('.nav a[data-route]').forEach(a => {
      a.classList.toggle('active', a.dataset.route === path);
    });
    const meta = PAGES[path];
    document.getElementById('page-title').textContent = meta.title;
    document.getElementById('page-sub').textContent = meta.sub;
    document.title = `${meta.title} — Mission Control`;
    const panel = document.getElementById('command-panel');
    if (path === '/command') {
      panel.classList.add('expanded');
      panel.classList.remove('collapsed');
    } else {
      panel.classList.remove('expanded');
    }
    this.render();
  },

  async refresh() {
    const app = document.getElementById('app');
    if (!this.state) app.innerHTML = '<p class="loading">Loading...</p>';
    try {
      const r = await fetch('/api/state');
      this.state = await r.json();
      this.updateExternalLinks();
      this.updatePersonaSelects();
      this.render();
    } catch (e) {
      app.innerHTML = `<p class="loading">Error: ${esc(e.message)}</p>`;
    }
  },

  updatePersonaSelects() {
    const names = this.state?.pantheon_names || [];
    const opts = ['<option value="">Default</option>']
      .concat(names.map(n => {
        const label = n.charAt(0).toUpperCase() + n.slice(1);
        return `<option value="${esc(n)}">${esc(label)}</option>`;
      }))
      .join('');
    ['command-persona'].forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      const cur = el.value;
      el.innerHTML = opts;
      if (cur && names.includes(cur)) el.value = cur;
    });
  },

  updateExternalLinks() {
    const svcs = this.state?.external_services || {};
    document.querySelectorAll('#nav-external a[data-svc]').forEach(a => {
      const svc = svcs[a.dataset.svc];
      const dot = a.querySelector('.svc-dot');
      if (dot && svc) {
        dot.className = 'svc-dot ' + (svc.up ? 'up' : 'down');
        if (svc.type === 'desktop') {
          dot.title = svc.up ? 'Running' : 'Not running — click to launch';
        } else {
          dot.title = svc.up ? 'Running' : 'Not running — run start-external-services.ps1';
        }
      }
    });
  },

  async launchDesktop(e, link) {
    e.preventDefault();
    link.classList.add('launching');
    try {
      const r = await fetch('/api/external/hermes-desktop/launch', { method: 'POST' });
      const data = await r.json();
      if (!data.ok) alert(data.error || 'Launch failed');
      setTimeout(() => this.refresh(), 2500);
    } catch (err) {
      alert(err.message);
    } finally {
      link.classList.remove('launching');
    }
  },

  render() {
    if (!this.state) { this.refresh(); return; }
    const s = this.state;
    const renderers = {
      '/': () => this.renderOverview(s),
      '/command': () => Command.renderPage(),
      '/projects': () => this.renderProjects(s),
      '/hermes': () => this.renderHermes(s),
      '/pantheon': () => this.renderPantheon(s),
      '/bridge': () => this.renderBridge(s),
      '/memory': () => this.renderMemory(s),
      '/growth': () => this.renderGrowth(s),
      '/cron': () => this.renderCron(s),
      '/skills': () => this.renderSkills(s),
    };
    document.getElementById('app').innerHTML = (renderers[this.route] || renderers['/'])();
    if (this.route === '/command') {
      const src = document.getElementById('command-persona');
      const dst = document.getElementById('command-page-persona');
      if (src && dst) dst.value = src.value;
      Command.renderMessages(document.getElementById('command-messages-page'));
    }
  },

  renderOverview(s) {
    const h = s.hermes || {};
    const bridge = s.bridge || {};
    const sessions = bridge.cursor_sessions || [];
    const chat = s.chat || {};
    return `
      <div class="grid">
        ${card('Hermes Command', `
          <div class="value">${chat.message_count || 0} messages</div>
          <p class="muted mt">Talk to Hermes from the command bar below or open the full Command page.</p>
          <a class="link-btn mt" href="/command">Open Command →</a>
        `)}
        ${card('Projects', `
          <div class="value">${(s.projects || []).length} repos</div>
          <p class="muted mt">Import GitHub repos or register local paths for Hermes.</p>
          <a class="link-btn mt" href="/projects">Manage projects →</a>
        `)}
        ${card('Hermes Agent', `
          <div class="value">${esc(h.version || '?')}</div>
          <p class="mt">Gateway: ${badge(h.gateway_running)}</p>
          <p class="muted mt">Model: ${esc(s.model || '?')}</p>
          <a class="link-btn mt" href="/hermes">View details →</a>
        `)}
        ${card('Claude OS Bridge', `
          <div class="value">${sessions.length} sessions</div>
          <p class="muted mt">Updated: ${esc(bridge.generated_at || 'never')}</p>
          <a class="link-btn mt" href="/bridge">Open bridge →</a>
        `)}
        ${card('Pantheon', `
          <div class="value">${Object.keys(s.pantheon || {}).length} personas</div>
          <p class="muted mt">Mercury · Labyrinth · Philosopher · Oracle</p>
          <a class="link-btn mt" href="/pantheon">Manage pantheon →</a>
        `)}
        ${card('Suggestions', (bridge.suggestions || []).map(x =>
          `<div class="suggestion">${esc(x)}</div>`
        ).join('') || '<p class="muted">No suggestions yet</p>')}
      </div>`;
  },

  renderProjects(s) {
    const projects = s.projects || [];
    const dir = s.projects_dir || 'agentic-os/projects';
    const rows = projects.map(p => {
      const g = p.git || {};
      const src = p.source === 'import' ? 'imported' : p.source === 'local' ? 'local' : p.source;
      return `
        <tr>
          <td><strong>${esc(p.name)}</strong>${p.primary ? ' <span class="badge on">primary</span>' : ''}</td>
          <td><code class="path-cell">${esc(p.path)}</code></td>
          <td>${esc(g.branch || p.branch || '—')}</td>
          <td class="muted">${esc(g.last_commit || '—')}</td>
          <td>${g.dirty ? '<span class="badge off">dirty</span>' : '<span class="badge on">clean</span>'}</td>
          <td><span class="tag">${esc(src)}</span></td>
          <td class="project-actions">
            <button onclick="Projects.askHermes('${esc(p.id)}')">Hermes</button>
            ${(p.path && p.exists !== false) ? `<button onclick="Projects.pull('${esc(p.id)}')">Pull</button>` : ''}
            ${!p.primary ? `<button class="danger" onclick="Projects.remove('${esc(p.id)}', false)">Remove</button>` : ''}
          </td>
        </tr>`;
    }).join('');

    return `
      <div class="grid">
        ${card('Import repository', `
          <form id="import-form" class="import-form" onsubmit="Projects.importRepo(event)">
            <label>Git URL</label>
            <input type="url" id="import-url" placeholder="https://github.com/user/repo.git" required>
            <label>Branch <span class="muted">(optional)</span></label>
            <input type="text" id="import-branch" placeholder="main">
            <label>Name <span class="muted">(optional)</span></label>
            <input type="text" id="import-name" placeholder="my-project">
            <button type="submit" id="import-btn">Clone &amp; import</button>
          </form>
          <p class="muted mt">Clones into <code>${esc(dir)}</code></p>
          <details class="mt">
            <summary class="muted" style="cursor:pointer">Register existing local path</summary>
            <form id="local-form" class="import-form mt" onsubmit="Projects.registerLocal(event)">
              <label>Path (WSL)</label>
              <input type="text" id="local-path" placeholder="/mnt/e/GITHUB/my-repo">
              <label>Name <span class="muted">(optional)</span></label>
              <input type="text" id="local-name" placeholder="my-repo">
              <button type="submit">Register</button>
            </form>
          </details>
          <p id="import-status" class="import-status muted mt"></p>
        `, 'full')}
      </div>
      ${card('Projects (' + projects.length + ')', projects.length ? `
        <div class="table-wrap">
          <table class="project-table">
            <thead>
              <tr>
                <th>Name</th><th>Path</th><th>Branch</th><th>Last commit</th><th>Status</th><th>Source</th><th></th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>
        </div>
      ` : '<p class="muted">No projects yet. Import a repository above.</p>', 'full')}
    `;
  },

  renderHermes(s) {
    const h = s.hermes || {};
    return `
      <div class="grid">
        ${card('Status', `
          <div class="value">${esc(h.version || '?')}</div>
          <p class="mt">Gateway: ${badge(h.gateway_running)}</p>
          <p class="muted mt">Model: ${esc(s.model || '?')}</p>
          <p class="muted">Home: <code>${esc(h.home || '')}</code></p>
          ${!h.gateway_running ? `<p class="warn mt">Start gateway: <code>hermes gateway start</code></p>` : ''}
        `)}
        ${card('Profiles', `<pre>${esc(h.profiles || 'None')}</pre>`)}
      </div>
      ${card('Gateway', `<pre>${esc(h.gateway_raw || 'No data')}</pre>`, 'full')}
      ${card('MCP Servers', `<pre>${esc(h.mcp_servers || 'None configured')}</pre>`, 'full')}
    `;
  },

  renderPantheon(s) {
    const full = s.pantheon_full || s.pantheon || {};
    const entries = Object.entries(full);
    const cards = entries.map(([name, p]) => {
      const prompt = typeof p === 'object' ? (p.system_prompt || '') : String(p);
      const tone = typeof p === 'object' ? (p.tone || '') : '';
      const style = typeof p === 'object' ? (p.style || '') : '';
      return card(name, `
        ${tone ? `<p class="tag">${esc(tone)}</p>` : ''}
        ${style ? `<p class="tag">${esc(style)}</p>` : ''}
        <pre class="prompt">${esc(prompt)}</pre>
        <p class="muted mt">Invoke: <code>use ${esc(name)} to ...</code> or select in Command panel</p>
        <button onclick="document.getElementById('command-persona').value='${esc(name)}'; App.navigate('/command'); document.getElementById('command-page-input')?.focus();" style="margin-top:8px;padding:6px 12px;border-radius:6px;border:1px solid var(--accent);background:transparent;color:var(--accent);cursor:pointer">Assign to ${esc(name)}</button>
      `, 'full');
    }).join('');

    return `
      ${card('Create persona', `
        <form id="persona-form" class="import-form" onsubmit="Pantheon.create(event)">
          <label>Name</label>
          <input type="text" id="persona-name" placeholder="scout" required pattern="[a-zA-Z][a-zA-Z0-9_\\-]*" title="Lowercase slug, e.g. scout or code_reviewer">
          <label>System prompt</label>
          <textarea id="persona-prompt" rows="6" placeholder="You are Scout — the Pantheon's code review agent. Role: ..." required></textarea>
          <label>Tone <span class="muted">(optional)</span></label>
          <input type="text" id="persona-tone" placeholder="precise, constructive">
          <label>Style <span class="muted">(optional)</span></label>
          <input type="text" id="persona-style" placeholder="bullet findings with severity">
          <button type="submit" id="persona-create-btn">Create &amp; sync to Hermes</button>
        </form>
        <p class="muted mt">Saved to <code>agentic-os/config/personalities.yaml</code> and merged into <code>~/.hermes/config.yaml</code></p>
        <p id="persona-status" class="import-status muted mt"></p>
      `, 'full')}
      ${entries.length ? cards : '<p class="muted">No personas yet — create one above.</p>'}
    `;
  },

  renderBridge(s) {
    const bridge = s.bridge || {};
    const sessions = bridge.cursor_sessions || [];
    const claude = bridge.claude_projects || [];
    return `
      <div class="actions-bar">
        <button onclick="App.refresh()">↻ Refresh digest</button>
        <button onclick="Command.send('Run collect_context.py and summarize bridge findings.', 'oracle')">Ask Oracle</button>
      </div>
      <div class="grid">
        ${card('Digest', `
          <p class="muted">Generated: ${esc(bridge.generated_at || 'never')}</p>
          <p class="mt"><strong>Suggestions</strong></p>
          ${(bridge.suggestions || []).map(x => `<div class="suggestion">${esc(x)}</div>`).join('') || '<p class="muted">None</p>'}
        `)}
        ${card('Paths', `
          <p class="muted">Repo: <code>${esc((bridge.paths || {}).repo || s.repo || '')}</code></p>
          <p class="muted mt">Obsidian: <code>${esc((bridge.paths || {}).obsidian_vault || s.obsidian_vault || '')}</code></p>
        `)}
      </div>
      ${card('Cursor Sessions (' + sessions.length + ')', sessions.length ? sessions.map(sess => `
        <div class="session">
          <strong>${esc(sess.project || 'unknown')}</strong>
          <span class="muted"> · ${esc(sess.modified || '')}</span>
          ${(sess.recent_queries || []).map(q => `<div class="query">"${esc(q)}"</div>`).join('')}
        </div>
      `).join('') : '<p class="muted">No Cursor sessions found</p>', 'full')}
      ${card('Claude Code Projects (' + claude.length + ')', claude.length ? claude.map(p => `
        <div class="session">
          <strong>${esc(p.path || '')}</strong>
          <span class="muted"> · ${esc(p.modified || '')}</span>
        </div>
      `).join('') : '<p class="muted">No Claude projects found</p>', 'full')}
    `;
  },

  renderMemory(s) {
    const m = s.memory || {};
    return `
      <div class="grid">
        ${card('Obsidian Vault', `
          <code>${esc(m.obsidian_vault || s.obsidian_vault || '')}</code>
        `)}
        ${card('Memory Files', (m.memory_files || []).map(f =>
          `<p><strong>${esc(f.name)}</strong></p>`
        ).join('') || '<p class="muted">No memory files</p>')}
      </div>
      ${card('SOUL.md', `<pre>${esc(m.soul || '(empty)')}</pre>`, 'full')}
      ${card('USER Profile', `<pre>${esc(m.user_profile || '(empty)')}</pre>`, 'full')}
    `;
  },

  renderGrowth(s) {
    const g = s.growth || {};
    const keys = ['published', 'content_plan', 'deals'];
    return `
      <div class="actions-bar">
        <button onclick="Command.send('Check growth-engine status and report.', 'mercury')">Ask Mercury</button>
      </div>
      <div class="grid">
        ${keys.map(k => {
          const v = g[k] || {};
          if (v.missing) return card(k, `<p class="warn">File missing</p>`);
          if (v.error) return card(k, `<p class="warn">${esc(v.error)}</p>`);
          return card(k, `
            <p class="muted">Modified: ${esc(v.modified || '?')}</p>
            <pre class="mt">${esc(JSON.stringify(v.data, null, 2))}</pre>
          `);
        }).join('')}
      </div>`;
  },

  renderCron(s) {
    const h = s.hermes || {};
    return `
      ${!h.gateway_running ? `<div class="banner warn">⚠ Gateway stopped — cron won't fire. <code>hermes gateway start</code></div>` : ''}
      ${card('Scheduled Jobs', `<pre>${esc(h.cron_jobs || 'None')}</pre>`, 'full')}
    `;
  },

  renderSkills(s) {
    const skills = s.skills || [];
    const agentic = skills.filter(x => ['pantheon', 'claude-os-bridge', 'hotproducts-growth'].includes(x.name));
    const row = sk => `
      <div class="skill-row">
        <strong>${esc(sk.name)}</strong>
        ${sk.installed ? '<span class="badge on">installed</span>' : '<span class="badge off">repo only</span>'}
        <p class="muted">${esc(sk.description || '')}</p>
      </div>`;
    return `
      ${card('Agentic OS Skills', agentic.map(row).join('') || '<p class="muted">None</p>', 'full')}
      ${card('All Skills (' + skills.length + ')', skills.filter(x => !agentic.includes(x)).map(row).join('') || '<p class="muted">None</p>', 'full')}
    `;
  },
};

function card(title, body, width) {
  return `<div class="card${width === 'full' ? ' full' : ''}"><h2>${title}</h2>${body}</div>`;
}

function badge(on) {
  return `<span class="badge ${on ? 'on' : 'off'}">${on ? 'Running' : 'Stopped'}</span>`;
}

function esc(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

App.init();
App.refresh();
