document.addEventListener('DOMContentLoaded', () => {
    const micBtn = document.getElementById('mic-btn');
    const commandForm = document.getElementById('command-form');
    const commandInput = document.getElementById('command-input');
    const chatContainer = document.getElementById('chat-container');
    const voiceStatusText = document.getElementById('voice-status-text');
    const remindersList = document.getElementById('reminders-list');
    const refreshRemindersBtn = document.getElementById('refresh-reminders-btn');
    const clearLogBtn = document.getElementById('clear-log-btn');
    const cpuValue = document.getElementById('cpu-value');
    const ramValue = document.getElementById('ram-value');
    const toastContainer = document.getElementById('toast-container');

    let isListening = false;
    let recognition = null;

    // Initialize Web Speech Recognition if supported
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';

        recognition.onstart = () => {
            isListening = true;
            micBtn.classList.add('listening');
            voiceStatusText.textContent = "Listening... Speak your command now.";
        };

        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            commandInput.value = transcript;
            voiceStatusText.textContent = `Heard: "${transcript}"`;
            submitCommand(transcript);
        };

        recognition.onerror = (event) => {
            isListening = false;
            micBtn.classList.remove('listening');
            voiceStatusText.textContent = `Mic Error: ${event.error}. Tap mic to try again.`;
        };

        recognition.onend = () => {
            isListening = false;
            micBtn.classList.remove('listening');
        };
    } else {
        voiceStatusText.textContent = "Speech recognition not supported in browser. Use text input below.";
    }

    // Toggle Mic Listening
    micBtn.addEventListener('click', () => {
        if (!recognition) {
            showToast("Speech recognition not supported in this browser. Please type your command.");
            return;
        }
        if (isListening) {
            recognition.stop();
        } else {
            recognition.start();
        }
    });

    // Form submission
    commandForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const text = commandInput.value.trim();
        if (text) {
            submitCommand(text);
            commandInput.value = '';
        }
    });

    // API Key Helper
    function getApiKey() {
        return localStorage.getItem('jarvis_api_key') || '';
    }

    function getAuthHeaders() {
        const headers = { 'Content-Type': 'application/json' };
        const key = getApiKey();
        if (key) {
            headers['X-API-Key'] = key;
        }
        return headers;
    }

    // Submit command to REST API
    async function submitCommand(commandText) {
        appendChatBubble('user', commandText);
        voiceStatusText.textContent = "Jarvis is processing...";

        try {
            const response = await fetch('/api/command', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ command: commandText })
            });

            const data = await response.json();
            if (response.ok && data.success) {
                appendChatBubble('assistant', data.response);
                voiceStatusText.textContent = "Done!";
                fetchReminders();
            } else if (response.status === 401) {
                const key = prompt("API Key Required. Please enter your Jarvis API Key:");
                if (key) {
                    localStorage.setItem('jarvis_api_key', key.trim());
                    submitCommand(commandText);
                } else {
                    appendChatBubble('assistant', 'Error: Unauthorized. Invalid API Key.');
                }
            } else {
                appendChatBubble('assistant', `Error: ${data.response || data.detail || 'Execution failed'}`);
                voiceStatusText.textContent = "An error occurred.";
            }
        } catch (err) {
            appendChatBubble('assistant', `Server connection error: ${err.message}`);
            voiceStatusText.textContent = "Connection error.";
        }
    }

    function appendChatBubble(sender, text) {
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble ${sender}-bubble`;
        bubble.innerHTML = `<p>${escapeHtml(text)}</p>`;
        chatContainer.appendChild(bubble);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function escapeHtml(str) {
        return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    // Fetch Reminders
    async function fetchReminders() {
        try {
            const res = await fetch('/api/reminders', { headers: getAuthHeaders() });
            const data = await res.json();
            remindersList.innerHTML = '';

            if (data.reminders && data.reminders.length > 0) {
                data.reminders.forEach(r => {
                    const item = document.createElement('div');
                    item.className = 'reminder-item';
                    item.innerHTML = `
                        <span class="reminder-title">${escapeHtml(r.title || 'Untitled')}</span>
                        <span class="reminder-time">${escapeHtml(r.scheduled_time || '')}</span>
                    `;
                    remindersList.appendChild(item);
                });
            } else {
                remindersList.innerHTML = '<div style="font-size:0.85rem; color:#94a3b8; text-align:center; padding:10px;">No upcoming reminders.</div>';
            }
        } catch (err) {
            remindersList.innerHTML = '<div style="font-size:0.85rem; color:#ef4444; text-align:center; padding:10px;">Could not load reminders.</div>';
        }
    }

    // Fetch System Metrics
    async function fetchMetrics() {
        try {
            const res = await fetch('/api/status', { headers: getAuthHeaders() });
            const data = await res.json();
            if (data.cpu !== undefined) cpuValue.textContent = `${data.cpu}%`;
            if (data.ram !== undefined) ramValue.textContent = `${data.ram}%`;
        } catch (err) {}
    }

    // Toast Notifications
    function showToast(msg) {
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = msg;
        toastContainer.appendChild(toast);
        setTimeout(() => toast.remove(), 4000);
    }

    // WebSocket Connection for Real-time Notifications
    function connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const apiKey = getApiKey();
        const wsUrl = `${protocol}//${window.location.host}/ws` + (apiKey ? `?api_key=${encodeURIComponent(apiKey)}` : '');
        const ws = new WebSocket(wsUrl);

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.event === 'reminder_due') {
                    showToast(`🔔 ${data.message}`);
                    appendChatBubble('assistant', `🔔 ${data.message}`);
                    fetchReminders();
                }
            } catch (e) {}
        };

        ws.onclose = () => {
            setTimeout(connectWebSocket, 5000); // Reconnect loop
        };
    }

    // Event Listeners
    refreshRemindersBtn.addEventListener('click', fetchReminders);
    clearLogBtn.addEventListener('click', () => {
        chatContainer.innerHTML = '<div class="chat-bubble assistant-bubble"><p>Log cleared.</p></div>';
    });

    // Initial Load
    fetchReminders();
    fetchMetrics();
    setInterval(fetchMetrics, 5000);
    connectWebSocket();
});
