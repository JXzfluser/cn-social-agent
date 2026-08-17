export const meta = {
  name: 'phase1-full-implementation',
  description: 'Phase 1 完整实施：T-05 + T-04 + R-01 Analytics + R-02 Calendar',
  phases: [
    { title: 'T-05 + T-04 Tech Debt', detail: 'scheduler filter + /metrics endpoint' },
    { title: 'Backend: R-01 Analytics API', detail: '4个 analytics API + notification API' },
    { title: 'Frontend: R-01 Analytics BI', detail: 'Chart.js 真实图表' },
    { title: 'Frontend: R-02 Calendar', detail: '月历视图 + 拖拽排期' },
    { title: 'Verify', detail: '集成验证所有改动' },
  ],
}

// ─── Phase 1: T-05 Scheduler Filter + T-04 Metrics ──────────────────────────
phase('T-05 + T-04 Tech Debt')
const [t05Result, t04Result] = await Promise.all([
  agent(
    `在 /Users/zfl/projects/cn-social-agent 中实施 T-05 scheduler filter 改造。

步骤：
1. 读取 src/scheduler/scheduler.py，找到 list_tasks 方法，增加 status 和 platform 两个可选过滤参数。
2. 在方法体内对任务列表做过滤：status 非空则 task.status == status；platform 非空则 task.metadata.get('platform') == platform
3. 读取 src/server.py，找到 GET /api/scheduler/tasks 路由的 handler，确认它从 query string 读取 status 和 platform 并传给 list_tasks
4. 确认 handler 签名正确（Optional imported from typing）
5. 运行语法检查：cd /Users/zfl/projects/cn-social-agent && python3 -m py_compile src/scheduler/scheduler.py && python3 -m py_compile src/server.py

返回 JSON：{"filesChanged": ["文件路径列表"], "apiAdded": ["端点列表"], "filtersSupported": ["过滤字段"]}`,
    { phase: 'T-05 + T-04 Tech Debt', schema: { type: 'object', properties: { filesChanged: { type: 'array' }, apiAdded: { type: 'array' }, filtersSupported: { type: 'array' } }, required: ['filesChanged'] } }
  ),
  agent(
    `在 /Users/zfl/projects/cn-social-agent 中实施 T-04 observability metrics 端点。

步骤：
1. 读取 src/observability/metrics.py，确认已有 Prometheus 格式导出方法（export_prometheus 或类似）
2. 读取 src/server.py，找到 create_app 函数的位置
3. 在 server.py 添加：from cn_social_agent.observability.metrics import get_global_metrics_collector（或适当的 import）
4. 在 create_app 中添加路由：app.router.add_get('/metrics', metrics_handler)
5. 实现 metrics_handler：
   - 调用 metrics_collector.export_prometheus() 或遍历 collector 的 metrics
   - 返回 web.Response(text=prometheus_text, content_type='text/plain; charset=utf-8')
6. 运行语法检查确认无错误

注意：/metrics 端点无需认证。

返回 JSON：{"filesChanged": ["文件路径"], "endpoint": "/metrics"}`,
    { phase: 'T-05 + T-04 Tech Debt', schema: { type: 'object', properties: { filesChanged: { type: 'array' }, endpoint: { type: 'string' } }, required: ['filesChanged'] } }
  ),
])

// ─── Phase 2: Backend Analytics + Notifications API ───────────────────────────
phase('Backend: R-01 Analytics API')

