const $ = (id) => document.getElementById(id);

function setStatus(text, kind) {
  const status = $("status");
  status.textContent = text;
  status.className = `status ${kind || ""}`.trim();
}

async function readJson(path, options) {
  const response = await fetch(path, options);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  return body;
}

function fillPresets(presets, currentUrl) {
  const select = $("preset");
  select.innerHTML = "";
  for (const preset of presets) {
    const option = document.createElement("option");
    option.value = preset.url;
    option.textContent = preset.label;
    select.appendChild(option);
  }
  const custom = document.createElement("option");
  custom.value = "";
  custom.textContent = "Custom URL";
  select.appendChild(custom);
  const match = presets.find((preset) => preset.url === currentUrl);
  select.value = match ? match.url : "";
}

function renderTools(tools) {
  const list = $("tools");
  const picker = $("tool-name");
  list.innerHTML = "";
  picker.innerHTML = "";
  for (const tool of tools) {
    const item = document.createElement("li");
    item.textContent = tool.name;
    list.appendChild(item);
    const option = document.createElement("option");
    option.value = tool.name;
    option.textContent = tool.name;
    picker.appendChild(option);
  }
  $("tools-panel").hidden = tools.length === 0;
}

async function connect() {
  const url = $("mcp-url").value.trim();
  setStatus("Connecting…");
  try {
    const result = await readJson("/api/handshake", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const name = result.serverInfo?.name || "MCP server";
    setStatus(`Connected to ${name} · ${result.tools.length} tools`, "ok");
    renderTools(result.tools);
  } catch (error) {
    setStatus(error.message, "bad");
    $("tools-panel").hidden = true;
  }
}

async function callSelected() {
  const url = $("mcp-url").value.trim();
  const name = $("tool-name").value;
  let args = {};
  try {
    args = JSON.parse($("tool-args").value || "{}");
  } catch {
    $("result").hidden = false;
    $("result").textContent = "Arguments must be JSON.";
    return;
  }
  const result = $("result");
  result.hidden = false;
  result.textContent = "Calling…";
  try {
    const body = await readJson("/api/tools/call", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, name, arguments: args }),
    });
    result.textContent = JSON.stringify(body, null, 2);
  } catch (error) {
    result.textContent = error.message;
  }
}

const config = await readJson("/api/config");
$("mcp-url").value = config.mcpUrl;
fillPresets(config.presets, config.mcpUrl);
$("provider-url").value = config.provider?.baseUrl || "";
$("provider-model").value = config.provider?.model || "";

const about = await readJson("/api/about");
$("about-body").textContent = about.body;

const updates = await readJson("/api/updates");
if (!updates.enabled) {
  $("updates").textContent =
    `Update checks are off. Placeholder releases page: ${updates.releasesPageUrl}`;
}

$("preset").addEventListener("change", () => {
  if ($("preset").value) {
    $("mcp-url").value = $("preset").value;
  }
});
$("connect").addEventListener("click", connect);
$("call").addEventListener("click", callSelected);
