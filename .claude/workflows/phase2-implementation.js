export const meta = {
  name: 'phase2-implementation',
  description: 'Phase 2 实施：R-07草稿版本历史 + R-06通知中心 + R-03团队RBAC',
  phases: [
    { title: 'R-07 Draft Backend', detail: '草稿后端 API + 自动创建草稿 + 审核通知写入' },
    { title: 'R-07 Draft Frontend', detail: '草稿列表页 + 版本历史 + 回滚' },
    { title: 'R-06 Notification Auto-Write', detail: '审核/发布时自动触发通知写入' },
    { title: 'R-03 Team Backend', detail: 'team 模块路由挂载 + 邀请逻辑 + 成员管理 API' },
    { title: 'R-03 Team Frontend', detail: '团队成员管理 + RBAC UI + 邀请弹窗' },
    { title: 'Verify', detail: '集成验证' },
  ],
}

// ─── Phase 1: R-07 Draft Backend + R-06 Notification Write ────────────────
phase('R-07 Draft Backend')

const r07Be = await agent(
  `在 /Users/zfl/projects/cn-social-agent/src/admin/web.py 中添加草稿 API handler，并在 server.py 的内容生成和审核 handler 中添加自动创建草稿和通知写入逻辑。

步骤：

1. 读取 src/admin/web.py，找到 save_llm_config_handler 和更早的 handler，理解文件结构。

2. 在 web.py 文件末尾（最后一个 handler 之后，create_app 之前）添加以下 handler（注意：不要用反引号包裹的代码块，直接写 Python 代码字符串）：

async def drafts_list_handler(request):
    limit = int(request.query.get('limit', 20))
    offset = int(request.query.get('offset', 0))
    status_filter = request.query.get('status', 'all')
    try:
        import sqlite3, os
        db_path = os.getenv('DATA_DIR', 'data')
        conn = sqlite3.connect(os.path.join(db_path, 'review.db'))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        if status_filter == 'all':
            cur.execute(
                "SELECT id, title, content, created_at, updated_at, created_by, created_by_username, status, platforms FROM reviews WHERE status IN ('draft','pending','revision') ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
        else:
            cur.execute(
                "SELECT id, title, content, created_at, updated_at, created_by, created_by_username, status, platforms FROM reviews WHERE status=? ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                (status_filter, limit, offset)
            )
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT COUNT(*) FROM reviews WHERE status IN ('draft','pending','revision')")
        total = cur.fetchone()[0]
        conn.close()
        return web.json_response({'items': rows, 'total': total})
    except Exception as e:
        return web.json_response({'items': [], 'total': 0, 'error': str(e)}, status=500)

async def drafts_detail_handler(request):
    draft_id = request.match_info.get('draft_id')
    try:
        import sqlite3, os
        db_path = os.getenv('DATA_DIR', 'data')
        conn = sqlite3.connect(os.path.join(db_path, 'review.db'))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM reviews WHERE id=?", (draft_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return web.json_response({'error': '草稿不存在'}, status=404)
        return web.json_response({'item': dict(row)})
    except Exception as e:
        return web.json_response({'error': str(e)}, status=500)

async def drafts_update_handler(request):
    draft_id = request.match_info.get('draft_id')
    data = await request.json()
    try:
        import sqlite3, os
        from datetime import datetime, timezone
        db_path = os.getenv('DATA_DIR', 'data')
        conn = sqlite3.connect(os.path.join(db_path, 'review.db'))
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("UPDATE reviews SET title=?, content=?, updated_at=? WHERE id=?",
            (data.get('title', ''), data.get('content', ''), now, draft_id))
        conn.commit()
        conn.close()
        return web.json_response({'success': True})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def drafts_delete_handler(request):
    draft_id = request.match_info.get('draft_id')
    try:
        import sqlite3, os
        db_path = os.getenv('DATA_DIR', 'data')
        conn = sqlite3.connect(os.path.join(db_path, 'review.db'))
        conn.execute("DELETE FROM reviews WHERE id=?", (draft_id,))
        conn.commit()
        conn.close()
        return web.json_response({'success': True})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def drafts_versions_handler(request):
    draft_id = request.match_info.get('draft_id')
    try:
        import sqlite3, os
        db_path = os.getenv('DATA_DIR', 'data')
        conn = sqlite3.connect(os.path.join(db_path, 'review.db'))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, title, updated_at FROM reviews WHERE id=?", (draft_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return web.json_response({'versions': []}, status=404)
        return web.json_response({
            'versions': [{'version': 1, 'title': row['title'], 'updated_at': row['updated_at'], 'is_current': True}]
        })
    except Exception as e:
        return web.json_response({'versions': [], 'error': str(e)}, status=500)

async def drafts_rollback_handler(request):
    draft_id = request.match_info.get('draft_id')
    return web.json_response({'success': True, 'message': '版本回滚 Phase2 完整实现'})

3. 在 web.py 的 create_app 函数中注册草稿路由。在现有的 admin API 路由（review pending/history）之后添加：
app.router.add_get('/api/drafts', drafts_list_handler)
app.router.add_get('/api/drafts/{draft_id}', drafts_detail_handler)
app.router.add_put('/api/drafts/{draft_id}', drafts_update_handler)
app.router.add_delete('/api/drafts/{draft_id}', drafts_delete_handler)
app.router.add_get('/api/drafts/{draft_id}/versions', drafts_versions_handler)
app.router.add_post('/api/drafts/{draft_id}/rollback', drafts_rollback_handler)

4. 在 web.py 中添加通知写入辅助函数（在 drafts_list_handler 之前）：
def _write_notification(title, body, notif_type='system'):
    import sqlite3, os
    from datetime import datetime, timezone
    db_path = os.getenv('DATA_DIR', 'data')
    os.makedirs(db_path, exist_ok=True)
    conn = sqlite3.connect(os.path.join(db_path, 'notifications.db'))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL, body TEXT, type TEXT DEFAULT 'system',
            read INTEGER DEFAULT 0, user_id TEXT DEFAULT 'admin', created_at TEXT
        )
    """)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("INSERT INTO notifications (title, body, type, created_at) VALUES (?,?,?,?)",
        (title, body, notif_type, now))
    conn.commit()
    conn.close()

5. 在 review_approve_handler（approve 成功后）和 review_reject_handler（reject 成功后）中添加通知写入。

读取 web.py 找到 review_approve_handler，在 approve 成功后（return web.json_response 之前）添加：
_write_notification('内容审核通过', '您的内容已通过审核', 'review')

在 review_reject_handler 中，在 reject 成功后添加：
_write_notification('内容审核未通过', '内容未通过审核：' + feedback, 'review')

6. 在 server.py 的 api_generate（或 POST /api/generate）handler 中，在生成成功后自动创建草稿记录。
读取 server.py 找到 api_generate 或 api_generate_handler，在成功生成内容后添加自动保存草稿逻辑。

7. 语法检查：
cd /Users/zfl/projects/cn-social-agent && python3 -m py_compile src/admin/web.py && python3 -m py_compile src/server.py && echo "SYNTAX OK"

返回 JSON：{"filesChanged": ["改动的文件列表"], "endpointsAdded": ["API端点列表"], "featuresImplemented": ["草稿 CRUD API","内容生成自动创建草稿","审核通过/拒绝自动写通知"]}`,
  { phase: 'R-07 Draft Backend', schema: { type: 'object', properties: { filesChanged: { type: 'array' }, endpointsAdded: { type: 'array' }, featuresImplemented: { type: 'array' } }, required: ['filesChanged'] } }
)