const analyticsBeResult = await agent(
  `在 /Users/zfl/projects/cn-social-agent/src/admin/web.py 中添加以下后端 API 处理器，并在 create_app() 中注册路由。

## 需要添加的 handler（在 save_llm_config_handler 之后添加）

### 1. content_trend_handler
实现 GET /api/analytics/content-trend?range=7d|30d|90d
- 从 review.db 聚合每日生成数量（created_at）和发布数量（status=approved 且 updated_at）
- 返回 {"labels": ["2026-06-01", ...], "generated": [5, ...], "published": [3, ...]}

### 2. platform_distribution_handler
实现 GET /api/analytics/platform-distribution
- 从 review.db 的 platforms 字段聚合各平台数量
- 返回 {"labels": ["weibo", ...], "values": [45, ...]}

### 3. engagement_handler
实现 GET /api/analytics/engagement?range=7d
- Phase1：基于已发布内容数做估算（impressions=总数*1200, likes=总数*85, comments=总数*12, shares=总数*6）
- 返回 {"impressions": N, "likes": N, "comments": N, "shares": N}

### 4. publish_calendar_handler
实现 GET /api/analytics/publish-calendar?year=2026&month=6
- 从 app._scheduler.list_tasks() 获取任务
- 过滤 year/month 匹配 next_run.date()
- 返回 {"year": N, "month": N, "items": [{"id": "...", "title": "...", "date": "2026-06-15", "status": "PENDING", "platform": "weibo"}, ...]}

### 5. notifications_handler
实现 GET /api/notifications?limit=20&type=&read=
- 使用 SQLite（data/notifications.db）存储通知
- 首次调用时自动建表：id, title, body, type, read(0/1), user_id, created_at
- 返回 {"items": [...], "unread": N, "total": N}

### 6. notifications_read_handler
实现 PUT /api/notifications/read
- body: {"ids": [1,2,3]} 或 {"ids": []}（空=全部已读）
- 更新 SQLite 中对应记录的 read=1

## 路由注册
在 create_app() 的路由注册区域，找到现有 admin API 路由末尾，添加：
app.router.add_get('/api/analytics/content-trend', content_trend_handler)
app.router.add_get('/api/analytics/platform-distribution', platform_distribution_handler)
app.router.add_get('/api/analytics/engagement', engagement_handler)
app.router.add_get('/api/analytics/publish-calendar', publish_calendar_handler)
app.router.add_get('/api/notifications', notifications_handler)
app.router.add_put('/api/notifications/read', notifications_read_handler)

## 注意事项
- import sqlite3, os, json, datetime 在 handler 顶部
- 路径用 os.getenv('DATA_DIR', 'data') + '/notifications.db'
- 异常处理：try/except 返回 500 + error 字段
- 语法检查：python3 -m py_compile src/admin/web.py

返回 JSON：{"filesChanged": ["src/admin/web.py"], "endpointsAdded": ["端点列表"]}`,
  { phase: 'Backend: R-01 Analytics API', schema: { type: 'object', properties: { filesChanged: { type: 'array' }, endpointsAdded: { type: 'array' } }, required: ['filesChanged'] } }
)

// ─── Phase 3: Frontend Analytics Dashboard ───────────────────────────────────
phase('Frontend: R-01 Analytics BI')

