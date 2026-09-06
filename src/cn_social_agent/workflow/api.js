const WorkflowAPI = {
  async list() {
    const res = await fetch('/api/workflows', { headers: this._headers() });
    if (!res.ok) throw new Error('Failed to list workflows');
    return res.json();
  },

  async get(id) {
    const res = await fetch(`/api/workflows/${id}`, { headers: this._headers() });
    if (!res.ok) throw new Error('Failed to get workflow');
    return res.json();
  },

  async create(data) {
    const res = await fetch('/api/workflows', {
      method: 'POST',
      headers: { ...this._headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to create workflow');
    return res.json();
  },

  async update(id, data) {
    const res = await fetch(`/api/workflows/${id}`, {
      method: 'PUT',
      headers: { ...this._headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to update workflow');
    return res.json();
  },

  async delete(id) {
    const res = await fetch(`/api/workflows/${id}`, {
      method: 'DELETE',
      headers: this._headers(),
    });
    if (!res.ok) throw new Error('Failed to delete workflow');
    return res.json();
  },

  async run(workflowId, context = {}) {
    const res = await fetch(`/api/workflows/${workflowId}/run`, {
      method: 'POST',
      headers: { ...this._headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ context }),
    });
    if (!res.ok) throw new Error('Failed to run workflow');
    return res.json();
  },

  async listRuns(workflowId) {
    const res = await fetch(`/api/workflows/${workflowId}/runs`, { headers: this._headers() });
    if (!res.ok) throw new Error('Failed to list runs');
    return res.json();
  },

  async listTemplates() {
    const res = await fetch('/api/workflows/templates', { headers: this._headers() });
    if (!res.ok) throw new Error('Failed to list templates');
    return res.json();
  },

  async createFromTemplate(templateId, name) {
    const res = await fetch(`/api/workflows/from-template/${templateId}`, {
      method: 'POST',
      headers: { ...this._headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!res.ok) throw new Error('Failed to create from template');
    return res.json();
  },

  async getRunLogs(runId) {
    const res = await fetch(`/api/workflows/runs/${runId}/logs`, { headers: this._headers() });
    if (!res.ok) throw new Error('Failed to get run logs');
    return res.json();
  },

  async retryRun(runId) {
    const res = await fetch(`/api/workflows/runs/${runId}/retry`, {
      method: 'POST',
      headers: this._headers(),
    });
    if (!res.ok) throw new Error('Failed to retry run');
    return res.json();
  },

  async exportWorkflow(workflowId) {
    const res = await fetch(`/api/workflows/${workflowId}/export`, { headers: this._headers() });
    if (!res.ok) throw new Error('Failed to export workflow');
    return res.json();
  },

  async importWorkflow(data) {
    const res = await fetch('/api/workflows/import', {
      method: 'POST',
      headers: { ...this._headers(), 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to import workflow');
    return res.json();
  },

  _headers() {
    const token = localStorage.getItem('wb_token') || '';
    return { 'Authorization': `Bearer ${token}` };
  }
};

window.WorkflowAPI = WorkflowAPI;