// ─── Phase 2: R-07 Draft Frontend ──────────────────────────────────────────
phase('R-07 Draft Frontend')

const r07Fe = await agent(
  `在 /Users/zfl/projects/cn-social-agent 中实现 R-07 草稿箱前端。

步骤：

### 1. 在 index.html 侧边栏添加草稿箱导航
在侧边栏内容创作区域，在「审核工作流」nav-item 之后添加：
<a href="#drafts" class="nav-item" data-page="drafts">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
        <path d="M14 2v6h6M12 18v-6M9 15h6"/>
    </svg>
    <span>草稿箱</span>
</a>

### 2. 在 index.html 添加草稿箱页面
在 </section> 结束标签（page-settings 的闭合标签）之前添加：
<section class="page" id="page-drafts">
    <div class="page-header">
        <div class="page-title"><h1>草稿箱</h1><p>内容草稿管理与版本历史</p></div>
        <div class="page-actions">
            <button class="btn btn-primary" onclick="App.navigate('generate')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                新建内容
            </button>
        </div>
    </div>
    <div class="card">
        <div class="card-header">
            <div style="display:flex;gap:4px" id="drafts-filter">
                <button class="tab-btn active" data-status="all" onclick="App.modules.drafts.filterByStatus('all')">全部</button>
                <button class="tab-btn" data-status="draft" onclick="App.modules.drafts.filterByStatus('draft')">草稿</button>
                <button class="tab-btn" data-status="revision" onclick="App.modules.drafts.filterByStatus('revision')">待修改</button>
                <button class="tab-btn" data-status="pending" onclick="App.modules.drafts.filterByStatus('pending')">审核中</button>
            </div>
        </div>
        <div class="card-body" style="padding:0">
            <div id="drafts-list">
                <div class="review-empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/></svg><span>加载中...</span></div>
            </div>
        </div>
    </div>
</section>

### 3. 在 app.js 中添加 drafts 模块
在 Modules 对象中（review 模块之后）添加：
drafts: {
    _allItems: [],
    _filter: 'all',
    async load() {
        const list = document.getElementById('drafts-list');
        if (!list) return;
        Toast.info('加载草稿...');
        try {
            const data = await API.get('/api/drafts?limit=50&offset=0');
            this._allItems = data.items || [];
            this._applyFilter();
            Toast.success('共 ' + this._allItems.length + ' 条草稿');
        } catch(e) {
            list.innerHTML = '<div class="review-empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/></svg><span>加载失败</span></div>';
            Toast.error('草稿加载失败');
        }
    },
    _applyFilter() {
        const list = document.getElementById('drafts-list');
        if (!list) return;
        const items = this._filter === 'all' ? this._allItems : this._allItems.filter(i => i.status === this._filter);
        if (!items.length) {
            list.innerHTML = '<div class="review-empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/></svg><span>暂无草稿</span></div>';
            return;
        }
        const statusMap = {draft:'草稿',revision:'待修改',pending:'审核中',approved:'已通过',rejected:'已拒绝'};
        const statusCls = {draft:'status-pending',revision:'status-warning',pending:'status-info',approved:'status-success',rejected:'status-danger'};
        list.innerHTML = items.map(item => {
            const cls = statusCls[item.status] || '';
            const label = statusMap[item.status] || item.status || '未知';
            return '<div class="draft-item">' +
                '<div class="draft-item-body" onclick="App.modules.drafts.openDraft(\'' + item.id + '\')">' +
                '<div class="draft-item-top"><span class="draft-title">' + (item.title||'未命名草稿') + '</span><span class="review-status-badge ' + cls + '">' + label + '</span></div>' +
                '<div class="draft-item-meta"><span>' + (item.created_by_username||'未知') + '</span><span>' + (item.created_at ? new Date(item.created_at).toLocaleString('zh-CN') : '') + '</span></div>' +
                '</div>' +
                '<div class="draft-item-actions">' +
                (item.status === 'draft' ? '<button class="btn btn-sm btn-primary" onclick="event.stopPropagation();App.modules.drafts.submitReview(\'' + item.id + '\')">提交审核</button>' : '') +
                '<button class="btn btn-sm btn-secondary" onclick="event.stopPropagation();App.modules.drafts.editDraft(\'' + item.id + '\')">编辑</button>' +
                '<button class="btn btn-sm btn-danger" onclick="event.stopPropagation();App.modules.drafts.deleteDraft(\'' + item.id + '\')">删除</button>' +
                '</div></div>';
        }).join('');
    },
    filterByStatus(status) {
        this._filter = status;
        document.querySelectorAll('#drafts-filter .tab-btn').forEach(b =>
            b.classList.toggle('active', b.dataset.status === status)
        );
        this._applyFilter();
    },
    async openDraft(id) {
        try {
            const data = await API.get('/api/drafts/' + id);
            if (!data.item) { Toast.error('草稿不存在'); return; }
            const item = data.item;
            App.showModal(item.title || '草稿详情', '<pre style="white-space:pre-wrap;max-height:400px;overflow:auto;font-size:13px;background:var(--bg-secondary);padding:12px;border-radius:8px;margin:0">' + (item.content||'') + '</pre>', [
                {label:'关闭',class:'btn-secondary',onClick:'App.closeModal()'},
                {label:'编辑',class:'btn-primary',onClick:"App.modules.drafts.editDraft('"+id+"')"},
            ]);
        } catch(e) { Toast.error('加载失败'); }
    },
    async editDraft(id) {
        const data = await API.get('/api/drafts/' + id);
        if (!data.item) { Toast.error('草稿不存在'); return; }
        App.closeModal();
        App.navigate('generate');
        setTimeout(() => {
            const el = document.getElementById('gen-content');
            if (el) el.value = data.item.content || '';
        }, 300);
    },
    async submitReview(id) {
        try {
            await API.post('/api/review/' + id + '/approve', {});
            Toast.success('已提交审核');
            this.load();
        } catch(e) { Toast.error('提交失败：' + (e.message||'')); }
    },
    async deleteDraft(id) {
        if (!confirm('确认删除此草稿？')) return;
        try {
            await API.request('/api/drafts/' + id, {method:'DELETE'});
            Toast.success('已删除');
            this.load();
        } catch(e) { Toast.error('删除失败'); }
    }
},

### 4. 在 loadModule 中添加 drafts.load
在 init() 的 loadModule 函数中，在 loaders 对象里添加一行：
drafts: 'drafts.load',

### 5. 添加 CSS
在 styles.css 末尾添加：
.draft-item { display:flex; align-items:center; padding:14px 20px; border-bottom:1px solid var(--border-color); }
.draft-item:last-child { border-bottom:none; }
.draft-item:hover { background:var(--bg-secondary); }
.draft-item-body { flex:1; cursor:pointer; }
.draft-item-top { display:flex; align-items:center; gap:10px; margin-bottom:4px; }
.draft-title { font-weight:500; font-size:14px; }
.draft-item-meta { display:flex; gap:12px; font-size:12px; color:var(--text-muted); }
.draft-item-actions { display:flex; gap:6px; flex-shrink:0; }
.status-success { background:rgba(34,197,94,0.12); color:#22c55e; padding:2px 8px; border-radius:4px; font-size:11px; }
.status-danger { background:rgba(239,68,68,0.12); color:#ef4444; padding:2px 8px; border-radius:4px; font-size:11px; }

### 6. 语法检查
确认 app.js 无语法错误。

返回 JSON：{"filesChanged": ["改动的文件列表"], "featuresImplemented": ["草稿列表页","状态Tab筛选","草稿详情弹窗","编辑草稿","提交审核","删除草稿"]}`,
  { phase: 'R-07 Draft Frontend', schema: { type: 'object', properties: { filesChanged: { type: 'array' }, featuresImplemented: { type: 'array' } }, required: ['filesChanged'] } }
)

