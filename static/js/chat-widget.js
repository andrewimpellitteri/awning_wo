/**
 * Chat Widget for RAG-enhanced AI Assistant
 *
 * Provides a floating chat interface that communicates with the
 * DeepSeek/OpenAI-powered RAG backend.
 */

(function() {
    'use strict';

    // State
    let currentSessionId = null;
    let isLoading = false;
    let ollamaStatus = null;

    // DOM Elements (will be set after widget injection)
    let widget = null;
    let messagesContainer = null;
    let inputField = null;
    let sendButton = null;
    let toggleButton = null;

    /**
     * Initialize the chat widget
     */
    function init() {
        injectWidget();
        bindEvents();
        checkStatus();
    }

    /**
     * Inject the widget HTML into the page
     */
    function injectWidget() {
        // Create toggle button
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'chat-toggle-btn';
        toggleBtn.id = 'chat-toggle-btn';
        toggleBtn.setAttribute('aria-label', 'Open chat assistant');
        toggleBtn.innerHTML = '<i class="fas fa-comments"></i>';
        document.body.appendChild(toggleBtn);
        toggleButton = toggleBtn;

        // Create widget container
        const widgetHtml = `
            <div class="chat-widget" id="chat-widget">
                <div class="chat-header">
                    <h6><i class="fas fa-robot"></i> AI Assistant</h6>
                    <div class="chat-header-actions">
                        <button class="chat-header-btn" id="chat-new-session" title="New conversation">
                            <i class="fas fa-plus"></i>
                        </button>
                        <button class="chat-header-btn" id="chat-close-btn" title="Close">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
                <div id="chat-status-bar" class="chat-status" style="display: none;">
                    <i class="fas fa-exclamation-triangle"></i>
                    <span id="chat-status-text">Checking connection...</span>
                </div>
                <div class="chat-quick-actions" id="chat-quick-actions">
                    <button class="chat-quick-action" data-query="What work orders are in progress?">In progress orders</button>
                    <button class="chat-quick-action" data-query="Show me rush orders">Rush orders</button>
                    <button class="chat-quick-action" data-query="What items need attention?">Items needing attention</button>
                </div>
                <div class="chat-messages" id="chat-messages">
                    <div class="chat-empty-state" id="chat-empty-state">
                        <i class="fas fa-comments"></i>
                        <p>Ask me anything about customers, work orders, or items!</p>
                    </div>
                </div>
                <div class="chat-input-area">
                    <textarea
                        class="chat-input"
                        id="chat-input"
                        placeholder="Type your message..."
                        rows="1"
                    ></textarea>
                    <button class="chat-send-btn" id="chat-send-btn" disabled>
                        <i class="fas fa-paper-plane"></i>
                    </button>
                </div>
            </div>
        `;

        const container = document.createElement('div');
        container.innerHTML = widgetHtml;
        document.body.appendChild(container.firstElementChild);

        // Get references to elements
        widget = document.getElementById('chat-widget');
        messagesContainer = document.getElementById('chat-messages');
        inputField = document.getElementById('chat-input');
        sendButton = document.getElementById('chat-send-btn');
    }

    /**
     * Bind event handlers
     */
    function bindEvents() {
        // Toggle widget
        toggleButton.addEventListener('click', toggleWidget);
        document.getElementById('chat-close-btn').addEventListener('click', closeWidget);

        // New session
        document.getElementById('chat-new-session').addEventListener('click', startNewSession);

        // Send message
        sendButton.addEventListener('click', sendMessage);
        inputField.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });

        // Enable/disable send button based on input
        inputField.addEventListener('input', () => {
            sendButton.disabled = !inputField.value.trim() || isLoading;
            autoResizeInput();
        });

        // Quick actions
        document.querySelectorAll('.chat-quick-action').forEach(btn => {
            btn.addEventListener('click', () => {
                const query = btn.dataset.query;
                inputField.value = query;
                sendMessage();
            });
        });

        // Close on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && widget.classList.contains('open')) {
                closeWidget();
            }
        });
    }

    /**
     * Auto-resize the input textarea
     */
    function autoResizeInput() {
        inputField.style.height = 'auto';
        inputField.style.height = Math.min(inputField.scrollHeight, 100) + 'px';
    }

    /**
     * Toggle widget visibility
     */
    function toggleWidget() {
        if (widget.classList.contains('open')) {
            closeWidget();
        } else {
            openWidget();
        }
    }

    /**
     * Open the widget
     */
    function openWidget() {
        widget.classList.add('open');
        toggleButton.innerHTML = '<i class="fas fa-times"></i>';
        inputField.focus();

        // Start a new session if none exists
        if (!currentSessionId) {
            startNewSession();
        }
    }

    /**
     * Close the widget
     */
    function closeWidget() {
        widget.classList.remove('open');
        toggleButton.innerHTML = '<i class="fas fa-comments"></i>';
    }

    /**
     * Check AI service/backend status
     */
    async function checkStatus() {
        const statusBar = document.getElementById('chat-status-bar');
        const statusText = document.getElementById('chat-status-text');

        try {
            const response = await fetch('/api/chat/status');
            const data = await response.json();
            ollamaStatus = data;

            if (!data.ollama.api_available && !data.ollama.ollama_running) {
                statusBar.style.display = 'flex';
                statusBar.className = 'chat-status error';
                statusText.textContent = 'AI service unavailable. Check API keys.';
            } else if (!data.ollama.chat_model_available || !data.ollama.embed_model_available) {
                statusBar.style.display = 'flex';
                statusBar.className = 'chat-status';
                const missing = [];
                if (!data.ollama.chat_model_available) missing.push('Chat API');
                if (!data.ollama.embed_model_available) missing.push('Embedding API');
                statusText.textContent = `Missing: ${missing.join(', ')}`;
            } else {
                statusBar.style.display = 'none';
            }
        } catch (error) {
            console.error('Failed to check status:', error);
            statusBar.style.display = 'flex';
            statusBar.className = 'chat-status error';
            statusText.textContent = 'Failed to connect to server';
        }
    }

    /**
     * Start a new chat session
     */
    async function startNewSession() {
        try {
            // Get context from current page if available
            const context = getPageContext();

            const response = await fetch('/api/chat/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(context)
            });

            if (!response.ok) {
                throw new Error('Failed to create session');
            }

            const data = await response.json();
            currentSessionId = data.session.id;

            // Clear messages
            clearMessages();
            showEmptyState();

        } catch (error) {
            console.error('Failed to start session:', error);
            showError('Failed to start conversation. Please try again.');
        }
    }

    /**
     * Get context from the current page
     */
    function getPageContext() {
        const context = {};
        const url = window.location.pathname;

        // Check if on work order page
        const woMatch = url.match(/\/work_orders\/([^\/]+)/);
        if (woMatch) {
            context.work_order_no = woMatch[1];
        }

        // Check if on customer page
        const custMatch = url.match(/\/customers\/([^\/]+)/);
        if (custMatch) {
            context.customer_id = custMatch[1];
        }

        return context;
    }

    /**
     * Send a message
     */
    async function sendMessage() {
        const message = inputField.value.trim();
        if (!message || isLoading) return;

        // Ensure we have a session
        if (!currentSessionId) {
            await startNewSession();
        }

        // Clear input
        inputField.value = '';
        inputField.style.height = 'auto';
        sendButton.disabled = true;

        // Hide empty state
        hideEmptyState();

        // Add user message to UI
        addMessage(message, 'user');

        // Show typing indicator
        showTypingIndicator();
        isLoading = true;

        try {
            const context = getPageContext();
            const response = await fetch(`/api/chat/sessions/${currentSessionId}/messages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: message,
                    work_order_context: context.work_order_no,
                    customer_context: context.customer_id
                })
            });

            hideTypingIndicator();

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to send message');
            }

            const data = await response.json();
            addMessage(data.assistant_message.content, 'assistant', data.assistant_message.metadata);

        } catch (error) {
            hideTypingIndicator();
            console.error('Failed to send message:', error);
            addMessage(`Sorry, I encountered an error: ${error.message}`, 'assistant', { error: true });
        } finally {
            isLoading = false;
            sendButton.disabled = !inputField.value.trim();
        }
    }

    /**
     * Add a message to the UI
     */
    function addMessage(content, role, metadata = {}) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${role}`;

        const contentDiv = document.createElement('div');
        contentDiv.className = 'chat-message-content';
        contentDiv.innerHTML = formatMessage(content);

        messageDiv.appendChild(contentDiv);

        // Add citations/sources if available (for RAG or tool responses)
        if (role === 'assistant' && (metadata.sources || metadata.tool_calls)) {
            const citationsDiv = createCitationsDisplay(metadata.sources, metadata.tool_calls);
            if (citationsDiv) {
                messageDiv.appendChild(citationsDiv);
            }
        }

        const timeDiv = document.createElement('div');
        timeDiv.className = 'chat-message-time';
        timeDiv.textContent = formatTime(new Date());

        messageDiv.appendChild(timeDiv);

        messagesContainer.appendChild(messageDiv);
        scrollToBottom();
    }

    /**
     * Format message content (basic markdown support)
     */
    function formatMessage(content) {
        // Escape HTML
        let formatted = content
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');

        // Code blocks
        formatted = formatted.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');

        // Inline code
        formatted = formatted.replace(/`([^`]+)`/g, '<code>$1</code>');

        // Bold
        formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

        // Italic
        formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');

        // Line breaks
        formatted = formatted.replace(/\n/g, '<br>');

        // Lists (simple detection)
        formatted = formatted.replace(/^- (.+)$/gm, '<li>$1</li>');
        formatted = formatted.replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>');

        return formatted;
    }

    /**
     * Create a professional dropdown display for citations and tool calls
     */
    function createCitationsDisplay(sources, toolCalls) {
        if (!sources && !toolCalls) return null;

        const container = document.createElement('div');
        container.className = 'citations-container';

        // Tool Calls Section (if any)
        if (toolCalls && toolCalls.length > 0) {
            const toolsSection = document.createElement('details');
            toolsSection.className = 'citations-dropdown';
            toolsSection.open = true; // Open by default

            const summary = document.createElement('summary');
            summary.className = 'citations-summary';
            summary.innerHTML = `
                <i class="fas fa-tools"></i>
                <span class="citations-label">Database Queries (${toolCalls.length})</span>
                <i class="fas fa-chevron-down citations-chevron"></i>
            `;

            const content = document.createElement('div');
            content.className = 'citations-content';

            toolCalls.forEach((call, idx) => {
                const toolItem = document.createElement('div');
                toolItem.className = 'tool-call-item';

                const toolName = call.tool || `Query ${idx + 1}`;
                const args = call.arguments || {};

                toolItem.innerHTML = `
                    <div class="tool-call-header">
                        <i class="fas fa-database"></i>
                        <span class="tool-call-name">${toolName}</span>
                    </div>
                    <div class="tool-call-args">${formatToolArguments(args)}</div>
                `;

                content.appendChild(toolItem);
            });

            toolsSection.appendChild(summary);
            toolsSection.appendChild(content);
            container.appendChild(toolsSection);
        }

        // Sources Section (if any)
        if (sources && (sources.customers?.length || sources.work_orders?.length || sources.items?.length)) {
            const sourcesSection = document.createElement('details');
            sourcesSection.className = 'citations-dropdown';

            const totalSources = (sources.customers?.length || 0) +
                                (sources.work_orders?.length || 0) +
                                (sources.items?.length || 0);

            const summary = document.createElement('summary');
            summary.className = 'citations-summary';
            summary.innerHTML = `
                <i class="fas fa-book"></i>
                <span class="citations-label">Sources (${totalSources})</span>
                <i class="fas fa-chevron-down citations-chevron"></i>
            `;

            const content = document.createElement('div');
            content.className = 'citations-content';

            if (sources.customers?.length) {
                sources.customers.forEach(custId => {
                    const link = document.createElement('a');
                    link.href = `/customers/${custId}`;
                    link.className = 'citation-link customer';
                    link.innerHTML = `<i class="fas fa-user"></i> Customer ${custId}`;
                    link.target = '_blank';
                    content.appendChild(link);
                });
            }

            if (sources.work_orders?.length) {
                sources.work_orders.forEach(woNo => {
                    const link = document.createElement('a');
                    link.href = `/work_orders/${woNo}`;
                    link.className = 'citation-link work-order';
                    link.innerHTML = `<i class="fas fa-clipboard-list"></i> Work Order ${woNo}`;
                    link.target = '_blank';
                    content.appendChild(link);
                });
            }

            if (sources.items?.length) {
                sources.items.forEach(itemId => {
                    const link = document.createElement('a');
                    link.href = `#item-${itemId}`;
                    link.className = 'citation-link item';
                    link.innerHTML = `<i class="fas fa-box"></i> Item ${itemId}`;
                    content.appendChild(link);
                });
            }

            sourcesSection.appendChild(summary);
            sourcesSection.appendChild(content);
            container.appendChild(sourcesSection);
        }

        return container.children.length > 0 ? container : null;
    }

    /**
     * Format tool arguments for display
     */
    function formatToolArguments(args) {
        if (!args || Object.keys(args).length === 0) {
            return '<span class="tool-args-empty">No parameters</span>';
        }

        return Object.entries(args)
            .map(([key, value]) => {
                const displayValue = typeof value === 'string' && value.length > 50
                    ? value.substring(0, 50) + '...'
                    : value;
                return `<span class="tool-arg"><strong>${key}:</strong> ${displayValue}</span>`;
            })
            .join(' ');
    }

    /**
     * Format time for display
     */
    function formatTime(date) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    /**
     * Show typing indicator (with enhanced "thinking" display)
     */
    function showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'chat-message assistant';
        indicator.id = 'typing-indicator';
        indicator.innerHTML = `
            <div class="chat-message-content">
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
            <div class="tool-execution">
                <div class="tool-execution-spinner"></div>
                <span class="tool-execution-text">Searching database...</span>
            </div>
        `;
        messagesContainer.appendChild(indicator);
        scrollToBottom();
    }

    /**
     * Update thinking indicator with tool info
     */
    function updateThinkingText(text) {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            const textEl = indicator.querySelector('.tool-execution-text');
            if (textEl) {
                textEl.textContent = text;
            }
        }
    }

    /**
     * Hide typing indicator
     */
    function hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    }

    /**
     * Show empty state
     */
    function showEmptyState() {
        const emptyState = document.getElementById('chat-empty-state');
        if (emptyState) {
            emptyState.style.display = 'flex';
        }
    }

    /**
     * Hide empty state
     */
    function hideEmptyState() {
        const emptyState = document.getElementById('chat-empty-state');
        if (emptyState) {
            emptyState.style.display = 'none';
        }
    }

    /**
     * Clear all messages
     */
    function clearMessages() {
        const messages = messagesContainer.querySelectorAll('.chat-message');
        messages.forEach(msg => msg.remove());
    }

    /**
     * Show error message
     */
    function showError(message) {
        addMessage(message, 'assistant', { error: true });
    }

    /**
     * Scroll to bottom of messages
     */
    function scrollToBottom() {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose for external use if needed
    window.ChatWidget = {
        open: openWidget,
        close: closeWidget,
        toggle: toggleWidget,
        sendMessage: (msg) => {
            inputField.value = msg;
            sendMessage();
        }
    };

})();
