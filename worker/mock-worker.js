/* ============================================================
 * 智能工单系统 —— 演示模式 Mock（工人端）
 *
 * 拦截 XMLHttpRequest，固定剧本：
 *   - 登录：任意姓名 + 任意密码均可进入（密码框填任意数字即可）
 *   - 工单列表：2 条指派工单（一条待处理、一条处理中）
 *   - 接单 / 完成按钮会真实改变状态（页面内内存态）
 *
 * 2026-09-07 由砚生成
 * ============================================================ */
(function () {
  'use strict';
  if (window.__MOCK_API_ACTIVE__) return;
  window.__MOCK_API_ACTIVE__ = true;

  var rand = function (a, b) { return a + Math.random() * (b - a); };
  var nowStr = function () {
    var d = new Date(), p = function (n) { return (n < 10 ? '0' : '') + n; };
    return d.getFullYear() + '-' + p(d.getMonth() + 1) + '-' + p(d.getDate()) +
      'T' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
  };

  function worker(name) {
    return {
      id: 268, name: name || 'worker_照明开关_1', phone: '138000010000',
      company: '区域中心1', department: '区域中心1维修单位', certs: '["低压电工证"]'
    };
  }

  // 工人名下的工单（内存态：接单/完成会真的改状态）
  var ORDERS = [
    {
      id: 44, order_no: 'WO20260907000001',
      accept_time: '2026-09-07T10:05:00',
      user_input: '家里客厅灯开关坏了，按了没反应',
      sub_category: '电气电路', problem: '照明开关',
      property_company: '区域中心1', maintenance_unit: '区域中心1维修单位',
      priority: '72小时内完成', required_cert: '低压电工证',
      target_dept_semantic: '电力维修组', worker_id: 268, status: 'PENDING',
      address: '示例路41弄12号603室', contact: '13800001234',
      created_at: '2026-09-07T10:04:30', updated_at: '2026-09-07T10:04:30',
      reporter_name: '示例住户', reporter_phone: '13800001234',
      worker_info: worker()
    },
    {
      id: 43, order_no: 'WO20260906000002',
      accept_time: '2026-09-06T09:14:00',
      user_input: '家里突然全部断电，邻居家正常',
      sub_category: '电气电路', problem: '断电',
      property_company: '区域中心1', maintenance_unit: '区域中心1维修单位',
      priority: '半小时到现场', required_cert: '低压电工证',
      target_dept_semantic: '电力维修组', worker_id: 268, status: 'processing',
      address: '示例路1299号8号楼302室', contact: '13800005678',
      created_at: '2026-09-06T09:13:30', updated_at: '2026-09-06T09:20:00',
      reporter_name: '示例住户B', reporter_phone: '13800005678',
      worker_info: worker()
    }
  ];

  function route(method, url, body) {
    var p = url.replace(/^https?:\/\/[^/]+/, '').split('?')[0];
    var ok = function (data, message) { return { code: 0, message: message || '操作成功', data: data }; };
    var m;

    if (method === 'POST' && p === '/api/v1/worker/login') {
      var nm = ((body && body.worker_name) || 'worker_照明开关_1').trim() || 'worker_照明开关_1';
      return ok({ worker: worker(nm) }, '登录成功，欢迎 ' + nm);
    }

    if (method === 'GET' && p === '/api/v1/work-orders') {
      var qi = url.indexOf('?'), q = {};
      if (qi >= 0) url.slice(qi + 1).split('&').forEach(function (kv) {
        var b = kv.split('='); q[decodeURIComponent(b[0])] = decodeURIComponent(b[1] || '');
      });
      var page = parseInt(q.page || '1', 10) || 1;
      var limit = parseInt(q.limit || '20', 10) || 20;
      var arr = ORDERS.slice();
      if (q.status) arr = arr.filter(function (o) { return o.status.toUpperCase() === q.status.toUpperCase(); });
      var items = arr.slice((page - 1) * limit, page * limit);
      return ok({ items: items, total: arr.length, page: page, limit: limit, total_pages: Math.ceil(arr.length / limit) || 1 });
    }

    m = p.match(/^\/api\/v1\/work-order\/([^/]+)$/);
    if (method === 'GET' && m) {
      for (var i = 0; i < ORDERS.length; i++) if (ORDERS[i].order_no === m[1]) return ok(ORDERS[i]);
      return { code: 1004, message: '工单不存在', data: null };
    }

    m = p.match(/^\/api\/v1\/work-order\/([^/]+)\/(start|worker-complete)$/);
    if (method === 'POST' && m) {
      for (var j = 0; j < ORDERS.length; j++) {
        if (ORDERS[j].order_no === m[1]) {
          ORDERS[j].status = (m[2] === 'start') ? 'processing' : 'worker_completed';
          ORDERS[j].updated_at = nowStr();
          return ok(ORDERS[j], '状态已更新为 ' + ORDERS[j].status);
        }
      }
      return { code: 1004, message: '工单不存在', data: null };
    }

    if (method === 'GET' && p === '/api/v1/health') return ok({ status: 'running', version: '2.0.0-demo' });
    return { code: 0, message: '演示模式：该接口未提供数据', data: null };
  }

  // ---- XMLHttpRequest 拦截（与主端 mock 同一套实现） ----
  function MockXHR() {
    var self = this;
    this._method = 'GET'; this._url = ''; this._headers = {};
    this.readyState = 0; this.status = 0; this.statusText = '';
    this.responseText = ''; this.response = ''; this._responseType = '';
    this.timeout = 0; this.withCredentials = false; this.upload = {};
    this.onreadystatechange = null; this.onload = null; this.onloadend = null;
    this.onerror = null; this.onabort = null; this.ontimeout = null;

    this._setReady = function (s) {
      self.readyState = s;
      if (typeof self.onreadystatechange === 'function') {
        try { self.onreadystatechange(new Event('readystatechange')); } catch (e) {}
      }
    };
    this._finish = function (result) {
      self.status = 200; self.statusText = 'OK';
      self.responseText = JSON.stringify(result);
      self.response = self.responseText;
      self._setReady(2); self._setReady(3); self._setReady(4);
      if (typeof self.onload === 'function') { try { self.onload(new Event('load')); } catch (e) {} }
      if (typeof self.onloadend === 'function') { try { self.onloadend(new Event('loadend')); } catch (e) {} }
    };
  }
  MockXHR.prototype.open = function (method, url) { this._method = String(method || 'GET').toUpperCase(); this._url = url; this._setReady(1); };
  MockXHR.prototype.setRequestHeader = function (k, v) { this._headers[k] = v; };
  MockXHR.prototype.abort = function () { if (typeof this.onabort === 'function') { try { this.onabort(new Event('abort')); } catch (e) {} } };
  MockXHR.prototype.getAllResponseHeaders = function () { return 'content-type: application/json\r\n'; };
  MockXHR.prototype.getResponseHeader = function (k) { return String(k).toLowerCase() === 'content-type' ? 'application/json' : null; };
  MockXHR.prototype.send = function (payload) {
    var self = this, body = null;
    if (payload && typeof payload === 'string') { try { body = JSON.parse(payload); } catch (e) {} }
    var result;
    try { result = route(this._method, this._url, body); }
    catch (err) { result = { code: 1500, message: '演示模式异常: ' + err.message, data: null }; }
    setTimeout(function () { self._finish(result); }, rand(350, 900));
  };

  window.XMLHttpRequest = MockXHR;
  console.log('%c[演示模式] 工人端 mock 已启用（任意姓名+密码可登录）', 'color:#67C23A;font-weight:bold');
})();