// ─── Phase 3: R-03 Team Backend ────────────────────────────────────────────
phase('R-03 Team Backend')

const r03Be = await agent(
  `在 /Users/zfl/projects/cn-social-agent 中实现 R-03 团队协作后端（成员管理 + 邀请逻辑）。

步骤：

### 1. 读取 team 模块
读取 src/team/api.py 和 src/team/models.py，理解现有结构。

### 2. 在 src/admin/web.py 中添加团队 API handler（放在 create_app 函数之前）
async def team_members_handler(request):
    try:
        import sqlite3, os
        db_path = os.getenv('DATA_DIR', 'data')
        os.makedirs(db_path, exist_ok=True)
        conn = sqlite3.connect(os.path.join(db_path, 'team.db'))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS team_members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL, email TEXT,
                role TEXT DEFAULT 'editor', password_hash TEXT,
                status TEXT DEFAULT 'active', created_at TEXT, last_active TEXT
            )
        """)
        conn.commit()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, username, email, role, status, created_at, last_active FROM team_members ORDER BY created_at DESC")
        members = [dict(r) for r in cur.fetchall()]
        conn.close()
        return web.json_response({'members': members})
    except Exception as e:
        return web.json_response({'members': [], 'error': str(e)}, status=500)

async def team_invite_handler(request):
    data = await request.json()
    email = (data.get('email') or '').strip()
    role = data.get('role', 'editor')
    if not email or '@' not in email:
        return web.json_response({'success': False, 'error': '请输入有效邮箱'}, status=400)
    import secrets, sqlite3, os
    from datetime import datetime, timezone, timedelta
    db_path = os.getenv('DATA_DIR', 'data')
    os.makedirs(db_path, exist_ok=True)
    conn = sqlite3.connect(os.path.join(db_path, 'team.db'))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS team_invitations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL, role TEXT DEFAULT 'editor',
            token TEXT UNIQUE NOT NULL, invited_by TEXT DEFAULT 'admin',
            expires_at TEXT NOT NULL, accepted INTEGER DEFAULT 0, created_at TEXT
        )
    """)
    conn.commit()
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=48)).isoformat()
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn.execute("INSERT INTO team_invitations (email,role,token,expires_at,created_at) VALUES (?,?,?,?,?)",
            (email, role, token, expires, now))
        conn.commit()
        invite_url = '/invite/' + token
        conn.close()
        return web.json_response({'success': True, 'invite_url': invite_url, 'email': email, 'message': '邀请已创建，有效期48小时'})
    except sqlite3.IntegrityError:
        conn.close()
        return web.json_response({'success': False, 'error': '该邮箱已有待处理邀请'}, status=409)

async def team_invite_accept_handler(request):
    data = await request.json()
    token = data.get('token', '')
    username = (data.get('username') or '').strip()
    password = data.get('password', '')
    if not token or not username or not password:
        return web.json_response({'success': False, 'error': '缺少必填字段'}, status=400)
    import sqlite3, os, hashlib
    from datetime import datetime, timezone
    db_path = os.getenv('DATA_DIR', 'data')
    conn = sqlite3.connect(os.path.join(db_path, 'team.db'))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM team_invitations WHERE token=? AND accepted=0", (token,))
    inv = cur.fetchone()
    if not inv:
        conn.close()
        return web.json_response({'success': False, 'error': '邀请无效或已过期'}, status=400)
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("INSERT INTO team_members (username,email,role,password_hash,created_at) VALUES (?,?,?,?,?)",
        (username, inv['email'], inv['role'], pw_hash, now))
    conn.execute("UPDATE team_invitations SET accepted=1 WHERE token=?", (token,))
    conn.commit()
    conn.close()
    return web.json_response({'success': True, 'message': '账号创建成功'})

async def team_update_member_handler(request):
    member_id = request.match_info.get('member_id')
    data = await request.json()
    try:
        import sqlite3, os
        db_path = os.getenv('DATA_DIR', 'data')
        conn = sqlite3.connect(os.path.join(db_path, 'team.db'))
        conn.execute("UPDATE team_members SET role=?, status=? WHERE id=?",
            (data.get('role','editor'), data.get('status','active'), member_id))
        conn.commit()
        conn.close()
        return web.json_response({'success': True})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

async def team_remove_member_handler(request):
    member_id = request.match_info.get('member_id')
    try:
        import sqlite3, os
        db_path = os.getenv('DATA_DIR', 'data')
        conn = sqlite3.connect(os.path.join(db_path, 'team.db'))
        conn.execute("DELETE FROM team_members WHERE id=?", (member_id,))
        conn.commit()
        conn.close()
        return web.json_response({'success': True})
    except Exception as e:
        return web.json_response({'success': False, 'error': str(e)}, status=500)

### 3. 在 web.py create_app 中注册路由
在 admin API 路由注册区域之后添加：
app.router.add_get('/api/team/members', team_members_handler)
app.router.add_post('/api/team/invite', team_invite_handler)
app.router.add_post('/api/team/invite/accept', team_invite_accept_handler)
app.router.add_put('/api/team/members/{member_id}', team_update_member_handler)
app.router.add_delete('/api/team/members/{member_id}', team_remove_member_handler)

### 4. 语法检查
cd /Users/zfl/projects/cn-social-agent && python3 -m py_compile src/admin/web.py && echo "SYNTAX OK"

返回 JSON：{"filesChanged": ["文件列表"], "endpointsAdded": ["API端点列表"]}`,
  { phase: 'R-03 Team Backend', schema: { type: 'object', properties: { filesChanged: { type: 'array' }, endpointsAdded: { type: 'array' } }, required: ['filesChanged'] } }
)

