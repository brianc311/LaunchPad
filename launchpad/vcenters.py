"""Browser page for the operator-maintained vCenters directory."""

VCENTERS_PATH = "/vcenters"

VCENTERS_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LaunchPad vCenters</title>
  <style>
    :root { --bg:#0b0f14; --panel:#151c27; --panel-alt:#0f141d; --text:#e8edf5; --muted:#a9b6c8; --accent:#ff6b00; --border:#2a3444; --danger:#ef4444; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; color:var(--text); font-family:Segoe UI,Inter,Arial,sans-serif; background:radial-gradient(circle at top,#172033 0%,var(--bg) 45%); }
    main { max-width:1120px; margin:0 auto; padding:28px 20px 48px; }
    section { margin-bottom:18px; padding:20px; border:1px solid var(--border); border-radius:14px; background:var(--panel); }
    .hero { background:linear-gradient(135deg,#1a2230,#101722); }
    h1 { margin:0 0 8px; color:var(--accent); font-size:1.9rem; }
    h2 { margin:0 0 14px; color:#ff9a56; font-size:1.12rem; }
    p, .hint, .status { color:var(--muted); line-height:1.5; }
    table { width:100%; border-collapse:collapse; }
    th, td { text-align:left; padding:8px 10px; border-bottom:1px solid var(--border); }
    th { color:var(--muted); font-size:.82rem; }
    a { color:#93c5fd; }
    button, a.button { min-height:36px; padding:0 14px; border:0; border-radius:9px; background:var(--accent); color:#111; font:inherit; font-weight:700; cursor:pointer; text-decoration:none; display:inline-flex; align-items:center; }
    button.secondary, a.secondary { color:var(--text); background:var(--panel-alt); border:1px solid var(--border); }
    button.danger { background:var(--danger); color:#fff; }
    button:disabled { opacity:.55; cursor:not-allowed; }
    .grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }
    label { display:flex; flex-direction:column; gap:6px; color:var(--muted); font-size:.86rem; font-weight:600; }
    input { width:100%; padding:9px 10px; color:var(--text); background:var(--panel-alt); border:1px solid var(--border); border-radius:8px; font:inherit; }
    .actions { display:flex; flex-wrap:wrap; gap:10px; margin-top:14px; }
    .name-btn { background:none; border:0; color:#93c5fd; padding:0; min-height:auto; font:inherit; font-weight:600; cursor:pointer; }
    .empty { color:var(--muted); padding:12px 0; }
    @media (max-width:700px) { .grid { grid-template-columns:1fr; } }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>vCenters</h1>
      <p>Directory of vCenter names, locations, and addresses. Click a name for details. The link opens the vSphere web client.</p>
      <a class="button secondary" href="/">Back to dashboard</a>
    </section>
    <section id="list-section">
      <h2>Directory</h2>
      <div class="actions"><button id="add-btn" type="button">Add</button></div>
      <div id="list-wrap"></div>
      <p id="list-status" class="status" role="status"></p>
    </section>
    <section id="detail-section" hidden>
      <h2>vCenter</h2>
      <p><strong>Name</strong><br><span id="d-name"></span></p>
      <p><strong>Location</strong><br><span id="d-location"></span></p>
      <p><strong>Address</strong><br><span id="d-address"></span></p>
      <p><strong>Link</strong><br><a id="d-link" href="#" target="_blank" rel="noopener"></a></p>
      <div class="actions">
        <button id="edit-btn" type="button">Edit</button>
        <button id="delete-btn" class="danger" type="button">Delete</button>
        <button id="back-btn" class="secondary" type="button">Back</button>
      </div>
    </section>
    <section id="form-section" hidden>
      <h2 id="form-title">Add vCenter</h2>
      <form id="vc-form" class="grid">
        <input type="hidden" id="vc-id">
        <label>Name<input id="name" name="name" required></label>
        <label>Location<input id="location" name="location"></label>
        <label>Address<input id="address" name="address" required placeholder="10.0.0.1 or vc.example.com"></label>
        <label>URL override (optional)<input id="url" name="url" placeholder="https://host/ui"></label>
      </form>
      <div class="actions">
        <button id="save-btn" type="button">Save</button>
        <button id="cancel-btn" class="secondary" type="button">Cancel</button>
      </div>
      <p id="form-status" class="status" role="status"></p>
    </section>
    <p class="hint">LaunchPad Health v{{APP_VERSION}}</p>
  </main>
  <script>
    const listWrap = document.getElementById("list-wrap");
    const listStatus = document.getElementById("list-status");
    const listSection = document.getElementById("list-section");
    const detailSection = document.getElementById("detail-section");
    const formSection = document.getElementById("form-section");
    const addBtn = document.getElementById("add-btn");
    const editBtn = document.getElementById("edit-btn");
    const deleteBtn = document.getElementById("delete-btn");
    const saveBtn = document.getElementById("save-btn");
    let rows = [];
    let unlocked = false;
    let selectedId = new URLSearchParams(location.search).get("id") || "";

    function escapeHtml(value) {
      return String(value || "").replace(/[&<>"']/g, (ch) => (
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]
      ));
    }

    function effectiveUrl(row) {
      return (row.url || "").trim() || ("https://" + row.address + "/ui");
    }

    function setMutationsEnabled(on) {
      addBtn.disabled = !on;
      editBtn.disabled = !on;
      deleteBtn.disabled = !on;
      saveBtn.disabled = !on;
      if (!on) listStatus.textContent = "Unlock LaunchPad to add or edit vCenters.";
    }

    async function loadList() {
      const res = await fetch("/api/vcenters");
      const data = await res.json();
      rows = data.vcenters || [];
      unlocked = data.unlocked === true;
      setMutationsEnabled(unlocked);
      render();
    }

    function showList() {
      selectedId = "";
      history.replaceState({}, "", "/vcenters");
      listSection.hidden = false;
      detailSection.hidden = true;
      formSection.hidden = true;
      renderTable();
    }

    function renderTable() {
      if (!rows.length) {
        listWrap.innerHTML = '<p class="empty">No vCenters yet</p>';
        return;
      }
      const body = rows.map((row) => {
        const href = escapeHtml(effectiveUrl(row));
        return `<tr>
          <td><button class="name-btn" data-id="${escapeHtml(row.id)}" type="button">${escapeHtml(row.name)}</button></td>
          <td>${escapeHtml(row.location)}</td>
          <td>${escapeHtml(row.address)}</td>
          <td><a href="${href}" target="_blank" rel="noopener">Open</a></td>
        </tr>`;
      }).join("");
      listWrap.innerHTML = `<table><thead><tr><th>Name</th><th>Location</th><th>Address</th><th>Link</th></tr></thead><tbody>${body}</tbody></table>`;
      listWrap.querySelectorAll(".name-btn").forEach((btn) => {
        btn.addEventListener("click", () => showDetail(btn.dataset.id));
      });
    }

    function rowById(id) {
      return rows.find((row) => row.id === id);
    }

    function showDetail(id) {
      const row = rowById(id);
      if (!row) { showList(); return; }
      selectedId = id;
      history.replaceState({}, "", "/vcenters?id=" + encodeURIComponent(id));
      document.getElementById("d-name").textContent = row.name;
      document.getElementById("d-location").textContent = row.location || "—";
      document.getElementById("d-address").textContent = row.address;
      const link = document.getElementById("d-link");
      link.href = effectiveUrl(row);
      link.textContent = effectiveUrl(row);
      listSection.hidden = true;
      formSection.hidden = true;
      detailSection.hidden = false;
    }

    function showForm(row) {
      document.getElementById("form-title").textContent = row ? "Edit vCenter" : "Add vCenter";
      document.getElementById("vc-id").value = row ? row.id : "";
      document.getElementById("name").value = row ? row.name : "";
      document.getElementById("location").value = row ? row.location : "";
      document.getElementById("address").value = row ? row.address : "";
      document.getElementById("url").value = row ? row.url : "";
      document.getElementById("form-status").textContent = "";
      listSection.hidden = true;
      detailSection.hidden = true;
      formSection.hidden = false;
    }

    function render() {
      if (selectedId) showDetail(selectedId);
      else showList();
    }

    addBtn.addEventListener("click", () => showForm(null));
    editBtn.addEventListener("click", () => showForm(rowById(selectedId)));
    document.getElementById("back-btn").addEventListener("click", showList);
    document.getElementById("cancel-btn").addEventListener("click", () => {
      if (selectedId) showDetail(selectedId);
      else showList();
    });
    deleteBtn.addEventListener("click", async () => {
      if (!selectedId || !confirm("Delete this vCenter?")) return;
      const res = await fetch("/api/vcenters/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: selectedId }),
      });
      const data = await res.json();
      if (!res.ok) {
        listStatus.textContent = data.error || "Delete failed.";
        return;
      }
      rows = data.vcenters || [];
      showList();
    });
    saveBtn.addEventListener("click", async () => {
      const payload = {
        id: document.getElementById("vc-id").value,
        name: document.getElementById("name").value,
        location: document.getElementById("location").value,
        address: document.getElementById("address").value,
        url: document.getElementById("url").value,
      };
      const res = await fetch("/api/vcenters", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        document.getElementById("form-status").textContent = data.error || "Save failed.";
        return;
      }
      rows = data.vcenters || [];
      unlocked = data.unlocked === true;
      const keepId = payload.id || (rows.find((row) => row.name === payload.name.trim()) || {}).id;
      selectedId = keepId || "";
      render();
    });
    loadList().catch((err) => {
      listStatus.textContent = err.message || String(err);
    });
  </script>
</body>
</html>
"""
