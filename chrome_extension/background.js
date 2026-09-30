/**
 * Beckie Chrome Extension – Background Service Worker (Manifest V3)
 *
 * Native Messaging Protocol (JSON-RPC 2.0 over stdin/stdout):
 *   Request:  { "jsonrpc": "2.0", "id": <int>, "method": <str>, "params": <obj> }
 *   Response: { "jsonrpc": "2.0", "id": <int>, "result": <any> }
 *           | { "jsonrpc": "2.0", "id": <int>, "error": { "code": <int>, "message": <str> } }
 *
 * Domain approval model:
 *   - No broad host_permissions are declared.
 *   - Before injecting any content script the user must explicitly grant
 *     access to the current domain via the popup UI (stored in chrome.storage.local).
 *   - Approval can be revoked domain by domain from the popup.
 */

const NATIVE_HOST = "com.beckie.jarvis";

let nativePort = null;
let pendingRequests = new Map(); // id → { resolve, reject }
let requestIdCounter = 1;

// ---------------------------------------------------------------------------
// Native port management
// ---------------------------------------------------------------------------

function connectNative() {
  if (nativePort) return nativePort;

  nativePort = chrome.runtime.connectNative(NATIVE_HOST);

  nativePort.onMessage.addListener((msg) => {
    const pending = pendingRequests.get(msg.id);
    if (!pending) return;
    pendingRequests.delete(msg.id);
    if (msg.error) {
      pending.reject(new Error(`[${msg.error.code}] ${msg.error.message}`));
    } else {
      pending.resolve(msg.result);
    }
  });

  nativePort.onDisconnect.addListener(() => {
    console.warn("Beckie native port disconnected:", chrome.runtime.lastError?.message);
    nativePort = null;
    // Reject all pending requests
    for (const [id, { reject }] of pendingRequests) {
      reject(new Error("Native host disconnected"));
    }
    pendingRequests.clear();
  });

  return nativePort;
}

/**
 * Send a JSON-RPC request to the Python native host.
 * @param {string} method
 * @param {object} params
 * @returns {Promise<any>}
 */
function sendToNative(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = requestIdCounter++;
    const port = connectNative();
    pendingRequests.set(id, { resolve, reject });
    port.postMessage({ jsonrpc: "2.0", id, method, params });
  });
}

// ---------------------------------------------------------------------------
// Domain approval helpers
// ---------------------------------------------------------------------------

async function getApprovedDomains() {
  const data = await chrome.storage.local.get("approvedDomains");
  return data.approvedDomains || [];
}

async function isDomainApproved(domain) {
  const approved = await getApprovedDomains();
  return approved.includes(domain);
}

async function approveDomain(domain) {
  const approved = await getApprovedDomains();
  if (!approved.includes(domain)) {
    approved.push(domain);
    await chrome.storage.local.set({ approvedDomains: approved });
  }
}

async function revokeDomain(domain) {
  const approved = await getApprovedDomains();
  const updated = approved.filter((d) => d !== domain);
  await chrome.storage.local.set({ approvedDomains: updated });
}

// ---------------------------------------------------------------------------
// Message handler (from popup / content scripts)
// ---------------------------------------------------------------------------

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  handleMessage(msg, sender)
    .then(sendResponse)
    .catch((err) => sendResponse({ error: err.message }));
  return true; // keep channel open for async response
});

async function handleMessage(msg, sender) {
  switch (msg.type) {

    // ── Domain approval management ──────────────────────────────────────────
    case "GET_APPROVED_DOMAINS":
      return { domains: await getApprovedDomains() };

    case "APPROVE_DOMAIN":
      await approveDomain(msg.domain);
      return { ok: true };

    case "REVOKE_DOMAIN":
      await revokeDomain(msg.domain);
      return { ok: true };

    case "CHECK_DOMAIN_APPROVED":
      return { approved: await isDomainApproved(msg.domain) };

    // ── Page content relay (gated by domain approval) ───────────────────────
    case "GET_PAGE_CONTENT": {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab) return { error: "No active tab." };

      const url = new URL(tab.url);
      const domain = url.hostname;

      if (!(await isDomainApproved(domain))) {
        return {
          error: `Domain '${domain}' is not approved. Grant access from the Beckie popup first.`,
        };
      }

      // Inject content reader into approved tab
      const results = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => ({
          title: document.title,
          url: location.href,
          text: document.body?.innerText?.slice(0, 4000) ?? "",
        }),
      });
      const content = results?.[0]?.result ?? {};
      return { content };
    }

    // ── Relay arbitrary commands to Python native host ───────────────────────
    case "NATIVE_RPC": {
      const result = await sendToNative(msg.method, msg.params);
      return { result };
    }

    // ── Ping / status ────────────────────────────────────────────────────────
    case "PING":
      return { pong: true, version: chrome.runtime.getManifest().version };

    default:
      return { error: `Unknown message type: ${msg.type}` };
  }
}
