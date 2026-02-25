/**
 * AgentForge Dashboard — Alpine.js Application
 */
function dashboard() {
    return {
        // State
        status: 'Connecting...',
        totalCost: 0,
        totalTokens: 0,
        elapsed: '0.0s',
        agents: [],
        steps: [],
        costByModel: {},
        pendingApproval: null,
        toasts: [],
        ws: null,
        startTime: null,
        elapsedInterval: null,

        // Computed
        get statusColor() {
            const map = {
                'Running': 'bg-accent-blue animate-pulse',
                'Completed': 'bg-accent-green',
                'Error': 'bg-accent-red',
                'Awaiting Approval': 'bg-accent-amber animate-pulse',
                'Idle': 'bg-gray-500',
                'Connecting...': 'bg-gray-500 animate-pulse',
            };
            return map[this.status] || 'bg-gray-500';
        },

        // Init
        init() {
            this.connectWebSocket();
            this.fetchTrace();
        },

        connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;

            try {
                this.ws = new WebSocket(wsUrl);

                this.ws.onopen = () => {
                    this.addToast('Connected to AgentForge', 'info');
                };

                this.ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.handleEvent(data);
                    } catch (e) {
                        console.error('Failed to parse event:', e);
                    }
                };

                this.ws.onclose = () => {
                    this.status = 'Disconnected';
                    // Reconnect after 2 seconds
                    setTimeout(() => this.connectWebSocket(), 2000);
                };

                this.ws.onerror = () => {
                    // Will trigger onclose
                };
            } catch (e) {
                setTimeout(() => this.connectWebSocket(), 2000);
            }
        },

        async fetchTrace() {
            try {
                const resp = await fetch('/api/trace');
                const data = await resp.json();
                if (data.events) {
                    data.events.forEach(e => this.handleEvent(e));
                }
                if (data.cost_breakdown) {
                    this.totalCost = data.cost_breakdown.total_cost || 0;
                    this.costByModel = data.cost_breakdown.by_model || {};
                    const t = data.cost_breakdown.total_tokens || {};
                    this.totalTokens = (t.input || 0) + (t.output || 0);
                }
            } catch (e) {
                // Server might not be ready yet
            }
        },

        handleEvent(event) {
            const type = event.event_type;

            switch (type) {
                case 'workflow_start':
                    this.status = 'Running';
                    this.startTime = Date.now();
                    this.startElapsedTimer();
                    if (event.data && event.data.agents) {
                        this.agents = event.data.agents.map(name => ({
                            name,
                            role: '',
                            model: '',
                            tokens: 0,
                            cost: 0,
                            status: 'idle'
                        }));
                    }
                    break;

                case 'workflow_end':
                    this.status = event.data?.success ? 'Completed' : 'Error';
                    this.stopElapsedTimer();
                    if (event.data?.success) {
                        this.addToast('Workflow completed successfully!', 'success');
                    } else {
                        this.addToast('Workflow failed', 'error');
                    }
                    break;

                case 'step_start':
                    this.addOrUpdateStep(event.step_id, {
                        id: event.step_id,
                        agent: event.agent_name,
                        status: 'running',
                        task: event.data?.task || '',
                        output: '',
                        tokens: 0,
                        cost: 0,
                        duration: 0,
                        model: '',
                        toolCalls: [],
                        expanded: false,
                    });
                    this.updateAgentStatus(event.agent_name, 'running');
                    break;

                case 'step_end':
                    this.addOrUpdateStep(event.step_id, {
                        status: event.data?.success ? 'completed' : 'error',
                        model: event.data?.model || '',
                        tokens: (event.tokens?.input || 0) + (event.tokens?.output || 0),
                        cost: event.cost || 0,
                        duration: (event.duration_ms || 0) / 1000,
                        output: event.data?.output_preview || '',
                    });
                    this.updateAgentStatus(event.agent_name, event.data?.success ? 'done' : 'error');
                    this.updateCosts(event);
                    this.addToast(`Step "${event.step_id}" completed`, 'success');
                    break;

                case 'agent_response':
                    this.updateCosts(event);
                    if (event.agent_name) {
                        const agent = this.agents.find(a => a.name === event.agent_name);
                        if (agent) {
                            agent.tokens += (event.tokens?.input || 0) + (event.tokens?.output || 0);
                            agent.cost += event.cost || 0;
                            agent.model = event.data?.model || agent.model;
                        }
                    }
                    break;

                case 'tool_call':
                    if (event.step_id) {
                        const step = this.steps.find(s => s.id === event.step_id);
                        if (step) {
                            step.toolCalls = step.toolCalls || [];
                            step.toolCalls.push({
                                tool: event.data?.tool || '',
                                args: event.data?.args || {},
                                result: '',
                                time: Date.now()
                            });
                        }
                    }
                    break;

                case 'tool_result':
                    // Update last tool call with result
                    if (event.step_id) {
                        const step = this.steps.find(s => s.id === event.step_id);
                        if (step && step.toolCalls && step.toolCalls.length > 0) {
                            const lastTc = step.toolCalls[step.toolCalls.length - 1];
                            lastTc.result = event.data?.output_preview || '';
                        }
                    }
                    break;

                case 'approval_requested':
                    this.status = 'Awaiting Approval';
                    this.pendingApproval = {
                        step_id: event.step_id,
                        agent: event.agent_name,
                        output: event.data?.output_preview || '',
                    };
                    this.addToast('Approval required for step "' + event.step_id + '"', 'info');
                    break;

                case 'approval_received':
                    this.pendingApproval = null;
                    this.status = 'Running';
                    break;

                case 'error':
                    this.addToast('Error: ' + (event.data?.error || 'Unknown'), 'error');
                    break;
            }
        },

        addOrUpdateStep(stepId, updates) {
            const existing = this.steps.find(s => s.id === stepId);
            if (existing) {
                Object.assign(existing, updates);
            } else {
                this.steps.push({
                    id: stepId,
                    agent: '',
                    status: 'pending',
                    task: '',
                    output: '',
                    tokens: 0,
                    cost: 0,
                    duration: 0,
                    model: '',
                    toolCalls: [],
                    expanded: false,
                    ...updates
                });
            }
        },

        updateAgentStatus(name, status) {
            const agent = this.agents.find(a => a.name === name);
            if (agent) {
                agent.status = status;
            }
        },

        updateCosts(event) {
            if (event.cost) {
                this.totalCost += event.cost;
            }
            const tok = (event.tokens?.input || 0) + (event.tokens?.output || 0);
            if (tok) {
                this.totalTokens += tok;
            }
        },

        stepIcon(step) {
            const map = {
                'completed': '✅',
                'running': '🔄',
                'error': '❌',
                'pending': '⏳',
            };
            return map[step.status] || '⏳';
        },

        agentStatusColor(agent) {
            const map = {
                'running': 'bg-accent-blue animate-pulse',
                'done': 'bg-accent-green',
                'error': 'bg-accent-red',
                'idle': 'bg-gray-500',
            };
            return map[agent.status] || 'bg-gray-500';
        },

        async approve(approved) {
            if (!this.pendingApproval) return;
            try {
                await fetch(`/api/approve/${this.pendingApproval.step_id}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ approved }),
                });
                this.addToast(approved ? 'Step approved' : 'Step rejected', approved ? 'success' : 'error');
                this.pendingApproval = null;
                this.status = 'Running';
            } catch (e) {
                this.addToast('Failed to send approval', 'error');
            }
        },

        addToast(message, type = 'info') {
            const id = Date.now() + Math.random();
            this.toasts.push({ id, message, type });
        },

        startElapsedTimer() {
            this.stopElapsedTimer();
            this.elapsedInterval = setInterval(() => {
                if (this.startTime) {
                    const secs = (Date.now() - this.startTime) / 1000;
                    this.elapsed = secs.toFixed(1) + 's';
                }
            }, 100);
        },

        stopElapsedTimer() {
            if (this.elapsedInterval) {
                clearInterval(this.elapsedInterval);
                this.elapsedInterval = null;
            }
        },
    };
}
