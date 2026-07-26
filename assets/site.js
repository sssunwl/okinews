/* OKIPLAYGROUND 共用腳本：工具函式、我的行程、導覽 */
(function () {
  'use strict';

  var PLAN_KEY = 'okiplayground-plan-v2';
  var WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];

  function escapeHTML(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char];
    });
  }

  function safeURL(value) {
    try {
      var url = new URL(value);
      return ['http:', 'https:'].indexOf(url.protocol) >= 0 ? url.href : '';
    } catch (err) {
      return '';
    }
  }

  function tokyoToday() {
    var parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit'
    }).formatToParts(new Date());
    function get(type) {
      for (var i = 0; i < parts.length; i++) if (parts[i].type === type) return parts[i].value;
      return '';
    }
    return get('year') + '-' + get('month') + '-' + get('day');
  }

  function fmtDate(iso, withYear) {
    if (!iso) return '';
    var date = new Date(iso + 'T00:00:00');
    if (isNaN(date)) return '';
    return (withYear ? date.getFullYear() + '年' : '') +
      (date.getMonth() + 1) + '/' + date.getDate() + '（' + WEEKDAYS[date.getDay()] + '）';
  }

  /* ── 我的行程：存完整摘要，任何頁面都能顯示 ── */
  function loadPlan() {
    try {
      var value = JSON.parse(localStorage.getItem(PLAN_KEY) || '[]');
      return Array.isArray(value) ? value.filter(function (item) { return item && item.id; }) : [];
    } catch (err) {
      return [];
    }
  }

  var plan = loadPlan();

  function savePlan() {
    try { localStorage.setItem(PLAN_KEY, JSON.stringify(plan)); } catch (err) { /* 私密模式忽略 */ }
    updatePlanUI();
    renderDrawer();
  }

  function inPlan(id) {
    return plan.some(function (item) { return item.id === id; });
  }

  function togglePlan(item) {
    if (!item || !item.id) return false;
    if (inPlan(item.id)) {
      plan = plan.filter(function (saved) { return saved.id !== item.id; });
    } else {
      plan = plan.concat([{ id: item.id, title: item.title, date: item.date || '', href: item.href || '' }]);
    }
    savePlan();
    return inPlan(item.id);
  }

  function updatePlanUI() {
    var nodes = document.querySelectorAll('[data-plan-count]');
    for (var i = 0; i < nodes.length; i++) nodes[i].textContent = String(plan.length);
    document.dispatchEvent(new CustomEvent('okip:plan-change'));
  }

  function renderDrawer() {
    var list = document.getElementById('drawerList');
    if (!list) return;
    var items = plan.slice().sort(function (a, b) {
      return String(a.date || '').localeCompare(String(b.date || ''));
    });
    list.innerHTML = items.length ? items.map(function (item) {
      var href = safeURL(item.href) || (item.href && item.href.charAt(0) !== 'j' ? item.href : '');
      var title = href
        ? '<a href="' + escapeHTML(href) + '">' + escapeHTML(item.title) + '</a>'
        : escapeHTML(item.title);
      return '<article class="saved-card"><small>' + escapeHTML(fmtDate(item.date, true) || '日期未定') +
        '</small><strong>' + title + '</strong>' +
        '<button class="saved-remove" type="button" data-remove-id="' + escapeHTML(item.id) + '">從行程移除</button></article>';
    }).join('') :
      '<div class="drawer-empty"><span>♡</span><strong>行程還是空的</strong><p>在活動卡片按下愛心，就會先存到這裡。</p></div>';
    var share = document.getElementById('drawerShare');
    if (share) share.hidden = !items.length;
  }

  function setDrawer(open) {
    var drawer = document.getElementById('planDrawer');
    if (!drawer) return;
    drawer.classList.toggle('open', open);
    var overlay = document.getElementById('drawerOverlay');
    if (overlay) overlay.classList.toggle('open', open);
    drawer.setAttribute('aria-hidden', String(!open));
    document.body.classList.toggle('drawer-lock', open);
    if (open) drawer.querySelector('.drawer-close').focus();
  }

  /* ── 導覽 ── */
  function initNav() {
    var toggle = document.querySelector('[data-menu-toggle]');
    var dropNav = document.getElementById('dropNav');
    if (toggle && dropNav) {
      toggle.addEventListener('click', function () {
        var open = dropNav.hasAttribute('hidden');
        if (open) dropNav.removeAttribute('hidden'); else dropNav.setAttribute('hidden', '');
        toggle.setAttribute('aria-expanded', String(open));
      });
    }
    var header = document.getElementById('siteHeader');
    if (header) {
      window.addEventListener('scroll', function () {
        header.classList.toggle('scrolled', window.scrollY > 12);
      }, { passive: true });
    }
  }

  function initDrawer() {
    var openers = document.querySelectorAll('.saved-open');
    for (var i = 0; i < openers.length; i++) {
      openers[i].addEventListener('click', function () { setDrawer(true); });
    }
    var close = document.querySelector('.drawer-close');
    if (close) close.addEventListener('click', function () { setDrawer(false); });
    var overlay = document.getElementById('drawerOverlay');
    if (overlay) overlay.addEventListener('click', function () { setDrawer(false); });
    var list = document.getElementById('drawerList');
    if (list) {
      list.addEventListener('click', function (event) {
        var button = event.target.closest('[data-remove-id]');
        if (!button) return;
        plan = plan.filter(function (saved) { return saved.id !== button.dataset.removeId; });
        savePlan();
      });
    }
    var share = document.getElementById('drawerShare');
    if (share) {
      share.addEventListener('click', function () {
        var payload = btoa(unescape(encodeURIComponent(JSON.stringify(plan))));
        var url = location.origin + location.pathname.replace(/[^/]*$/, '') + '?plan=' + encodeURIComponent(payload);
        if (navigator.clipboard) navigator.clipboard.writeText(url);
        share.textContent = '連結已複製';
        setTimeout(function () { share.textContent = '複製行程連結'; }, 2000);
      });
    }
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') setDrawer(false);
    });
  }

  function importSharedPlan() {
    var payload = new URLSearchParams(location.search).get('plan');
    if (!payload) return;
    try {
      var incoming = JSON.parse(decodeURIComponent(escape(atob(payload))));
      if (!Array.isArray(incoming)) return;
      incoming.forEach(function (item) {
        if (item && item.id && !inPlan(item.id)) plan = plan.concat([item]);
      });
      savePlan();
    } catch (err) { /* 連結壞掉就當沒事 */ }
  }

  window.OKIP = {
    escapeHTML: escapeHTML,
    safeURL: safeURL,
    tokyoToday: tokyoToday,
    fmtDate: fmtDate,
    WEEKDAYS: WEEKDAYS,
    inPlan: inPlan,
    togglePlan: togglePlan,
    getPlan: function () { return plan.slice(); }
  };

  initNav();
  initDrawer();
  importSharedPlan();
  updatePlanUI();
  renderDrawer();
})();
