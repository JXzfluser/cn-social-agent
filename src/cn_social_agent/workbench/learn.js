(function () {
  "use strict";

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  var AL = { topics: [], current: null, quiz: null, currentReadme: "" };
  var keepTab = null;
  var topicsLoaded = false;
  var PANE = { notes: "learnNotes", demos: "learnDemos", kb: "learnKb", quiz: "learnQuiz", diagram: "learnDiagram", graph: "learnGraph", tutor: "learnTutor" };

  // SM-2 间隔重复算法
  var SM2 = {
    // 状态：key=quizId-userId，值={ease, reps, interval, due}
    state: JSON.parse(localStorage.getItem("sm2_state") || "{}"),
    get(key) { return this.state[key] || {ease: 2.5, reps: 0, interval: 0, due: 0}; },
    set(key, val) { this.state[key] = val; localStorage.setItem("sm2_state", JSON.stringify(this.state)); },
    forget() { this.state = {}; localStorage.removeItem("sm2_state"); }
  };

  // 记录 quiz 答案并更新 SM-2
  function recordQuizResult(quizId, correct) {
    var key = quizId + "-" + (token() || "anon");
    var s = SM2.get(key);
    if (correct) {
      if (s.reps === 0) { s.interval = 1; }
      else if (s.interval < 1) { s.interval = 1; }
      else { s.interval = Math.round(s.interval * s.ease); }
      s.ease = Math.max(1.3, s.ease + (0.1 - (5 - s.q)/(5 * Math.pow(3, s.reps/5 + 1.6))) || 1.3);
      s.reps++;
    } else {
      s.ease = Math.max(1.3, s.ease - 0.8);
      s.reps = 0;
      s.interval = 0;
    }
    s.due = new Date().getTime() + s.interval * 86400000; // 间隔（天）转毫秒
    SM2.set(key, s);
    localStorage.setItem("sm2_state", JSON.stringify(SM2.state));
    return s;
  }

  // 下次复习的题目（按 due 时间排序）
  function dueQuizzes(userId) {
    var keys = Object.keys(SM2.state).filter(function(k) { return k.endsWith("-" + userId || ""); });
    var items = keys.map(function(k) {
      var s = SM2.state[k];
      var topicId = k.split("-")[0];
      return {topicId, due: s.due, ease: s.ease, reps: s.reps};
    }).sort(function(a, b){ return a.due - b.due; });
    return items.filter(function(i){ return i.due <= Date.now(); });
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  function token() { return localStorage.getItem("wb_token") || ""; }

  function cleanSrc(s) {
    if (!s) return "";
    var i = String(s).indexOf("topics/");
    if (i >= 0) {
      var rest = String(s).slice(i + 7).split("/");
      return rest[0] || String(s);
    }
    return String(s);
  }

  function api(path, opts) {
    opts = opts || {};
    var headers = {};
    var t = token();
    if (t) headers["Authorization"] = "Bearer " + t;
    if (opts.body) headers["Content-Type"] = "application/json";
    return fetch("/api/learn" + path, {
      method: opts.method || "GET",
      headers: headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined
    }).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
        return j;
      });
    });
  }

  function status(msg, kind) {
    var el = $("#learnStatus");
    if (!el) return;
    el.textContent = msg || "";
    el.className = "learn-status" + (kind ? " " + kind : "");
  }

  function inline(s) {
    return esc(s)
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>");
  }

  function renderMd(md) {
    if (!md) return '<p class="muted">（暂无笔记）</p>';
    var lines = String(md).replace(/\r\n/g, "\n").split("\n");
    var html = [], i = 0, inCode = false, code = [];
    function flush() { html.push("<pre><code>" + esc(code.join("\n")) + "</code></pre>"); code = []; }
    function parseTableRow(line) {
      return line.split("|").map(function(c){ return c.trim(); }).filter(function(c){ return c !== ""; });
    }
    while (i < lines.length) {
      var line = lines[i];
      if (/^```/.test(line)) { if (inCode) { flush(); inCode = false; } else { inCode = true; } i++; continue; }
      if (inCode) { code.push(line); i++; continue; }
      var h = line.match(/^(#{1,6})\s+(.*)$/);
      if (h) { var l = h[1].length; html.push("<h" + l + ">" + inline(h[2]) + "</h" + l + ">"); i++; continue; }
      // Table: detect | delimited rows
      if (/^\|/.test(line) && i + 1 < lines.length && /^\|[\s\-:|]+\|/.test(lines[i + 1])) {
        var headers = parseTableRow(line);
        i += 2; // skip separator row
        var rows = [];
        while (i < lines.length && /^\|/.test(lines[i])) {
          rows.push(parseTableRow(lines[i]));
          i++;
        }
        var tbl = ['<div class="learn-table-wrap"><table>'];
        tbl.push("<thead><tr>");
        headers.forEach(function(c){ tbl.push("<th>" + inline(c) + "</th>"); });
        tbl.push("</tr></thead>");
        if (rows.length) {
          tbl.push("<tbody>");
          rows.forEach(function(row) {
            tbl.push("<tr>");
            row.forEach(function(c){ tbl.push("<td>" + inline(c) + "</td>"); });
            tbl.push("</tr>");
          });
          tbl.push("</tbody>");
        }
        tbl.push("</table></div>");
        html.push(tbl.join(""));
        continue;
      }
      if (/^\s*[-*]\s+/.test(line)) {
        var ul = ["<ul>"];
        while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) { ul.push("<li>" + inline(lines[i].replace(/^\s*[-*]\s+/, "")) + "</li>"); i++; }
        ul.push("</ul>"); html.push(ul.join("")); continue;
      }
      if (/^\s*\d+\.\s+/.test(line)) {
        var ol = ["<ol>"];
        while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) { ol.push("<li>" + inline(lines[i].replace(/^\s*\d+\.\s+/, "")) + "</li>"); i++; }
        ol.push("</ol>"); html.push(ol.join("")); continue;
      }
      if (/^\s*$/.test(line)) { i++; continue; }
      html.push("<p>" + inline(line) + "</p>"); i++;
    }
    if (inCode) flush();
    return html.join("\n");
  }

  function showTab(tab) {
    $$(".learn-tabs button").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-tab") === tab);
    });
    Object.keys(PANE).forEach(function (k) {
      var p = $("#" + PANE[k]);
      if (p) p.hidden = (k !== tab);
    });
    if (tab === "graph") renderKnowledgeGraph();
  }

  function loadTopics() {
    if (topicsLoaded) return;
    status("加载知识点…");
    api("/topics").then(function (d) {
      AL.topics = d.topics || [];
      $("#learnCount").textContent = AL.topics.length + " 个";
      var list = $("#learnTopicList");
      list.innerHTML = AL.topics.map(function (t) {
        return '<button class="learn-topic" data-id="' + esc(t.id) + '">' +
          '<span class="lt-id">' + esc(t.id) + '</span>' +
          '<span class="lt-title">' + esc(t.title || t.name) + '</span></button>';
      }).join("");
      $$(".learn-topic", list).forEach(function (b) {
        b.addEventListener("click", function () { selectTopic(b.getAttribute("data-id"), b); });
      });
      status("");
      topicsLoaded = true;
      if (AL.topics.length) selectTopic(AL.topics[0].id, $(".learn-topic", list));
    }).catch(function (e) {
      status("加载失败：" + e.message, "err");
    });
  }

  function selectTopic(id, el) {
    $$(".learn-topic").forEach(function (b) { b.classList.remove("active"); });
    if (el) el.classList.add("active");
    AL.current = id;
    status("加载主题 " + id + " …");
    api("/topic/" + id).then(function (d) {
      AL.currentReadme = d.readme || "";
      AL.currentTitle = d.title || d.name || id;
      $("#learnHead").innerHTML =
        '<span class="lh-title">' + esc(d.title || d.name) + '</span>' +
        '<span class="lh-sum">' + esc(d.id) + '</span>' +
        '<span class="lh-actions">' +
          '<button id="learnExportCanvas" title="导出笔记到画布">导出到画布</button>' +
          '<button id="learnMarkDone" title="标记为已学完" class="primary">✓ 已学完</button>' +
        '</span>';
      $("#learnExportCanvas").onclick = exportToCanvas;
      $("#learnMarkDone").onclick = markCompleted;
      renderNotes(d.readme);
      renderDemos(d.demos || []);
      buildKb();
      loadQuiz(id);
      loadDiagram(id);
      showTab(keepTab || "notes"); keepTab = null;
      status("");
    }).catch(function (e) {
      status("主题加载失败：" + e.message, "err");
    });
  }

  function renderNotes(md) {
    $("#learnNotes").innerHTML = '<div class="learn-md">' + renderMd(md) + "</div>";
  }

  function renderDemos(demos) {
    var box = $("#learnDemos");
    if (!demos.length) { box.innerHTML = '<div class="soon">该主题暂无 Demo</div>'; return; }
    box.innerHTML = demos.map(function (dm, idx) {
      return '<div class="demo-card">' +
        '<div class="demo-title"><code>' + esc(dm.path) + '</code></div>' +
        (dm.doc ? '<div class="demo-doc">' + esc(dm.doc) + '</div>' : '') +
        '<button type="button" class="quiz-opt" data-idx="' + idx + '" data-path="' + esc(dm.path) + '">运行 Demo</button>' +
        '<pre class="demo-out" id="demoOut' + idx + '" hidden></pre></div>';
    }).join("");
    $$(".demo-card button", box).forEach(function (b) {
      b.addEventListener("click", function () { runDemo(b.getAttribute("data-path"), b); });
    });
  }

  function runDemo(path, btn) {
    var out = $("#demoOut" + btn.getAttribute("data-idx"));
    btn.disabled = true; out.hidden = false; out.textContent = "运行中…";
    status("运行：" + path);
    api("/run", { method: "POST", body: { path: path } }).then(function (r) {
      var txt = (r.stdout || "") + (r.stderr ? "\n[stderr]\n" + r.stderr : "");
      out.textContent = txt || "（无输出）";
      status(r.returncode === 0 ? "运行完成" : "结束（exit " + r.returncode + "）", r.returncode === 0 ? "ok" : "warn");
    }).catch(function (e) {
      out.textContent = "错误：" + e.message;
      status("运行失败：" + e.message, "err");
    }).then(function () { btn.disabled = false; });
  }

  function buildKb() {
    $("#learnKb").innerHTML =
      '<div class="kb-box">' +
      '<input id="kbQuestion" type="text" placeholder="向知识库提问…" />' +
      '<button id="kbRun" type="button" class="quiz-opt">提问</button></div>' +
      '<div id="kbAnswer" class="kb-res soon">输入问题，在本仓库知识库（RAG）中检索相关笔记。</div>' +
      '<div id="kbSources"></div>' +
      '<div id="learnStatus" class="learn-status"></div>';
    $("#kbRun").addEventListener("click", runKb);
    var q = $("#kbQuestion");
    q.addEventListener("keydown", function (e) { if (e.key === "Enter") runKb(); });
  }

  function runKb() {
    var q = $("#kbQuestion").value.trim();
    if (!q) { status("请输入问题", "warn"); return; }
    status("检索中…");
    api("/kb", { method: "POST", body: { query: q, top_k: 5, synthesize: true } }).then(function (r) {
      var answerHtml;
      if (r.answer && !r.answer_error) {
        answerHtml = '<div class="learn-md">' + renderMd(r.answer) + "</div>";
      } else {
        var chunks = (r.results || []).slice(0, 3).map(function (s) {
          return '<div class="learn-md"><p>' + esc(s.text) + "</p></div>";
        }).join("");
        answerHtml = '<div class="muted">（离线合成不可用，以下为检索到的相关笔记）</div>' + chunks;
      }
      var ans = $("#kbAnswer");
      ans.className = "kb-res";
      ans.innerHTML = answerHtml;
      $("#kbSources").innerHTML = (r.results || []).map(function (s) {
        return '<div class="kb-res"><span class="score">' + (s.score != null ? s.score.toFixed(2) : "") +
          '</span><span class="src">' + esc(cleanSrc(s.source)) + '</span></div>';
      }).join("");
      status("");
    }).catch(function (e) {
      status("问答失败：" + e.message, "err");
    });
  }

  function loadQuiz(id) {
    api("/quiz/" + id).then(function (d) {
      AL.quiz = d; renderQuiz(d);
    }).catch(function (e) {
      $("#learnQuiz").innerHTML = '<div class="soon">该主题暂无自测题</div>';
    });
  }

  function renderQuiz(d) {
    var box = $("#learnQuiz");
    if (!d || !d.questions || !d.questions.length) { box.innerHTML = '<div class="soon">该主题暂无自测题</div>'; return; }
    box.innerHTML = d.questions.map(function (q, i) {
      return '<div class="quiz-q" data-i="' + i + '">' +
        '<div class="q">' + (i + 1) + ". " + esc(q.q) + "</div>" +
        q.options.map(function (o, j) {
          return '<button type="button" class="quiz-opt" data-q="' + i + '" data-o="' + j + '">' + esc(o) + "</button>";
        }).join("") +
        '<div class="quiz-fb" id="qfb' + i + '"></div></div>';
    }).join("") + '<button id="quizGrade" type="button" class="quiz-opt">提交自测</button>';

var due = dueQuizzes(token() || "anon");
if (due.length > 0) {
  box.innerHTML += '<button id="quizReview" type="button" class="quiz-opt" style="margin-top:8px;">复习 (' + due.length + ')</button>';
}
box.innerHTML += '<span id="quizScore"></span>';
    $$(".quiz-opt[data-q]", box).forEach(function (b) {
      b.addEventListener("click", function () {
        var qi = b.getAttribute("data-q");
        $$('.quiz-opt[data-q="' + qi + '"]', box).forEach(function (x) { x.classList.remove("sel"); });
        b.classList.add("sel");
      });
    });
    $("#quizGrade").addEventListener("click", gradeQuiz);
  }

  function gradeQuiz() {
    if (!AL.quiz) return;
    var qs = AL.quiz.questions, correct = 0;
    qs.forEach(function (q, i) {
      var opts = $$('.quiz-opt[data-q="' + i + '"]', $("#learnQuiz"));
      var sel = $(".quiz-opt.sel[data-q='" + i + "']", $("#learnQuiz"));
      var picked = sel ? parseInt(sel.getAttribute("data-o"), 10) : -1;
      var ok = picked === q.answer;
      if (ok) correct++;
      opts.forEach(function (o) { o.disabled = true; o.style.cursor = "default"; });
      if (opts[q.answer]) opts[q.answer].classList.add("correct");
      if (sel && !ok && opts[picked]) opts[picked].classList.add("wrong");
      var fb = $("#qfb" + i);
      fb.className = "quiz-fb " + (ok ? "correct" : "wrong");
      fb.innerHTML = (ok ? "✓ 正确。" : "✗ 正确：" + esc(q.options[q.answer] || "")) +
        '<div class="quiz-explain">' + esc(q.explain || "") + "</div>";
    });
    var gradeBtn = $("#quizGrade");
    if (gradeBtn) gradeBtn.disabled = true;
    var scoreText = "得分 " + correct + " / " + qs.length;
    // 记录 SM-2 间隔重复结果
    var key = AL.quiz.id + "-" + (token() || "anon");
    var s = recordQuizResult(key, correct > 0);
    scoreText += " · 复习间隔: " + (s.interval || 0) + "天";
    $("#quizScore").textContent = scoreText;
  }

  function loadDiagram(id) {
    api("/diagram/" + id).then(function (d) {
      AL.diagram = d; renderDiagram(d);
    }).catch(function (e) {
      $("#learnDiagram").innerHTML = '<div class="soon">该主题暂无流程图</div>';
    });
  }

  function renderDiagram(d) {
    var box = $("#learnDiagram");
    if (!d || !d.nodes || !d.nodes.length) { box.innerHTML = '<div class="soon">该主题暂无流程图</div>'; return; }
    var colW = 220, rowH = 96, nW = 168, nH = 48, padX = 24, padY = 24;
    var maxCol = 0, maxRow = 0;
    d.nodes.forEach(function (n) { maxCol = Math.max(maxCol, n.col || 0); maxRow = Math.max(maxRow, n.row || 0); });
    var W = padX * 2 + (maxCol + 1) * nW + maxCol * Math.max(0, colW - nW);
    var H = padY * 2 + (maxRow + 1) * nH + maxRow * Math.max(0, rowH - nH);
    function cx(n) { return padX + (n.col || 0) * colW + nW / 2; }
    function cy(n) { return padY + (n.row || 0) * rowH + nH / 2; }
    var pos = {};
    d.nodes.forEach(function (n) { pos[n.id] = { x: cx(n), y: cy(n) }; });
    var edges = d.edges.map(function (e) {
      var a = pos[e.from], b = pos[e.to];
      if (!a || !b) return "";
      var dx = b.x - a.x, dy = b.y - a.y;
      var sx = a.x + (dx ? (dx > 0 ? nW / 2 : -nW / 2) : 0);
      var sy = a.y + (dy ? (dy > 0 ? nH / 2 : -nH / 2) : 0);
      var tx = b.x - (dx ? (dx > 0 ? nW / 2 : -nW / 2) : 0);
      var ty = b.y - (dy ? (dy > 0 ? nH / 2 : -nH / 2) : 0);
      return '<path class="edge" d="M' + sx + "," + sy + " L" + tx + "," + ty + '" marker-end="url(#arrow)"/>' +
        (e.label ? '<text class="elabel" x="' + ((sx + tx) / 2) + '" y="' + ((sy + ty) / 2 - 4) + '" text-anchor="middle">' + esc(e.label) + "</text>" : "");
    }).join("");
    var nodes = d.nodes.map(function (n) {
      var p = pos[n.id];
      return '<g><rect class="node" x="' + (p.x - nW / 2) + '" y="' + (p.y - nH / 2) + '" width="' + nW + '" height="' + nH + '" rx="8"/>' +
        '<text class="nlabel" x="' + p.x + '" y="' + p.y + '" text-anchor="middle" dominant-baseline="middle">' + esc(n.label) + "</text></g>";
    }).join("");
    box.innerHTML = '<svg class="diagram-svg" viewBox="0 0 ' + W + " " + H + '" width="100%">' +
      '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">' +
      '<path d="M0,0 L8,3 L0,6 Z" fill="#a8a29e"/></marker></defs>' + edges + nodes + "</svg>";
  }



  function renderKnowledgeGraph() {
    var box = $("#learnGraph");
    if (!box) return;
    var topics = AL.topics || [];
    if (!topics.length) { box.innerHTML = '<div class="soon">暂无可展示的知识点</div>'; return; }
    var completed = JSON.parse(localStorage.getItem("learn_completed") || "[]");
    var N = topics.length;
    function titleOf(t) { return t.title || t.name || t.id; }
    function short(s) { s = titleOf(s); return s.length > 8 ? s.slice(0, 7) + "…" : s; }

    if (!AL.current) {
      var ov = [];
      ov.push('<div class="kg-head"><div class="kg-title">学习路径总览</div>');
      ov.push('<div class="kg-sub">共 ' + N + ' 个知识点，已学完 ' + completed.length + ' 个。点击任意节点进入「模拟吃透」。</div></div>');
      ov.push('<div class="kg-path">');
      topics.forEach(function (t, idx) {
        var cls = "kg-chip" + (completed.indexOf(t.id) >= 0 ? " done" : "");
        ov.push('<span class="' + cls + '" data-id="' + esc(t.id) + '">' + (idx + 1) + '. ' + esc(short(t)) + '</span>');
      });
      ov.push('</div>');
      box.innerHTML = ov.join("");
      box.querySelectorAll(".kg-chip").forEach(function (el) {
        el.addEventListener("click", function () { focusTopic(el.getAttribute("data-id")); });
      });
      return;
    }

    var i = -1;
    for (var k = 0; k < N; k++) { if (topics[k].id === AL.current) { i = k; break; } }
    if (i < 0) { box.innerHTML = '<div class="soon">请先在左侧选择一个知识点</div>'; return; }
    var cur = topics[i];

    var html = [];
    html.push('<div class="kg-head">');
    html.push('<div class="kg-title">知识点网络 · 第 ' + (i + 1) + ' / ' + N + ' 个</div>');
    html.push('<div class="kg-sub">中心为「当前知识点」，两侧为学习路径上的前驱 / 后继节点</div>');
    html.push('</div>');

    var W = 640, H = 320, cx = W / 2, cy = H / 2, nW = 150, nH = 46, cW = 184, cH = 56;
    var slots = {
      "-2": { x: cx - 238, y: cy - 118, rel: "前驱" },
      "-1": { x: cx - 258, y: cy, rel: "前驱" },
      "1": { x: cx + 258, y: cy, rel: "后继" },
      "2": { x: cx + 238, y: cy - 118, rel: "后继" }
    };
    var nb = [];
    [-2, -1, 1, 2].forEach(function (off) {
      var idx = i + off;
      if (idx < 0 || idx >= N) return;
      nb.push({ t: topics[idx], pos: slots[String(off)], rel: slots[String(off)].rel });
    });

    var edges = nb.map(function (n) {
      var dx = n.pos.x - cx, dy = n.pos.y - cy, len = Math.sqrt(dx * dx + dy * dy) || 1;
      var ux = dx / len, uy = dy / len;
      var sx = cx + ux * (cW / 2 + 10), sy = cy + uy * (cH / 2 + 10);
      var ex = n.pos.x - ux * (nW / 2 + 10), ey = n.pos.y - uy * (nH / 2 + 10);
      return '<path class="edge" d="M' + sx + ',' + sy + ' L' + ex + ',' + ey + '" marker-end="url(#kgArrow)"/>' +
        '<text class="elabel" x="' + ((sx + ex) / 2) + '" y="' + ((sy + ey) / 2 - 4) + '" text-anchor="middle">' + esc(n.rel) + '</text>';
    }).join("");

    var curNode = '<g><rect class="node cur" x="' + (cx - cW / 2) + '" y="' + (cy - cH / 2) + '" width="' + cW + '" height="' + cH + '" rx="10"/>' +
      '<text class="nlabel kg-cur-label" x="' + cx + '" y="' + cy + '" text-anchor="middle" dominant-baseline="middle">' + esc(short(cur)) + '</text></g>';

    var others = nb.map(function (n) {
      return '<g class="kg-neighbor" data-id="' + esc(n.t.id) + '" style="cursor:pointer"><rect class="node" x="' + (n.pos.x - nW / 2) + '" y="' + (n.pos.y - nH / 2) + '" width="' + nW + '" height="' + nH + '" rx="8"/>' +
        '<text class="nlabel" x="' + n.pos.x + '" y="' + n.pos.y + '" text-anchor="middle" dominant-baseline="middle">' + esc(short(n.t)) + '</text></g>';
    }).join("");

    html.push('<svg class="diagram-svg kg-svg" viewBox="0 0 ' + W + ' ' + H + '" width="100%">' +
      '<defs><marker id="kgArrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth"><path d="M0,0 L8,3 L0,6 Z" fill="#a8a29e"/></marker></defs>' +
      edges + curNode + others + '</svg>');

    html.push('<div class="kg-overview"><div class="kg-ov-title">学习路径（第 ' + (i + 1) + ' / ' + N + ' 个，已学 ' + completed.length + '）</div><div class="kg-path">');
    topics.forEach(function (t, idx) {
      var cls = "kg-chip" + (t.id === AL.current ? " cur" : "") + (completed.indexOf(t.id) >= 0 ? " done" : "");
      html.push('<span class="' + cls + '" data-id="' + esc(t.id) + '">' + (idx + 1) + '. ' + esc(short(t)) + '</span>');
    });
    html.push('</div></div>');

    box.innerHTML = html.join("");
    box.querySelectorAll(".kg-neighbor, .kg-chip").forEach(function (el) {
      el.addEventListener("click", function () { focusTopic(el.getAttribute("data-id")); });
    });
  }

  function focusTopic(id) {
    var el = document.querySelector('.learn-topic[data-id="' + id + '"]');
    keepTab = "graph";
    selectTopic(id, el);
  }

  function initAITutor() {
    var headers = { "Content-Type": "application/json" };
    var t = token();
    if (t) headers["Authorization"] = "Bearer " + t;
    function sendMsg(text, toBot) {
      var role = toBot ? "assistant" : "user";
      var el = document.createElement("div");
      el.className = `bubble ${role}`;
      el.textContent = text;
      var messages = $("#tutorMessages");
      messages.appendChild(el);
      messages.scrollTop = messages.scrollHeight;
      return el;
    }
    function addSystemPrompt() {
      var messages = $("#tutorMessages");
      var el = document.createElement("div");
      el.className = "bubble bot";
      el.innerHTML = "<strong>AI导师</strong> <small>（由 InsForge + LLM 驱动）</small><p>你好！我是关于 <span id='tutorTopicName'></span> 的 AI 导师。我可以帮助你：</p><ul><li>解释概念</li><li>回答问题</li><li>提供例子</li><li>出测验</li></ul><p>请输入你的问题：</p>";
      messages.innerHTML = "";
      messages.appendChild(el);
    }
    function loadTopicForTutor(topicId) {
      api("/topic/" + topicId).then(function(d) {
        var topicName = d.title || d.name || topicId;
        $("#tutorTopicName").textContent = topicName;
        addSystemPrompt();
      }).catch(function(){});
    }
    $("#tutorSend").onclick = function() {
      var input = $("#tutorInput");
      var text = input.value.trim();
      if (!text) return;
      sendMsg(text, false);
      input.value = "";
      var headers = { "Content-Type": "application/json" };
      var t = token();
      if (t) headers["Authorization"] = "Bearer " + t;
      fetch("/api/learn/chat", {
        method: "POST",
        headers: headers,
        body: JSON.stringify({ topic: $("#tutorTopicName").textContent || "", question: text })
      }).then(function(r){ return r.json(); })
        .then(function(d){
          var reply = d.reply || d.error || "抱歉，我暂时无法回答。";
          sendMsg(reply, true);
        })
        .catch(function(e){ sendMsg("网络错误：" + (e.message || e), true); });
    };
    $("#tutorInput").onkeypress = function(e){
      if(e.key === "Enter") $("#tutorSend").onclick();
    };
  }

  function exportToCanvas() {
    if (!AL.current || !AL.currentReadme) { status("无笔记可导出", "err"); return; }
    status("导出到画布…");
    var noteContent = "# " + (AL.currentTitle || AL.current) + "\n\n" + AL.currentReadme;
    var newNode = {
      id: "learn_" + AL.current + "_" + Date.now(),
      type: "note",
      content: noteContent,
      x: 200 + Math.random() * 300,
      y: 150 + Math.random() * 200,
      tags: ["学习笔记", AL.current]
    };
    var headers = { "Content-Type": "application/json" };
    var t = token();
    if (t) headers["Authorization"] = "Bearer " + t;
    fetch("/api/canvas", { method: "GET", headers: headers })
      .then(function(r){ return r.json(); })
      .then(function(data) {
        var nodes = (data.canvas && data.canvas.nodes) || [];
        var edges = (data.canvas && data.canvas.edges) || [];
        nodes.push(newNode);
        return fetch("/api/canvas", {
          method: "PUT",
          headers: headers,
          body: JSON.stringify({
            nodes: nodes,
            edges: edges,
            title: (data.canvas && data.canvas.title) || "学习笔记"
          })
        });
      })
      .then(function(r){ return r.json(); })
      .then(function(d) {
        status("已导出到画布 ✓", "ok");
      })
      .catch(function(e) {
        status("导出失败：" + (e.message || e), "err");
      });
  }

  function markCompleted() {
    if (!AL.current) return;
    var completed = JSON.parse(localStorage.getItem("learn_completed") || "[]");
    if (completed.indexOf(AL.current) === -1) {
      completed.push(AL.current);
      localStorage.setItem("learn_completed", JSON.stringify(completed));
    }
    var headers = { "Content-Type": "application/json" };
    var t = token();
    if (t) headers["Authorization"] = "Bearer " + t;
    fetch("/api/learn/progress", {
      method: "POST",
      headers: headers,
      body: JSON.stringify({ completed: completed })
    }).catch(function(){});
    var btn = $("#learnMarkDone");
    if (btn) { btn.textContent = "✓ 已学完"; btn.style.opacity = "0.6"; btn.disabled = true; }
    updateTopicIndicators();
    status("已标记学完 ✓", "ok");
  }

  function loadProgress() {
    var headers = {};
    var t = token();
    if (t) headers["Authorization"] = "Bearer " + t;
    fetch("/api/learn/progress", { headers: headers })
      .then(function(r){ return r.json(); })
      .then(function(data) {
        if (data.completed && data.completed.length) {
          var local = JSON.parse(localStorage.getItem("learn_completed") || "[]");
          var merged = Array.from(new Set(local.concat(data.completed)));
          localStorage.setItem("learn_completed", JSON.stringify(merged));
          updateTopicIndicators();
        }
      })
      .catch(function(){});
  }

  function updateTopicIndicators() {
    var completed = JSON.parse(localStorage.getItem("learn_completed") || "[]");
    $$(".learn-topic").forEach(function(b) {
      var id = b.getAttribute("data-id");
      var done = completed.indexOf(id) >= 0;
      var title = b.querySelector(".lt-title");
      if (title) {
        title.textContent = (AL.topics.find(function(t){ return t.id === id; }) || {}).title || id;
        if (done) title.textContent = "✓ " + title.textContent;
      }
    });
  }

  function activateLearn() {
    if (topicsLoaded) { updateTopicIndicators(); return; }
    if (token()) {
      loadTopics();
      loadProgress();
      setTimeout(updateTopicIndicators, 1500);
    }
  }

  function selectTopicById(id) {
    var btn = $(".learn-topic[data-id='" + id + "']");
    if (btn) selectTopic(id, btn);
  }

  function waitForToken(tries) {
    if (topicsLoaded) return;
    if (token()) { loadTopics(); return; }
    if (tries <= 1) return;
    setTimeout(function () { waitForToken(tries - 1); }, 600);
  }

  function init() {
    $$(".learn-tabs button").forEach(function (t) {
      t.addEventListener("click", function () { showTab(t.getAttribute("data-tab")); });
    });
    var learnBtn = document.querySelector('[data-mode="learn"]');
    if (learnBtn) {
      learnBtn.addEventListener("click", function () { activateLearn(); });
    }
    var view = document.getElementById("viewLearn");
    if (view && "MutationObserver" in window) {
      new MutationObserver(function () {
        if (view.classList.contains("active")) activateLearn();
      }).observe(view, { attributes: true, attributeFilter: ["class"] });
      if (view.classList.contains("active")) activateLearn();
    }
    waitForToken(50);
  }

  window.__learnActivate = activateLearn;
  window.__learnSelectTopic = selectTopicById;

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
