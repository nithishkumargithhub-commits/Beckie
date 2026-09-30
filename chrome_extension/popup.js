/**
 * Beckie popup script – manages per-domain content approval UI.
 */

async function getCurrentDomain() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.url) return null;
  try { return new URL(tab.url).hostname; } catch { return null; }
}

async function render() {
  const domain = await getCurrentDomain();
  const domainEl = document.getElementById("current-domain");
  domainEl.textContent = domain ? `Current page: ${domain}` : "No active page";

  const { domains } = await chrome.runtime.sendMessage({ type: "GET_APPROVED_DOMAINS" });
  const listEl = document.getElementById("domain-list");
  listEl.innerHTML = "";

  if (!domains.length) {
    listEl.innerHTML = '<p class="empty">No domains approved yet.</p>';
  } else {
    for (const d of domains) {
      const row = document.createElement("div");
      row.className = "domain-row";
      row.innerHTML = `
        <span class="domain-name">${d}</span>
        <button class="revoke-btn" data-domain="${d}">Revoke</button>
      `;
      listEl.appendChild(row);
    }
  }

  // Wire revoke buttons
  listEl.querySelectorAll(".revoke-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      await chrome.runtime.sendMessage({ type: "REVOKE_DOMAIN", domain: btn.dataset.domain });
      render();
    });
  });

  // Approve button
  const approveBtn = document.getElementById("approve-btn");
  if (domain) {
    const { approved } = await chrome.runtime.sendMessage({
      type: "CHECK_DOMAIN_APPROVED", domain,
    });
    approveBtn.textContent = approved
      ? `✓ ${domain} already approved`
      : `Grant access to ${domain}`;
    approveBtn.disabled = approved;
    approveBtn.onclick = async () => {
      await chrome.runtime.sendMessage({ type: "APPROVE_DOMAIN", domain });
      render();
    };
  } else {
    approveBtn.disabled = true;
    approveBtn.textContent = "No active domain";
  }
}

render();