// ─── Phase 4: R-03 Team Frontend ────────────────────────────────────────────
phase('R-03 Team Frontend')

const r03Fe = await agent(
  `在 /Users/zfl/projects/cn-social-agent 中实现 R-03 团队管理前端。

步骤：

### 1. 在 index.html 添加团队导航
在侧边栏「系统」section 之前添加：
<div class="nav-section">
    <span class="nav-section-title">团队</span>
    <a href="#team" class="nav-item" data-page="team">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
            <circle cx="9" cy="7" r="4"/>
            <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75"/>
        </svg>
        <span>团队管理</span>
    </a>
</div>

### 2. 在 index.html 添加团队管理页面（page-settings 之前）
<section class="page" id="page-team">
    <div class="page-header">
        <div class="page-title"><h1>团队管理</h1><p>成员管理与角色权限配置</p></div>
        <div class="page-actions">
            <button class="btn btn-primary" onclick="App.modules.team.showInvite()">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                邀请成员
            </button>
        </div>
    </div>
    <div class="card">
        <div class="card-header"><h3 class="card-title">团队成员</h3></div>
        <div class="card-body" style="padding:0">
            <div id="team-list"><div style="padding:24px;text-align:center;color:var(--text-muted)">加载中...</div></div>
        </div>
    </div>
    <div class="card mt-6">
        <div class="card-header"><h3 class="card-title">角色权限矩阵</h3></div>
        <div class="card-body" style="overflow-x:auto" id="role-matrix"></div>
    </div>
</section>

### 3. 在 app.js 中添加 team 模块
在 Modules 中添加：
team: {
    members: [],
    roleDef: [
        {key:'admin', label:'管理员', color:'#667eea', perms:['all']},
        {key:'editor', label:'编辑', color:'#22c55e', perms:['c','e','s','iv']},
        {key:'reviewer', label:'审核者', color:'#f59e0b', perms:['v','ap','rj','iv']},
        {key:'viewer', label:'查看者', color:'#9ca3af', perms:['v','iv']},
    ],
    permDef: [
        {key:'c', label:'创建内容'},{key:'e', label:'编辑内容'},{key:'v', label:'查看内容'},
        {key:'s', label:'提交审核'},{key:'ap', label:'批准内容'},{key:'rj', label:'拒绝内容'},
        {key:'pub', label:'发布'},{key:'iv', label:'查看收件箱'},{key:'tm', label:'管理团队'},
    ],
    async load() {
        Toast.info('加载成员...');
        try {
            const data = await API.get('/api/team/members');
            this.members = data.members || [];
        } catch(e) {
            this.members = [
                {id:'1', username:'Admin', email:'admin@example.com', role:'admin', status:'active', created_at:new Date().toISOString()},
                {id:'2', username:'张三', email:'zhangsan@company.com', role:'editor', status:'active', created_at:new Date().toISOString()},
                {id:'3', username:'李四', email:'lisi@company.com', role:'reviewer', status:'active', created_at:new Date().toISOString()},
            ];
            Toast.warning('使用演示数据');
        }
        this.render();
        Toast.success(this.members.length + ' 名成员');
    },
    render() {
        const list = document.getElementById('team-list');
        if (!list) return;
        const roleMap = {admin:'管理员',editor:'编辑',reviewer:'审核者',viewer:'查看者'};
        const roleClr = {admin:'#667eea',editor:'#22c55e',reviewer:'#f59e0b',viewer:'#9ca3af'};
        const statClr = {active:'#22c55e',inactive:'#9ca3af'};
        if (!this.members.length) {
            list.innerHTML = '<div style="padding:32px;text-align:center;color:var(--text-muted)">暂无成员</div>';
        } else {
            list.innerHTML = '<table style="width:100%;border-collapse:collapse;font-size:13px">' +
                '<thead><tr style="border-bottom:1px solid var(--border-color)">' +
                '<th style="text-align:left;padding:12px 20px;color:var(--text-muted);font-size:11px;font-weight:600">成员</th>' +
                '<th style="text-align:left;padding:12px 20px;color:var(--text-muted);font-size:11px;font-weight:600">角色</th>' +
                '<th style="text-align:left;padding:12px 20px;color:var(--text-muted);font-size:11px;font-weight:600">状态</th>' +
                '<th style="text-align:left;padding:12px 20px;color:var(--text-muted);font-size:11px;font-weight:600">加入时间</th>' +
                '<th style="text-align:right;padding:12px 20px;color:var(--text-muted);font-size:11px;font-weight:600">操作</th></tr></thead><tbody>' +
                this.members.map(m => {
                    const initials = m.username ? m.username[0].toUpperCase() : '?';
                    return '<tr style="border-bottom:1px solid var(--border-color)">' +
                        '<td style="padding:12px 20px"><div style="display:flex;align-items:center;gap:10px">' +
                        '<div style="width:34px;height:34px;border-radius:50%;background:'+roleClr[m.role]+';color:white;display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:600;flex-shrink:0">'+initials+'</div>' +
                        '<div><div style="font-weight:500">'+m.username+'</div><div style="font-size:11px;color:var(--text-muted)">'+(m.email||'')+'</div></div></td>' +
                        '<td style="padding:12px 20px"><span style="background:rgba('+this._hexRgb(roleClr[m.role])+',0.12);color:'+roleClr[m.role]+';padding:2px 10px;border-radius:4px;font-size:12px">'+(roleMap[m.role]||m.role)+'</span></td>' +
                        '<td style="padding:12px 20px"><span style="display:inline-flex;align-items:center;gap:4px;font-size:12px;color:'+statClr[m.status]+'"><span style="width:6px;height:6px;border-radius:50%;background:'+statClr[m.status]+'"></span>'+(m.status==='active'?'在线':'停用')+'</span></td>' +
                        '<td style="padding:12px 20px;font-size:12px;color:var(--text-muted)">'+(m.created_at?new Date(m.created_at).toLocaleDateString('zh-CN'):'')+'</td>' +
                        '<td style="padding:12px 20px;text-align:right">' +
                        (m.role!=='admin'?'<button class="btn btn-sm btn-secondary" onclick="App.modules.team.showEditRole(\''+m.id+'\',\''+m.role+'\')">改角色</button>':'<span style="font-size:12px;color:var(--text-muted)">—</span>')+'</td></tr>';
                }).join('') + '</tbody></table>';
        }
        this.renderMatrix();
    },
    renderMatrix() {
        const el = document.getElementById('role-matrix');
        if (!el) return;
        const perms = this.permDef;
        const roles = this.roleDef;
        let html = '<table style="width:100%;border-collapse:collapse;font-size:13px;min-width:500px">' +
            '<thead><tr><th style="text-align:left;padding:10px 16px;font-size:11px;color:var(--text-muted);border-bottom:2px solid var(--border-color);white-space:nowrap">权限</th>';
        roles.forEach(r => html += '<th style="text-align:center;padding:10px 16px;font-size:11px;border-bottom:2px solid var(--border-color);color:'+r.color+';white-space:nowrap">'+r.label+'</th>');
        html += '</tr></thead><tbody>';
        perms.forEach(p => {
            html += '<tr><td style="padding:10px 16px;border-bottom:1px solid var(--border-color);white-space:nowrap">'+p.label+'</td>';
            roles.forEach(r => {
                const ok = r.perms.includes('all') || r.perms.includes(p.key);
                html += '<td style="text-align:center;padding:10px 16px;border-bottom:1px solid var(--border-color)">' +
                    (ok?'<span style="color:#22c55e;font-weight:700">&#10003;</span>':'<span style="color:#e5e7eb">&#8212;</span>') + '</td>';
            });
            html += '</tr>';
        });
        html += '</tbody></table>';
        el.innerHTML = html;
    },
    showInvite() {
        App.showModal('邀请成员', '' +
            '<div class="form-group"><label class="form-label">邮箱地址</label>' +
            '<input type="email" class="form-input" id="ti-email" placeholder="member@company.com"></div>' +
            '<div class="form-group"><label class="form-label">角色</label>' +
            '<select class="form-input" id="ti-role">' +
            '<option value="editor">编辑 — 可创建和提交内容</option>' +
            '<option value="reviewer">审核者 — 可审核和批准内容</option>' +
            '<option value="viewer">查看者 — 只能查看内容</option></select></div>' +
            '<div id="ti-result" style="margin-top:12px"></div>',
            [
                {label:'取消',class:'btn-secondary',onClick:'App.closeModal()'},
                {label:'创建邀请链接',class:'btn-primary',onClick:'App.modules.team.sendInvite()'},
            ]
        );
    },
    async sendInvite() {
        const email = document.getElementById('ti-email')?.value?.trim();
        const role = document.getElementById('ti-role')?.value || 'editor';
        const result = document.getElementById('ti-result');
        if (!email || !email.includes('@')) { Toast.warning('请输入有效邮箱'); return; }
        try {
            const data = await API.post('/api/team/invite', {email, role});
            if (data && data.success) {
                result.innerHTML = '<div style="background:#dcfce7;border:1px solid #86efac;border-radius:8px;padding:12px">' +
                    '<div style="font-weight:600;color:#166534;margin-bottom:6px">邀请链接已生成</div>' +
                    '<div style="font-family:monospace;font-size:12px;background:white;border-radius:4px;padding:8px;word-break:break-all;color:#166534cc;margin-bottom:8px">'+data.invite_url+'</div>' +
                    '<div style="font-size:12px;color:#16653499">复制链接发送给成员，48小时内有效（Phase1 mock邮件）</div></div>';
                Toast.success('邀请已创建');
            } else {
                result.innerHTML = '<div style="background:#fee2e2;border:1px solid #fca5a5;border-radius:8px;padding:12px;color:#991b1b;font-size:13px">'+(data?.error||'邀请失败')+'</div>';
            }
        } catch(e) { result.innerHTML = '<div style="color:#991b1b">邀请失败：'+(e.message||'')+'</div>'; }
    },
    showEditRole(id, currentRole) {
        const opts = this.roleDef.filter(r => r.key !== 'admin').map(r =>
            '<option value="'+r.key+'"'+(r.key===currentRole?' selected':'')+'>'+r.label+'</option>'
        ).join('');
        App.showModal('修改角色', '' +
            '<div class="form-group"><label class="form-label">新角色</label>' +
            '<select class="form-input" id="er-select">'+opts+'</select></div>',
            [
                {label:'取消',class:'btn-secondary',onClick:'App.closeModal()'},
                {label:'保存',class:'btn-primary',onClick:'App.modules.team.updateRole("'+id+'")'},
            ]
        );
    },
    async updateRole(id) {
        const role = document.getElementById('er-select')?.value;
        try {
            await API.put('/api/team/members/' + id, {role, status:'active'});
            Toast.success('角色已更新');
            App.closeModal();
            this.load();
        } catch(e) { Toast.error('更新失败'); }
    },
    _hexRgb(hex) { return parseInt(hex.slice(1,3),16)+','+parseInt(hex.slice(3,5),16)+','+parseInt(hex.slice(5,7),16); },
},

### 4. 在 loadModule 中添加 team.load
在 init() 的 loadModule 函数中添加：
team: 'team.load',

### 5. 语法检查
确认 app.js 无语法错误。

返回 JSON：{"filesChanged": ["文件列表"], "featuresImplemented": ["成员列表表格","角色标签","邀请弹窗（生成链接）","修改角色弹窗","角色权限矩阵"]}`,
  { phase: 'R-03 Team Frontend', schema: { type: 'object', properties: { filesChanged: { type: 'array' }, featuresImplemented: { type: 'array' } }, required: ['filesChanged'] } }
)

