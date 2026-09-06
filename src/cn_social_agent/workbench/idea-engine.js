(() => {
  const esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[c]);

  const safeUrl = (u) => {
    const s = String(u || "").trim();
    return /^https?:\/\//i.test(s) ? esc(s) : "#";
  };

  class IdeaEnginePanel {
    constructor(container) {
      this.container = container;
      this.materials = [];
      this.cards = [];
      this.fragments = [];
      this.library = [];
      this.connectorStatus = [];
      this.currentTab = "materials";
      this.loading = false;
      this.init();
    }

    init() {
      this.render();
      this.wireEvents();
      this.loadMaterials();
      this.loadConnectorStatus();
    }

    async api(path, options = {}) {
      const token = localStorage.getItem("wb_token") || "";
      const resp = await fetch(path, {
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        ...options,
      });
      if (!resp.ok) throw new Error(`API error: ${resp.status}`);
      return resp.json();
    }

    notify(msg) {
      const el = this.container.querySelector(".idea-notify");
      if (!el) return;
      el.textContent = msg;
      el.style.display = "";
      clearTimeout(this._notifyTimer);
      this._notifyTimer = setTimeout(() => {
        el.style.display = "none";
      }, 3000);
    }

    async loadConnectorStatus() {
      this.loading = true;
      this.updateLoading();
      try {
        const [typesData, statusData] = await Promise.all([
          this.api("/api/idea/connectors/types"),
          this.api("/api/idea/connectors"),
        ]);

        const types = typesData.types || [];
        const status = statusData.connectors || [];

        this.connectorStatus = types.map((t) => {
          const s = status.find((st) => st.connector_id === t.id);
          return {
            connector_id: t.id,
            name: t.name,
            description: t.description,
            icon: t.icon,
            status: s ? s.status : "ready",
            enabled: s ? s.enabled : true,
            last_sync_at: s ? s.last_sync_at : null,
            sync_count: s ? s.sync_count : 0,
          };
        });

        this.renderConnectors();
      } catch (e) {
        console.error("Failed to load connector status:", e);
      } finally {
        this.loading = false;
        this.updateLoading();
      }
    }

    async loadMaterials() {
      this.loading = true;
      this.updateLoading();
      try {
        const data = await this.api("/api/idea/materials");
        this.materials = data.items || [];
        this.renderMaterials();
      } catch (e) {
        console.error("Failed to load materials:", e);
      } finally {
        this.loading = false;
        this.updateLoading();
      }
    }

    async loadCards() {
      this.loading = true;
      this.updateLoading();
      try {
        const data = await this.api("/api/idea/cards");
        this.cards = data.items || [];
        this.renderCards();
      } catch (e) {
        console.error("Failed to load cards:", e);
      } finally {
        this.loading = false;
        this.updateLoading();
      }
    }

    async loadFragments() {
      this.loading = true;
      this.updateLoading();
      try {
        const data = await this.api("/api/idea/fragments");
        this.fragments = data.items || [];
        this.renderFragments();
      } catch (e) {
        console.error("Failed to load fragments:", e);
      } finally {
        this.loading = false;
        this.updateLoading();
      }
    }

    async loadLibrary() {
      this.loading = true;
      this.updateLoading();
      try {
        const data = await this.api("/api/idea/library");
        this.library = data.items || [];
        this.renderLibrary();
      } catch (e) {
        console.error("Failed to load library:", e);
      } finally {
        this.loading = false;
        this.updateLoading();
      }
    }

    async syncMaterials() {
      this.loading = true;
      this.updateLoading();
      try {
        const connectors = this.connectorStatus.filter((c) => c.enabled);
        let allMaterials = [];

        for (const conn of connectors) {
          try {
            const data = await this.api(`/api/idea/sync/${conn.connector_id}`, {
              method: "POST",
            });
            allMaterials = [...allMaterials, ...(data.materials || [])];
          } catch (e) {
            console.error(`Failed to sync ${conn.connector_id}:`, e);
          }
        }

        this.materials = [...this.materials, ...allMaterials];
        this.renderMaterials();
        this.notify(`同步完成，新增 ${allMaterials.length} 条素材`);
      } finally {
        this.loading = false;
        this.updateLoading();
      }
    }

    async generateCards() {
      this.loading = true;
      this.updateLoading();
      try {
        const data = await this.api("/api/idea/generate", {
          method: "POST",
          body: JSON.stringify({}),
        });
        this.cards = [...this.cards, ...(data.cards || [])];
        this.renderCards();
        this.notify(`生成 ${data.cards?.length || 0} 张选题卡`);
      } catch (e) {
        console.error("Failed to generate cards:", e);
        this.notify("生成选题失败", true);
      } finally {
        this.loading = false;
        this.updateLoading();
      }
    }

    async createFragment() {
      const input = document.getElementById("fragment-input");
      const content = input?.value?.trim();
      if (!content) return;

      try {
        const data = await this.api("/api/idea/fragments", {
          method: "POST",
          body: JSON.stringify({ content }),
        });
        this.fragments.unshift(data);
        input.value = "";
        this.renderFragments();
      } catch (e) {
        console.error("Failed to create fragment:", e);
        this.notify("记录灵感失败", true);
      }
    }

    async deleteFragment(fragmentId) {
      try {
        await this.api(`/api/idea/fragments/${fragmentId}`, { method: "DELETE" });
        this.fragments = this.fragments.filter((f) => f.id !== fragmentId);
        this.renderFragments();
      } catch (e) {
        console.error("Failed to delete fragment:", e);
      }
    }

    async selectCard(cardId) {
      try {
        const data = await this.api(`/api/idea/cards/${cardId}/select`, {
          method: "POST",
          body: JSON.stringify({ create_project: true }),
        });
        const card = this.cards.find((c) => c.id === cardId);
        if (card) card.status = "selected";
        this.renderCards();
        if (data.project_created) {
          this.notify(`项目已创建: ${data.project_id}`);
        }
      } catch (e) {
        console.error("Failed to select card:", e);
        this.notify("选择选题失败", true);
      }
    }

    async rejectCard(cardId) {
      try {
        await this.api(`/api/idea/cards/${cardId}/reject`, { method: "POST" });
        this.cards = this.cards.filter((c) => c.id !== cardId);
        this.renderCards();
      } catch (e) {
        console.error("Failed to reject card:", e);
      }
    }

    async addToLibrary(card) {
      try {
        const data = await this.api("/api/idea/library", {
          method: "POST",
          body: JSON.stringify({
            card_id: card.id,
            title: card.title,
            hook: card.hook,
            tags: card.angles || [],
          }),
        });
        this.library.unshift(data);
        this.notify("已添加到选题库");
      } catch (e) {
        console.error("Failed to add to library:", e);
        this.notify("收藏失败", true);
      }
    }

    async removeFromLibrary(itemId) {
      try {
        await this.api(`/api/idea/library/${itemId}`, { method: "DELETE" });
        this.library = this.library.filter((i) => i.id !== itemId);
        this.renderLibrary();
      } catch (e) {
        console.error("Failed to remove from library:", e);
      }
    }

    async selectMaterial(materialId) {
      try {
        const data = await this.api("/api/idea/generate", {
          method: "POST",
          body: JSON.stringify({ material_ids: [materialId] }),
        });
        if (data.cards && data.cards.length > 0) {
          this.cards = [...this.cards, ...data.cards];
          this.switchTab("cards");
        }
      } catch (e) {
        console.error("Failed to generate card from material:", e);
        this.notify("生成选题失败", true);
      }
    }

    wireEvents() {
      this.container.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-idea-action]");
        if (!btn) return;
        const action = btn.dataset.ideaAction;
        const id = btn.dataset.id;
        switch (action) {
          case "sync": return this.syncMaterials();
          case "generate": return this.generateCards();
          case "tab": return this.switchTab(btn.dataset.tab);
          case "select-material": return this.selectMaterial(id);
          case "select-card": return this.selectCard(id);
          case "reject-card": return this.rejectCard(id);
          case "add-library": {
            const card = this.cards.find((c) => c.id === id);
            if (card) return this.addToLibrary(card);
            return;
          }
          case "add-fragment": return this.createFragment();
          case "delete-fragment": return this.deleteFragment(id);
          case "remove-library": return this.removeFromLibrary(id);
        }
      });
      this.container.addEventListener("keydown", (e) => {
        if (e.target.id === "fragment-input" && e.key === "Enter") {
          e.preventDefault();
          this.createFragment();
        }
      });
    }

    render() {
      this.container.innerHTML = `
        <div class="idea-panel">
          <div class="idea-notify" style="display:none"></div>
          <div class="idea-header">
            <div class="idea-actions">
              <button class="btn-sync" data-idea-action="sync">同步素材</button>
              <button class="btn-generate" data-idea-action="generate">生成选题</button>
            </div>
          </div>
          <div class="idea-tabs">
            <button class="tab ${this.currentTab === "materials" ? "active" : ""}"
                    data-idea-action="tab" data-tab="materials">
              素材 (${this.materials.length})
            </button>
            <button class="tab ${this.currentTab === "cards" ? "active" : ""}"
                    data-idea-action="tab" data-tab="cards">
              选题 (${this.cards.length})
            </button>
            <button class="tab ${this.currentTab === "fragments" ? "active" : ""}"
                    data-idea-action="tab" data-tab="fragments">
              灵感 (${this.fragments.length})
            </button>
            <button class="tab ${this.currentTab === "library" ? "active" : ""}"
                    data-idea-action="tab" data-tab="library">
              选题库 (${this.library.length})
            </button>
            <button class="tab ${this.currentTab === "connectors" ? "active" : ""}"
                    data-idea-action="tab" data-tab="connectors">
              连接器
            </button>
          </div>
          <div class="idea-content">
            <div id="materials-list" class="materials-list"></div>
            <div id="cards-list" class="cards-list" style="display:none"></div>
            <div id="fragments-list" class="fragments-list" style="display:none"></div>
            <div id="library-list" class="library-list" style="display:none"></div>
            <div id="connectors-list" class="connectors-list" style="display:none"></div>
          </div>
          <div class="idea-loading" style="display:none">加载中...</div>
        </div>
      `;
    }

    switchTab(tab) {
      this.currentTab = tab;
      const tabs = ["materials", "cards", "fragments", "library", "connectors"];

      this.container.querySelectorAll(".idea-tabs .tab").forEach((el) => {
        el.classList.toggle("active", el.dataset.tab === tab);
      });

      tabs.forEach((t) => {
        const el = document.getElementById(`${t}-list`);
        if (el) el.style.display = tab === t ? "" : "none";
      });

      if (tab === "cards") this.loadCards();
      if (tab === "fragments") this.loadFragments();
      if (tab === "library") this.loadLibrary();
      if (tab === "connectors") this.loadConnectorStatus();
    }

    updateLoading() {
      const el = this.container.querySelector(".idea-loading");
      if (el) el.style.display = this.loading ? "" : "none";
    }

    renderMaterials() {
      const list = document.getElementById("materials-list");
      if (!list) return;

      if (this.materials.length === 0) {
        list.innerHTML = '<div class="empty">暂无素材，点击「同步素材」开始采集</div>';
        return;
      }

      list.innerHTML = this.materials
        .map(
          (m) => `
      <div class="material-card">
        <div class="material-header">
          <span class="material-source">${esc(m.source)}</span>
          <span class="material-heat">🔥 ${esc(m.heat)}</span>
        </div>
        <h3 class="material-title">
          <a href="${safeUrl(m.url)}" target="_blank" rel="noopener">${esc(m.title)}</a>
        </h3>
        <p class="material-summary">${esc(m.summary || "")}</p>
        <div class="material-tags">
          ${(m.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}
        </div>
        <div class="material-actions">
          <button class="btn-select" data-idea-action="select-material" data-id="${esc(m.id)}">生成选题</button>
        </div>
      </div>
    `
        )
        .join("");
    }

    renderCards() {
      const list = document.getElementById("cards-list");
      if (!list) return;

      if (this.cards.length === 0) {
        list.innerHTML = '<div class="empty">暂无选题，点击「生成选题」开始创作</div>';
        return;
      }

      list.innerHTML = this.cards
        .map(
          (c) => `
      <div class="card-item ${esc(c.status)}">
        <div class="card-header">
          <span class="card-status">${c.status === "selected" ? "已选" : c.status === "rejected" ? "已拒" : "待选"}</span>
          <span class="card-scores">
            热度 ${esc(c.heat_score)}/5 · 难度 ${esc(c.difficulty_score)}/5
          </span>
        </div>
        <h3 class="card-title">${esc(c.title)}</h3>
        <p class="card-hook">${esc(c.hook)}</p>
        <div class="card-angles">
          ${(c.angles || []).map((a) => `<div class="angle">• ${esc(a)}</div>`).join("")}
        </div>
        <div class="card-meta">时间窗口: ${esc(c.time_window)}</div>
        ${
          c.status === "pending"
            ? `<div class="card-actions">
                 <button class="btn-accept" data-idea-action="select-card" data-id="${esc(c.id)}">做这个</button>
                 <button class="btn-save" data-idea-action="add-library" data-id="${esc(c.id)}">收藏</button>
                 <button class="btn-reject" data-idea-action="reject-card" data-id="${esc(c.id)}">跳过</button>
               </div>`
            : ""
        }
      </div>
    `
        )
        .join("");
    }

    renderFragments() {
      const list = document.getElementById("fragments-list");
      if (!list) return;

      const inputHtml = `
        <div class="fragment-input-box">
          <input type="text" id="fragment-input" placeholder="记录一个灵感..." />
          <button class="btn-add-fragment" data-idea-action="add-fragment">添加</button>
        </div>
      `;

      if (this.fragments.length === 0) {
        list.innerHTML = inputHtml + '<div class="empty">暂无灵感碎片，随手记录你的想法</div>';
        return;
      }

      list.innerHTML =
        inputHtml +
        this.fragments
          .map(
            (f) => `
      <div class="fragment-item">
        <div class="fragment-content">${esc(f.content)}</div>
        <div class="fragment-meta">
          <span class="fragment-time">${esc(new Date(f.created_at).toLocaleDateString())}</span>
          <button class="btn-delete-fragment" data-idea-action="delete-fragment" data-id="${esc(f.id)}">×</button>
        </div>
      </div>
    `
          )
          .join("");
    }

    renderLibrary() {
      const list = document.getElementById("library-list");
      if (!list) return;

      if (this.library.length === 0) {
        list.innerHTML = '<div class="empty">暂无收藏的选题</div>';
        return;
      }

      list.innerHTML = this.library
        .map(
          (item) => `
      <div class="library-item">
        <div class="library-header">
          <h3 class="library-title">${esc(item.title)}</h3>
          <button class="btn-delete-library" data-idea-action="remove-library" data-id="${esc(item.id)}">×</button>
        </div>
        <p class="library-hook">${esc(item.hook)}</p>
        <div class="library-tags">
          ${(item.tags || []).map((t) => `<span class="tag">${esc(t)}</span>`).join("")}
        </div>
        <div class="library-meta">
          收藏于 ${esc(new Date(item.created_at).toLocaleDateString())}
        </div>
      </div>
    `
        )
        .join("");
    }

    renderConnectors() {
      const list = document.getElementById("connectors-list");
      if (!list) return;

      if (this.connectorStatus.length === 0) {
        list.innerHTML = '<div class="empty">暂无可用连接器</div>';
        return;
      }

      list.innerHTML = this.connectorStatus
        .map(
          (c) => `
      <div class="connector-item">
        <div class="connector-icon">${esc(c.icon || "🔗")}</div>
        <div class="connector-info">
          <h3 class="connector-name">${esc(c.name)}</h3>
          <p class="connector-desc">${esc(c.description || c.connector_id)}</p>
        </div>
        <div class="connector-status ${esc(c.status)}">${c.status === "ready" ? "就绪" : esc(c.status)}</div>
      </div>
    `
        )
        .join("");
    }
  }

  window.IdeaEnginePanel = IdeaEnginePanel;
})();
