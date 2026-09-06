const wfEscapeHtml = (s) => String(s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));

class ScheduleManager {
  constructor(container) {
    this.container = container;
    this.schedules = [];
    this.init();
  }

  init() {
    this.container.innerHTML = `
      <div style="display:flex;flex-direction:column;height:100%;">
        <div style="padding:12px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center;">
          <span style="font-weight:600;font-size:14px;">定时任务</span>
          <button id="refreshSchedulesBtn" style="padding:4px 8px;border:1px solid var(--line);border-radius:4px;cursor:pointer;font-size:12px;background:var(--panel);">刷新</button>
        </div>
        <div id="scheduleList" style="flex:1;overflow:auto;padding:8px;"></div>
      </div>
    `;

    document.getElementById('refreshSchedulesBtn').addEventListener('click', () => this.load());
    this.load();
  }

  async load() {
    try {
      const data = await window.WorkflowAPI.list();
      const workflows = data.workflows || [];
      this.schedules = workflows
        .map(wf => {
          const node = (wf.nodes || []).find(n => n.type === 'trigger.schedule');
          if (!node) return null;
          return {
            id: wf.id,
            name: wf.name || '未命名',
            cron: node.config?.cron || wf.trigger?.cron || '未设置',
            enabled: wf.enabled !== false,
          };
        })
        .filter(Boolean);
      this.renderList();
    } catch (err) {
      console.error('Failed to load schedules:', err);
      this.renderEmpty('加载定时任务失败');
    }
  }

  renderList() {
    const list = document.getElementById('scheduleList');
    if (!list) return;

    if (this.schedules.length === 0) {
      this.renderEmpty('暂无定时任务 — 给工作流添加「定时触发」节点后在此管理');
      return;
    }

    list.innerHTML = this.schedules.map(s => {
      const enabled = s.enabled !== false;
      const statusColor = enabled ? '#22c55e' : '#94a3b8';
      const statusText = enabled ? '已启用' : '已暂停';

      return `
        <div class="schedule-item" data-schedule-id="${wfEscapeHtml(s.id)}" style="padding:10px 12px;margin-bottom:6px;background:var(--bg);border-radius:6px;cursor:pointer;border-left:3px solid ${statusColor};">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="font-size:13px;font-weight:500;">${wfEscapeHtml(s.name)}</span>
            <span style="font-size:10px;padding:2px 6px;background:${statusColor}20;color:${statusColor};border-radius:4px;">${statusText}</span>
          </div>
          <div style="font-size:11px;color:var(--muted);margin-top:4px;">Cron: ${wfEscapeHtml(String(s.cron))}</div>
        </div>
      `;
    }).join('');

    list.querySelectorAll('.schedule-item').forEach(item => {
      item.addEventListener('click', () => {
        const scheduleId = item.dataset.scheduleId;
        this.selectSchedule(scheduleId);
      });
    });
  }

  renderEmpty(msg) {
    const list = document.getElementById('scheduleList');
    if (list) {
      list.innerHTML = `<div style="padding:16px;color:var(--muted);text-align:center;">${msg}</div>`;
    }
  }

  selectSchedule(scheduleId) {
    const schedule = this.schedules.find(s => s.id === scheduleId);
    if (!schedule) return;

    document.querySelectorAll('.schedule-item').forEach(item => {
      item.style.background = item.dataset.scheduleId === scheduleId ? 'var(--panel)' : 'var(--bg)';
    });

    if (this.onScheduleSelect) {
      this.onScheduleSelect(schedule);
    }
  }

  async toggleSchedule(scheduleId, enabled) {
    try {
      await window.WorkflowAPI.update(scheduleId, { enabled });
      this.load();
    } catch (err) {
      console.error('Failed to toggle schedule:', err);
    }
  }

  async deleteSchedule(scheduleId) {
    if (!confirm('确定要删除这个定时任务吗？')) return;

    try {
      await window.WorkflowAPI.delete(scheduleId);
      this.load();
    } catch (err) {
      console.error('Failed to delete schedule:', err);
    }
  }
}

window.ScheduleManager = ScheduleManager;