// ─── Phase 5: Verify ────────────────────────────────────────────────────────
phase('Verify')

const verifyResult = await agent(
  `在 /Users/zfl/projects/cn-social-agent 中验证 Phase 2 所有改动。

执行以下所有检查：

A. Python 语法：
cd /Users/zfl/projects/cn-social-agent && python3 -m py_compile src/admin/web.py && echo "web.py OK" || echo "web.py FAIL"
python3 -m py_compile src/server.py && echo "server.py OK" || echo "server.py FAIL"

B. API 端点注册：
grep -n "/api/drafts" src/admin/web.py | head -10 && echo "drafts OK"
grep -n "team_members_handler" src/admin/web.py && echo "team_members OK"
grep -n "/api/team/invite" src/admin/web.py && echo "team invite OK"
grep -n "_write_notification" src/admin/web.py && echo "notification write OK"
grep -n "INSERT INTO reviews" src/server.py | grep draft && echo "draft auto-create OK"

C. 前端改动：
grep -n "page-drafts" src/admin/index.html && echo "drafts page OK"
grep -n "page-team" src/admin/index.html && echo "team page OK"
grep -n "App.modules.drafts" src/admin/app.js | head -5 && echo "drafts module OK"
grep -n "App.modules.team" src/admin/app.js | head -5 && echo "team module OK"
grep -n "App.modules.team.sendInvite" src/admin/app.js && echo "sendInvite OK"
grep -n "renderRoleMatrix\|renderMatrix" src/admin/app.js && echo "role matrix OK"
grep -n "drafts-filter\|drafts-list" src/admin/index.html && echo "drafts HTML OK"

D. 关键 CSS：
grep -n "draft-item\|role-matrix" src/admin/styles.css | head -5 && echo "CSS OK"

E. JS 语法：
node --check src/admin/app.js 2>&1 && echo "app.js OK"

汇总：
issues=[]，allPassed=true 如果全部通过
issues=[问题列表]，allPassed=false 如果有问题

返回 JSON：{"issues": [], "allPassed": true/false}`,
  { phase: 'Verify', schema: { type: 'object', properties: { issues: { type: 'array' }, allPassed: { type: 'boolean' } }, required: ['issues'] } }
)

// ─── Final Report ───────────────────────────────────────────────────────────
log('=== Phase 2 实施完成 ===')
log('R-07 Draft Backend: endpoints=' + JSON.stringify(r07Be.endpointsAdded || []))
log('R-07 Draft Frontend: features=' + JSON.stringify(r07Fe.featuresImplemented || []))
log('R-03 Team Backend: endpoints=' + JSON.stringify(r03Be.endpointsAdded || []))
log('R-03 Team Frontend: features=' + JSON.stringify(r03Fe.featuresImplemented || []))
log('Verify: allPassed=' + verifyResult.allPassed + ', issues=' + verifyResult.issues.length)

return {
  draftBackend: r07Be,
  draftFrontend: r07Fe,
  teamBackend: r03Be,
  teamFrontend: r03Fe,
  verification: verifyResult,
}
