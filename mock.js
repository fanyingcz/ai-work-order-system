/* ============================================================
 * 智能工单系统 —— 演示模式 Mock（主端：报修 / 管理）
 *
 * 作用：拦截页面的 XMLHttpRequest（axios 底层），按固定剧本返回数据。
 * 纯静态可部署：不需要后端、数据库、API Key，任何静态托管都能跑。
 *
 * 剧本设计（与真实系统行为一致）：
 *   第 1 轮输入只描述问题、不含地址 → MISS，提示补充地址
 *   第 1 轮就带地址（含"地址/路/号/弄/室/小区"等）→ 直接 SUCCESS
 *   会话中第 2 轮输入 → 合并后 SUCCESS，生成工单
 *   点"重新报修"（DELETE /session/...）→ 重置剧本
 *
 * 2026-09-07 由砚生成
 * ============================================================ */
(function () {
  'use strict';
  if (window.__MOCK_API_ACTIVE__) return;
  window.__MOCK_API_ACTIVE__ = true;

  // ---------- 工具 ----------
  var rand = function (a, b) { return a + Math.random() * (b - a); };
  var nowStr = function () {
    var d = new Date(), p = function (n) { return (n < 10 ? '0' : '') + n; };
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) +
      'T' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
  };
  var hasAddressWord = function (t) {
    return /地址|路|号|弄|室|小区|新村|苑|村|花园/.test(t);
  };

  // ---------- 剧本数据（全部为脱敏样例值） ----------
  var WORKER = {
    id: 268, name: 'worker_照明开关_1', phone: '138000010000',
    company: '区域中心1', department: '区域中心1维修单位',
    certs: '["低压电工证"]'
  };

  function mkOrder(over) {
    var base = {
      id: 40, order_no: 'WO20260907000001',
      accept_time: nowStr(),
      user_input: '家里客厅灯开关坏了，按了没反应',
      sub_category: '电气电路', problem: '照明开关',
      property_company: '区域中心1', maintenance_unit: '区域中心1维修单位',
      priority: '72小时内完成', required_cert: '低压电工证',
      target_dept_semantic: '电力维修组',
      worker_id: 268, status: 'PENDING',
      address: '示例路41弄12号603室', contact: null,
      created_at: nowStr(), updated_at: nowStr(),
      reporter_name: '示例住户', reporter_phone: '13800001234',
      worker_info: WORKER
    };
    for (var k in (over || {})) base[k] = over[k];
    return base;
  }

  // 工单列表：覆盖全部状态，供管理端列表 / 工人端列表 / 看板使用
  var ORDERS = [
    mkOrder({ id: 44, order_no: 'WO20260907000001', status: 'PENDING' }),
    mkOrder({
      id: 43, order_no: 'WO20260906000002', status: 'processing',
      user_input: '家里突然全部断电，邻居家正常', sub_category: '电气电路', problem: '断电',
      address: '示例路1299号8号楼302室', order_no: 'WO20260906000002',
      accept_time: '2026-09-06T09:14:00', created_at: '2026-09-06T09:14:00',
      priority: '半小时到现场', target_dept_semantic: '电力维修组'
    }),
    mkOrder({
      id: 42, order_no: 'WO20260905000003', status: 'completed',
      user_input: '厨房下水道返水，地漏往外冒水', sub_category: '管道窨井', problem: '管道堵塞',
      address: '示例小区3号楼101室', order_no: 'WO20260905000003',
      accept_time: '2026-09-05T15:40:00', created_at: '2026-09-05T15:40:00',
      priority: '24小时内处理', target_dept_semantic: '管道维修组'
    }),
    mkOrder({
      id: 41, order_no: 'WO20260904000004', status: 'worker_completed',
      user_input: '卧室窗户关不严，漏风', sub_category: '门窗维修', problem: '门窗维修',
      address: '示例花园一期6号楼1201室', order_no: 'WO20260904000004',
      accept_time: '2026-09-04T11:02:00', created_at: '2026-09-04T11:02:00',
      priority: '72小时内完成', target_dept_semantic: '门窗维修组'
    }),
    mkOrder({
      id: 40, order_no: 'WO20260903000005', status: 'completed',
      user_input: '卫生间水龙头滴水，关不紧', sub_category: '给排水', problem: '水龙头',
      address: '示例路41弄12号1002室', order_no: 'WO20260903000005',
      accept_time: '2026-09-03T08:20:00', created_at: '2026-09-03T08:20:00',
      priority: '72小时内完成', target_dept_semantic: '管道维修组'
    })
  ];

  var SUBCATEGORIES = [
    { id: 1, sub_category: '电气电路', description: '照明、开关、插座、断电等电力问题' },
    { id: 2, sub_category: '管道窨井', description: '下水道、地漏、管道堵塞与返水' },
    { id: 3, sub_category: '给排水', description: '水龙头、阀门、漏水等用水问题' },
    { id: 4, sub_category: '屋面墙面', description: '渗水、墙皮脱落、屋面破损' },
    { id: 5, sub_category: '门窗维修', description: '门窗变形、关不严、五金损坏' },
    { id: 6, sub_category: '电梯故障', description: '电梯停运、困人、按键失灵' }
  ];

  var CATEGORIES = [
    { id: 1, rule_id: 1, category: '应急维修', sub_category: '险', problem: '墙面严重倾斜', priority: '半小时到现场', required_cert: '结构加固资质', target_dept_semantic: '结构维修组', description: '房屋墙体出现明显倾斜，存在结构安全隐患' },
    { id: 2, rule_id: 2, category: '应急维修', sub_category: '电气电路', problem: '断电', priority: '半小时到现场', required_cert: '低压电工证', target_dept_semantic: '电力维修组', description: '住户家中或公共区域突发断电' },
    { id: 3, rule_id: 3, category: '应急维修', sub_category: '电梯故障', problem: '电梯困人', priority: '立即到现场', required_cert: '电梯维修资质', target_dept_semantic: '电梯维保组', description: '人员被困电梯内，需立即救援' },
    { id: 4, rule_id: 4, category: '日常维修', sub_category: '电气电路', problem: '照明开关', priority: '72小时内完成', required_cert: '低压电工证', target_dept_semantic: '电力维修组', description: '开关、灯具等照明设施损坏' },
    { id: 5, rule_id: 5, category: '日常维修', sub_category: '管道窨井', problem: '管道堵塞', priority: '24小时内处理', required_cert: '管道工证', target_dept_semantic: '管道维修组', description: '下水道、地漏等排水管道堵塞' },
    { id: 6, rule_id: 6, category: '日常维修', sub_category: '给排水', problem: '水龙头', priority: '72小时内完成', required_cert: '管道工证', target_dept_semantic: '管道维修组', description: '水龙头、阀门漏水或损坏' }
  ];

  var KEYWORDS = [
    { id: 1, keyword: '断电', category_id: 2, sub_category: '电气电路', problem: '断电' },
    { id: 2, keyword: '跳闸', category_id: 2, sub_category: '电气电路', problem: '断电' },
    { id: 3, keyword: '开关坏了', category_id: 4, sub_category: '电气电路', problem: '照明开关' },
    { id: 4, keyword: '灯不亮', category_id: 4, sub_category: '电气电路', problem: '照明开关' },
    { id: 5, keyword: '下水道堵', category_id: 5, sub_category: '管道窨井', problem: '管道堵塞' },
    { id: 6, keyword: '返水', category_id: 5, sub_category: '管道窨井', problem: '管道堵塞' },
    { id: 7, keyword: '漏水', category_id: 6, sub_category: '给排水', problem: '水龙头' },
    { id: 8, keyword: '滴水', category_id: 6, sub_category: '给排水', problem: '水龙头' }
  ];

  var LOCATIONS = [
    { id: 1, location: '示例路41弄', category_id: 4, sub_category: '电气电路', problem: '照明开关' },
    { id: 2, location: '示例小区', category_id: 5, sub_category: '管道窨井', problem: '管道堵塞' },
    { id: 3, location: '示例花园一期', category_id: 6, sub_category: '门窗维修', problem: '门窗维修' }
  ];

  var ADDRESS_MAPPINGS = [
    { id: 1, community: '示例路41弄', street: '示例路', property_company: '区域中心1', maintenance_unit: '区域中心1维修单位', district: '示例新区', city: '上海市' },
    { id: 2, community: '示例小区', street: '', property_company: '区域中心2', maintenance_unit: '区域中心2维修单位', district: '示例新区', city: '上海市' },
    { id: 3, community: '示例花园一期', street: '', property_company: '区域中心3', maintenance_unit: '区域中心3维修单位', district: '示例新区', city: '上海市' }
  ];

  var WORKERS = [
    WORKER,
    { id: 269, name: 'worker_断电_1', phone: '138000020000', company: '区域中心1', department: '区域中心1维修单位', certs: '["低压电工证"]' },
    { id: 270, name: 'worker_管道堵塞_1', phone: '138000030000', company: '区域中心2', department: '区域中心2维修单位', certs: '["管道工证"]' },
    { id: 271, name: 'worker_水龙头_1', phone: '138000040000', company: '区域中心2', department: '区域中心2维修单位', certs: '["管道工证"]' },
    { id: 272, name: 'worker_门窗维修_1', phone: '138000050000', company: '区域中心3', department: '区域中心3维修单位', certs: '["木工证"]' }
  ];

  var STATS = {
    total_orders: ORDERS.length,
    status_distribution: { PENDING: 1, processing: 1, completed: 2, worker_completed: 1 },
    subcategory_distribution: [
      { sub_category: '电气电路', count: 2 },
      { sub_category: '管道窨井', count: 1 },
      { sub_category: '给排水', count: 1 },
      { sub_category: '门窗维修', count: 1 }
    ],
    company_distribution: [
      { property_company: '区域中心1', count: 2 },
      { property_company: '区域中心2', count: 2 },
      { property_company: '区域中心3', count: 1 }
    ],
    total_workers: 395,
    pending_feedbacks: 1
  };

  var PENDING_FEEDBACK = [{
    id: 1, order_no: 'WO20260906000002',
    model_problem: '照明开关', human_problem: '电表跳闸', human_keyword: '全屋断电',
    status: 'pending', created_at: nowStr(), updated_at: nowStr()
  }];

  // ---------- 会话剧本 ----------
  var sessionTurn = {};   // userId -> 已对话轮数
  function resetSession(userId) { delete sessionTurn[userId]; }

  function converseReply(userId, text, reporterName, reporterPhone) {
    var turn = sessionTurn[userId] || 0;
    var wo = mkOrder({
      user_input: text,
      accept_time: nowStr(), created_at: nowStr(), updated_at: nowStr()
    });
    if (reporterName) wo.reporter_name = reporterName;
    if (reporterPhone) wo.reporter_phone = reporterPhone;

    // 第 1 轮且输入里已带地址 → 直接成功；否则 MISS 要求补充
    var direct = turn === 0 && hasAddressWord(text);
    if (direct || turn >= 1) {
      sessionTurn[userId] = 0;
      wo.order_no = 'WO20260907000001';
      return {
        code: 0, message: 'ok',
        data: {
          work_order: wo,
          details: {
            input_processor: {
              content: wo.user_input, address: wo.address,
              reporter_name: wo.reporter_name, reporter_phone: wo.reporter_phone
            },
            rule_engine: { sub_category: wo.sub_category, problem: wo.problem, matched_keyword: '演示模式' }
          }
        }
      };
    }
    sessionTurn[userId] = 1;
    return {
      code: 0, message: 'ok',
      data: {
        need_more_input: true,
        content: '客厅照明开关损坏，按下无反应',
        message_to_user: '收到您的报修信息。为确保维修人员准确上门，请补充<b>详细地址</b>（如：××路××弄××号×××室）。',
        session_alive: true,
        input_processor: {
          prechoice_subcategories: ['电气电路'],
          content: '客厅照明开关损坏，按下无反应',
          reporter_name: reporterName || null,
          reporter_phone: reporterPhone || null,
          address: null, location: null
        }
      }
    };
  }

  // ---------- 路由匹配 ----------
  function route(method, url, body) {
    var m; var p = url.replace(/^https?:\/\/[^/]+/, '').split('?')[0];

    var ok = function (data, message) { return { code: 0, message: message || '操作成功', data: data }; };
    var listPage = function (arr, q) {
      var page = parseInt((q && q.page) || '1', 10) || 1;
      var limit = parseInt((q && q.limit) || '20', 10) || 20;
      var items = arr.slice((page - 1) * limit, page * limit);
      return { items: items, total: arr.length, page: page, limit: limit, total_pages: Math.ceil(arr.length / limit) || 1 };
    };
    var parseQuery = function (u) {
      var q = {}; var i = u.indexOf('?');
      if (i < 0) return q;
      u.slice(i + 1).split('&').forEach(function (kv) {
        if (!kv) return;
        var b = kv.split('='); q[decodeURIComponent(b[0])] = decodeURIComponent(b[1] || '');
      });
      return q;
    };

    // ---- 工单对话流程 ----
    if (method === 'POST' && p === '/api/v1/work-order/converse') {
      var b = body || {};
      return converseReply(b.user_id || 'demo', (b.text || '').trim(), b.reporter_name, b.reporter_phone);
    }
    if (method === 'DELETE' && /^\/api\/v1\/session\//.test(p)) {
      resetSession(p.split('/')[4] || '');
      return ok(null, '会话已结束');
    }
    if (method === 'GET' && /^\/api\/v1\/session\//.test(p)) {
      return ok({ has_session: false, step: 'initial', content: '' });
    }

    // ---- 工单查询 ----
    if (method === 'GET' && p === '/api/v1/work-orders') {
      var q = parseQuery(url);
      var arr = ORDERS.slice();
      if (q.status) arr = arr.filter(function (o) { return o.status.toUpperCase() === q.status.toUpperCase(); });
      if (q.worker_id) arr = arr.filter(function (o) { return String(o.worker_id) === String(q.worker_id); });
      return ok(listPage(arr, q));
    }
    if (method === 'POST' && p === '/api/v1/work-orders/search') {
      return ok(listPage(ORDERS, {}));
    }
    m = p.match(/^\/api\/v1\/work-order\/([^/]+)$/);
    if (method === 'GET' && m) {
      var found = null;
      for (var i = 0; i < ORDERS.length; i++) if (ORDERS[i].order_no === m[1]) found = ORDERS[i];
      if (!found) return { code: 1004, message: '工单不存在', data: null };
      return ok(found);
    }
    m = p.match(/^\/api\/v1\/work-order\/([^/]+)\/(start|complete|worker-complete)$/);
    if (method === 'POST' && m) {
      for (var j = 0; j < ORDERS.length; j++) {
        if (ORDERS[j].order_no === m[1]) {
          ORDERS[j].status = (m[2] === 'start') ? 'processing'
            : (m[2] === 'worker-complete') ? 'worker_completed' : 'completed';
          ORDERS[j].updated_at = nowStr();
          return ok(ORDERS[j], '状态已更新为 ' + ORDERS[j].status);
        }
      }
      return { code: 1004, message: '工单不存在', data: null };
    }
    m = p.match(/^\/api\/v1\/work-order\/([^/]+)$/);
    if (method === 'PUT' && m) {
      for (var k2 = 0; k2 < ORDERS.length; k2++) {
        if (ORDERS[k2].order_no === m[1]) {
          var up = body || {};
          for (var f in up) if (up[f] != null && f in ORDERS[k2]) ORDERS[k2][f] = up[f];
          return ok(ORDERS[k2], '工单已更新');
        }
      }
      return { code: 1004, message: '工单不存在', data: null };
    }
    if (method === 'POST' && p === '/api/v1/feedback') {
      return ok(null, '反馈已提交，等待管理员审核');
    }

    // ---- 规则 / 看板 / 管理端数据 ----
    if (method === 'GET' && p === '/api/v1/stats') return ok(STATS);
    if (method === 'GET' && p === '/api/v1/health') return ok({ status: 'running', version: '2.0.0-demo' });
    if (method === 'GET' && p === '/api/v1/subcategories') return ok(SUBCATEGORIES);
    if (method === 'GET' && p === '/api/v1/categories') return ok(CATEGORIES);
    if (method === 'GET' && p === '/api/v1/keywords') return ok(KEYWORDS);
    if (method === 'GET' && p === '/api/v1/rules/completeness') return ok({ complete: true, missing: [] });
    if (method === 'GET' && p === '/api/v1/address-mappings') return ok(ADDRESS_MAPPINGS);
    if (method === 'GET' && p === '/api/v1/workers') return ok(WORKERS);
    if (method === 'GET' && p === '/api/v1/admin/subcategories') return ok(SUBCATEGORIES);
    if (method === 'GET' && p === '/api/v1/admin/categories') return ok(CATEGORIES);
    if (method === 'GET' && p === '/api/v1/admin/keywords') return ok(KEYWORDS);
    if (method === 'GET' && p === '/api/v1/admin/locations') return ok(LOCATIONS);
    if (method === 'GET' && p === '/api/v1/admin/workers') return ok(WORKERS);
    if (method === 'GET' && p === '/api/v1/admin/prompts') return ok([]);
    if (method === 'POST' && /^\/api\/v1\/admin\/prompts/.test(p)) return ok(null);
    if (method === 'PUT' && /^\/api\/v1\/admin\//.test(p)) return ok(null);
    if (method === 'POST' && /^\/api\/v1\/admin\//.test(p)) return ok(null);
    if (method === 'DELETE' && /^\/api\/v1\/admin\//.test(p)) return ok(null);
    if (method === 'GET' && p === '/api/v1/feedback/pending') return ok({ items: PENDING_FEEDBACK, total: PENDING_FEEDBACK.length });
    if (method === 'GET' && p === '/api/v1/feedback/all') return ok({ items: PENDING_FEEDBACK, total: PENDING_FEEDBACK.length });
    if (method === 'POST' && /^\/api\/v1\/feedback\/\d+\/(approve|reject)$/.test(p)) return ok(null, '已处理');

    // ---- 模型测试（演示不深入，最小兜底） ----
    if (method === 'GET' && p === '/api/v1/test/tasks') return ok([]);
    if (method === 'GET' && p === '/api/v1/test/logs') return ok([]);
    if (method === 'POST' && p === '/api/v1/test/run') return ok({ task_id: 'mock-task-demo' });
    if (method === 'GET' && /^\/api\/v1\/test\/[^/]+\/status$/.test(p)) {
      return ok({ task_id: 'mock-task-demo', status: 'completed', progress: 100, result: { total: 18, success: 17, accuracy: 0.944 } });
    }

    // ---- 工人端登录 ----
    if (method === 'POST' && p === '/api/v1/worker/login') {
      var bb = body || {};
      var nm = (bb.worker_name || 'worker_照明开关_1').trim();
      var w = {
        id: 268, name: nm, phone: '138000010000',
        company: '区域中心1', department: '区域中心1维修单位',
        certs: '["低压电工证"]'
      };
      return ok({ worker: w }, '登录成功，欢迎 ' + nm);
    }

    // ---- 兜底：任何未覆盖的 API ----
    return { code: 0, message: '演示模式：该接口未提供数据', data: null };
  }

  // ---------- XMLHttpRequest 拦截 ----------
  var RealXHR = window.XMLHttpRequest;
  function MockXHR() {
    var self = this;
    this._method = 'GET';
    this._url = '';
    this._headers = {};
    this._readyState = 0;
    this._status = 0;
    this._response = '';
    this._responseText = '';
    this._responseType = '';
    this._timeout = 0;
    this.onreadystatechange = null;
    this.onload = null;
    this.onloadend = null;
    this.onerror = null;
    this.onabort = null;
    this.ontimeout = null;
    this.withCredentials = false;
    this.upload = {};
    this.responseText = '';
    this.response = '';
    this.statusText = '';
    this.readyState = 0;

    this._setReady = function (s) {
      self.readyState = s;
      self._readyState = s;
      if (typeof self.onreadystatechange === 'function') {
        try { self.onreadystatechange(new Event('readystatechange')); } catch (e) {}
      }
    };
    this._finish = function (result) {
      self._status = 200; self.status = 200;
      self.statusText = 'OK';
      self._responseText = JSON.stringify(result);
      self.responseText = self._responseText;
      self._response = self._responseText;
      self.response = self._response;
      self._setReady(2); self._setReady(3); self._setReady(4);
      if (typeof self.onload === 'function') {
        try { self.onload(new Event('load')); } catch (e) {}
      }
      if (typeof self.onloadend === 'function') {
        try { self.onloadend(new Event('loadend')); } catch (e) {}
      }
    };
  }
  MockXHR.prototype.open = function (method, url) { this._method = String(method || 'GET').toUpperCase(); this._url = url; this._setReady(1); };
  MockXHR.prototype.setRequestHeader = function (k, v) { this._headers[k] = v; };
  MockXHR.prototype.abort = function () {
    if (typeof this.onabort === 'function') { try { this.onabort(new Event('abort')); } catch (e) {} }
  };
  MockXHR.prototype.getAllResponseHeaders = function () { return 'content-type: application/json\r\n'; };
  MockXHR.prototype.getResponseHeader = function (k) {
    return String(k).toLowerCase() === 'content-type' ? 'application/json' : null;
  };
  MockXHR.prototype.send = function (payload) {
    var self = this;
    var body = null;
    if (payload && typeof payload === 'string') {
      try { body = JSON.parse(payload); } catch (e) { body = null; }
    }
    var result;
    try { result = route(this._method, this._url, body); }
    catch (err) { result = { code: 1500, message: '演示模式异常: ' + err.message, data: null }; }
    // 随机 350–900ms 延迟，模拟真实网络与推理耗时
    setTimeout(function () { self._finish(result); }, rand(350, 900));
  };

  window.XMLHttpRequest = MockXHR;

  // 控制台提示，方便确认演示模式已生效
  console.log('%c[演示模式] 智能工单系统 mock 已启用（输入输出为固定剧本，不连接真实后端）',
    'color:#67C23A;font-weight:bold');
})();