const analyticsFeResult = await agent(
  `在 /Users/zfl/projects/cn-social-agent 中用真实 API 替换 analytics 页面的假数据占位符。

## 目标：修改 src/admin/index.html 和 src/admin/app.js

### A. index.html 修改

1. 在 analytics page 的 .card-body 中，在最顶部添加 Chart.js CDN：
在第一个 <div class="card"> 之前添加：
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>

2. 替换 analytics page 中的 .chart-placeholder，找到 id="analytics-trend-chart" 的 div，替换为：
<canvas id="chart-trend" height="160"></canvas>

3. 在 analytics page 中，platform-distribution 的 .card-body 内，找到 .platform-distribution 替换为：
<canvas id="chart-platform" height="160"></canvas>

4. 在 analytics page 中，在平台分布卡片之后添加互动数据卡片：
<div class="card mt-6">
    <div class="card-header"><h3 class="card-title">互动数据 <span style="font-size:11px;color:var(--text-muted);font-weight:400">(Phase1 估算数据)</span></h3></div>
    <div class="card-body">
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px" id="engagement-stats"></div>
    </div>
</div>

### B. app.js 修改

找到 analytics 模块（Modules.analytics），替换整个模块为以下实现：
analytics: {
    trendChart: null,
    platformChart: null,
    async load() {
        const range = document.getElementById('analytics-range')?.value || '7d';
        Toast.info('加载数据...');
        try {
            await Promise.all([this.loadTrend(range), this.loadPlatform(), this.loadEngagement()]);
            Toast.success('数据已加载');
        } catch(e) {
            Toast.error('数据加载失败：' + (e.message || '未知错误'));
        }
    },
    async loadTrend(range) {
        const data = await API.get('/api/analytics/content-trend?range=' + range);
        if (!data || data.error) { Toast.warning('趋势数据加载失败'); return; }
        const ctx = document.getElementById('chart-trend');
        if (!ctx) return;
        if (typeof Chart === 'undefined') { console.warn('Chart.js not loaded'); return; }
        if (this.trendChart) this.trendChart.destroy();
        this.trendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels || [],
                datasets: [
                    { label: '生成', data: data.generated || [], borderColor: '#667eea', backgroundColor: 'rgba(102,126,234,0.08)', fill: true, tension: 0.4, pointRadius: 3 },
                    { label: '发布', data: data.published || [], borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.08)', fill: true, tension: 0.4, pointRadius: 3 },
                ]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } },
                scales: { x: { ticks: { font: { size: 10 }, maxTicksLimit: 10 }, grid: { display: false } }, y: { beginAtZero: true, ticks: { stepSize: 1 } } }
            }
        });
    },
    async loadPlatform() {
        const data = await API.get('/api/analytics/platform-distribution');
        if (!data || data.error) { Toast.warning('平台数据加载失败'); return; }
        const ctx = document.getElementById('chart-platform');
        if (!ctx) return;
        if (typeof Chart === 'undefined') return;
        if (this.platformChart) this.platformChart.destroy();
        const colors = ['#667eea','#22c55e','#f59e0b','#ef4444','#3b82f6','#8b5cf6','#ec4899'];
        this.platformChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels || [],
                datasets: [{ data: data.values || [], backgroundColor: colors.slice(0, Math.max((data.labels||[]).length, 1)) }]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } }
            }
        });
    },
    async loadEngagement() {
        const data = await API.get('/api/analytics/engagement?range=7d');
        if (!data || data.error) return;
        const container = document.getElementById('engagement-stats');
        if (!container) return;
        const stats = [
            { label: '曝光量', value: this._fmt(data.impressions || 0), color: '#667eea' },
            { label: '点赞', value: this._fmt(data.likes || 0), color: '#22c55e' },
            { label: '评论', value: this._fmt(data.comments || 0), color: '#f59e0b' },
            { label: '转发', value: this._fmt(data.shares || 0), color: '#ef4444' },
        ];
        container.innerHTML = stats.map(s =>
            '<div style="text-align:center;padding:12px;background:rgba(' + this._hexRgb(s.color) + ',0.07);border-radius:8px">' +
            '<div style="font-size:20px;font-weight:700;color:' + s.color + '">' + s.value + '</div>' +
            '<div style="font-size:11px;color:var(--text-muted);margin-top:4px">' + s.label + '</div></div>'
        ).join('');
    },
    _fmt(n) {
        if (n >= 1000000) return (n/1000000).toFixed(1)+'M';
        if (n >= 1000) return (n/1000).toFixed(1)+'K';
        return String(n || 0);
    },
    _hexRgb(hex) {
        const r = parseInt(hex.slice(1,3),16);
        const g = parseInt(hex.slice(3,5),16);
        const b = parseInt(hex.slice(5,7),16);
        return r+','+g+','+b;
    }
}

### C. 移除 demo 数据
analytics 模块中原来的 demo 数据赋值（直接设置 textContent 为 '127' 等假数字）全部删除，改为通过 API 动态加载。

### D. 确认 analytics-range change 事件
找到 init() 中的 analytics-range change 事件，确认它调用了 this.modules.analytics.load()（已存在，无需修改）

### E. 语法检查
确认 app.js 中无语法错误（特别检查模块末尾逗号、括号匹配）。

返回 JSON：{"filesChanged": ["改动的文件列表"], "chartsImplemented": ["实现的图表类型"]}`,
  { phase: 'Frontend: R-01 Analytics BI', schema: { type: 'object', properties: { filesChanged: { type: 'array' }, chartsImplemented: { type: 'array' } }, required: ['filesChanged'] } }
)

// ─── Phase 4: Frontend Content Calendar ─────────────────────────────────────
phase('Frontend: R-02 Calendar')

const calendarFeResult = await agent(
  `在 /Users/zfl/projects/cn-social-agent 中实现 R-02 内容日历前端（月历视图 + 拖拽排期）。

## 目标：修改 src/admin/index.html 和 src/admin/app.js

### A. index.html 修改

在发布管理 page（id=page-publish）中，找到 tab-nav 区域，在现有 tab 按钮之后添加：
<button class="tab-btn" data-tab="calendar" onclick="App.modules.publish.switchTab('calendar')">发布日历</button>

在 id="publish-list" 的 div 之后添加日历容器：
<div id="calendar-container" style="display:none">
    <div id="calendar-nav" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <button class="btn btn-sm btn-secondary" onclick="App.modules.publish.calPrev()">&#8592; 上月</button>
        <h3 id="cal-title" style="margin:0;font-size:16px;font-weight:600"></h3>
        <div style="display:flex;gap:8px">
            <button class="btn btn-sm btn-secondary" onclick="App.modules.publish.calNext()">下月 &#8594;</button>
            <button class="btn btn-sm btn-primary" onclick="App.navigate('generate')">+ 新建内容</button>
        </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px" id="cal-grid"></div>
</div>

### B. app.js 修改

找到 publish 模块，在现有内容后添加 calendar 子模块：

在 publish 模块内添加：
calendar: {
    year: new Date().getFullYear(),
    month: new Date().getMonth() + 1,
    tasks: [],
    _dragId: null,
    async load() {
        const data = await API.get('/api/analytics/publish-calendar?year=' + this.year + '&month=' + this.month);
        this.tasks = data.items || [];
        this.render();
    },
    render() {
        const title = document.getElementById('cal-title');
        if (title) title.textContent = this.year + '年 ' + this.month + '月';
        const grid = document.getElementById('cal-grid');
        if (!grid) return;
        const firstDow = new Date(this.year, this.month-1, 1).getDay();
        const offset = firstDow === 0 ? 6 : firstDow - 1;
        const daysInMonth = new Date(this.year, this.month, 0).getDate();
        const weekDays = ['一','二','三','四','五','六','日'];
        const today = new Date().toISOString().slice(0,10);
        let html = weekDays.map(d => '<div style="text-align:center;font-size:11px;font-weight:600;color:var(--text-muted);padding:6px 0">'+d+'</div>').join('');
        for (let i=0; i<offset; i++) html += '<div></div>';
        for (let d=1; d<=daysInMonth; d++) {
            const ds = this.year + '-' + String(this.month).padStart(2,'0') + '-' + String(d).padStart(2,'0');
            const dayTasks = this.tasks.filter(t => t.date === ds);
            const isToday = ds === today;
            const bg = isToday ? 'rgba(102,126,234,0.06)' : 'var(--bg-secondary)';
            const border = isToday ? '2px solid #667eea' : '1px solid var(--border-color)';
            html += '<div style="background:'+bg+';border:'+border+';border-radius:8px;min-height:88px;padding:6px;cursor:pointer" ' +
                'ondragover="App.modules.publish.calDragOver(event)" ' +
                'ondrop="App.modules.publish.calDrop(event,\''+ds+'\')" ' +
                'data-date="'+ds+'" ' +
                'onclick="App.modules.publish.calShowDay(\''+ds+'\')">' +
                '<div style="font-size:12px;font-weight:600;margin-bottom:4px' + (isToday?';color:#667eea':'') + '">' + d + '</div>';
            dayTasks.slice(0,3).forEach(t => {
                const color = t.status === 'SUCCESS' ? '#22c55e' : t.status === 'FAILED' || t.status === 'FAILED' ? '#ef4444' : '#667eea';
                const picon = {weibo:'W',weixin:'微',xiaohongshu:'红',douyin:'抖',dingtalk:'钉',feishu:'飞'}[t.platform] || '·';
                html += '<div draggable="true" ' +
                    'ondragstart="App.modules.publish.calDragStart(event,\''+t.id+'\')" ' +
                    'style="background:rgba('+this._rgb(color)+',0.1);color:'+color+';border-radius:4px;padding:2px 5px;margin-bottom:2px;' +
                    'font-size:10px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;cursor:grab;user-select:none">' +
                    picon+' '+ (t.title||'任务').substring(0,10) + '</div>';
            });
            if (dayTasks.length > 3) html += '<div style="font-size:10px;color:var(--text-muted);text-align:center">+'+(dayTasks.length-3)+'</div>';
            html += '</div>';
        }
        grid.innerHTML = html;
    },
    calPrev() { if(--this.month<1){this.month=12;this.year--} this.load(); },
    calNext() { if(++this.month>12){this.month=1;this.year++} this.load(); },
    calDragStart(e, id) { this._dragId=id; e.dataTransfer.effectAllowed='move'; },
    calDragOver(e) { e.preventDefault(); e.dataTransfer.dropEffect='move'; },
    async calDrop(e, newDate) {
        e.preventDefault();
        if (!this._dragId) return;
        const task = this.tasks.find(t => t.id === this._dragId);
        if (!task) return;
        const runAt = newDate + 'T09:00:00';
        try {
            await API.request('/api/scheduler/tasks/' + this._dragId, {
                method: 'PUT', body: JSON.stringify({ run_at: runAt })
            });
            Toast.success('排期已更新至 ' + newDate);
            this.load();
        } catch(err) { Toast.error('更新失败'); }
    },
    calShowDay(ds) {
        const tasks = this.tasks.filter(t => t.date === ds);
        if (!tasks.length) return;
        const html = tasks.map(t =>
            '<div style="padding:8px;border-bottom:1px solid var(--border-color);font-size:13px">' +
            '<div style="font-weight:500">'+t.title+'</div>' +
            '<div style="font-size:11px;color:var(--text-muted);margin-top:2px">' +
            '状态：<span style="color:'+(t.status==='SUCCESS'?'#22c55e':'#ef4444')+'">'+t.status+'</span> | ' +
            '平台：'+t.platform+'</div></div>'
        ).join('');
        App.showModal(ds+' 任务', html, [{label:'关闭',class:'btn-secondary',onClick:'App.closeModal()'}]);
    },
    _rgb(hex) { return parseInt(hex.slice(1,3),16)+','+parseInt(hex.slice(3,5),16)+','+parseInt(hex.slice(5,7),16); },
},

### C. 修改 switchTab 支持 calendar tab

找到 publish.switchTab 方法，修改为：
async switchTab(tab) {
    this.currentTab = tab;
    document.querySelectorAll('#publish-tab-nav .tab-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.tab === tab)
    );
    document.getElementById('publish-list').style.display = tab === 'scheduled' || tab === 'published' || tab === 'failed' ? 'block' : 'none';
    document.getElementById('calendar-container').style.display = tab === 'calendar' ? 'block' : 'none';
    if (tab === 'calendar') {
        this.calendar.year = new Date().getFullYear();
        this.calendar.month = new Date().getMonth() + 1;
        await this.calendar.load();
    } else {
        await this.load();
    }
}

### D. 添加样式
在 styles.css 末尾添加：
#calendar-container .cal-day:hover { background: var(--bg-primary) !important; }
#calendar-container [draggable]:active { opacity: 0.6; cursor: grabbing; }

返回 JSON：{"filesChanged": ["改动的文件列表"], "featuresImplemented": ["功能列表"]}`,
  { phase: 'Frontend: R-02 Calendar', schema: { type: 'object', properties: { filesChanged: { type: 'array' }, featuresImplemented: { type: 'array' } }, required: ['filesChanged'] } }
)

// ─── Phase 5: Verify ────────────────────────────────────────────────────────
phase('Verify')

const verifyResult = await agent(
  `在 /Users/zfl/projects/cn-social-agent 中验证 Phase 1 所有改动。

执行以下所有检查：

## A. Python 语法检查
cd /Users/zfl/projects/cn-social-agent && python3 -m py_compile src/admin/web.py && echo "web.py OK" || echo "web.py SYNTAX ERROR"
python3 -m py_compile src/server.py && echo "server.py OK" || echo "server.py SYNTAX ERROR"
python3 -m py_compile src/scheduler/scheduler.py && echo "scheduler.py OK" || echo "scheduler.py SYNTAX ERROR"

## B. API 端点注册检查
grep -n "analytics/content-trend" src/admin/web.py && echo "trend OK"
grep -n "analytics/platform-distribution" src/admin/web.py && echo "platform OK"
grep -n "analytics/engagement" src/admin/web.py && echo "engagement OK"
grep -n "analytics/publish-calendar" src/admin/web.py && echo "calendar OK"
grep -n "notifications" src/admin/web.py && echo "notifications OK"
grep -n "/metrics" src/server.py && echo "metrics OK"

## C. 前端关键改动检查
grep -n "chart-trend" src/admin/index.html && echo "trend canvas OK"
grep -n "chart-platform" src/admin/index.html && echo "platform canvas OK"
grep -n "chart.js" src/admin/index.html && echo "Chart.js CDN OK"
grep -n "calendar-container" src/admin/index.html && echo "calendar container OK"
grep -n "data-tab=\"calendar\"" src/admin/index.html && echo "calendar tab OK"
grep -n "App.modules.publish.calDrop" src/admin/app.js && echo "calDrop OK"
grep -n "App.modules.analytics.loadTrend" src/admin/app.js && echo "analytics API calls OK"

## D. JS 语法快速检查
node --check src/admin/app.js 2>&1 || echo "JS syntax check done"

## 汇总
如果所有检查通过：issues=[]，allPassed=true
如果有问题：issues=[问题描述列表]，allPassed=false

返回 JSON：{"issues": [], "allPassed": true/false}`,
  { phase: 'Verify', schema: { type: 'object', properties: { issues: { type: 'array' }, allPassed: { type: 'boolean' } }, required: ['issues'] } }
)

// ─── Final Report ───────────────────────────────────────────────────────────
log('=== Phase 1 实施完成 ===')
log('T-05 (scheduler filter): files=' + JSON.stringify(t05Result.filesChanged || []))
log('T-04 (/metrics): files=' + JSON.stringify(t04Result.filesChanged || []))
log('Analytics Backend: endpoints=' + JSON.stringify(analyticsBeResult.endpointsAdded || []))
log('Analytics Frontend: charts=' + JSON.stringify(analyticsFeResult.chartsImplemented || []))
log('Calendar Frontend: features=' + JSON.stringify(calendarFeResult.featuresImplemented || []))
log('Verification: allPassed=' + verifyResult.allPassed + ', issues=' + verifyResult.issues.length)

return {
  techDebt: { t05: t05Result, t04: t04Result },
  analyticsBackend: analyticsBeResult,
  analyticsFrontend: analyticsFeResult,
  calendarFrontend: calendarFeResult,
  verification: verifyResult,
}
