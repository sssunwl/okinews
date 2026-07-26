/* 活動年曆頁 */
(function () {
  'use strict';

  var escapeHTML = OKIP.escapeHTML, safeURL = OKIP.safeURL, fmtDate = OKIP.fmtDate;
  var dataNode = document.getElementById('eventData');
  if (!dataNode) return;

  var EVENTS = JSON.parse(dataNode.textContent).map(function (event, index) {
    event._index = index;
    return event;
  });
  var MONTHS = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'];
  var state = { year: 0, month: 0, selectedDate: null, filter: 'all', search: '', limit: 10 };

  function eventId(event) {
    return [event.source, event.date_start, event.url || event.name_zh || event.name].join('|');
  }
  function displayName(event) { return event.name_zh || event.name || '未命名活動'; }
  function sourceName(event) {
    if (event.source === 'today_is') return 'OKIP 文化日';
    if (event.source === 'okinawastory') return 'おきなわ物語';
    return 'Visit Okinawa';
  }
  function planItem(event) {
    return {
      id: eventId(event),
      title: displayName(event),
      date: event.date_start,
      href: new URL(location.pathname + '#event-' + encodeURIComponent(eventId(event)), location.href).href
    };
  }

  function initDate() {
    var today = OKIP.tokyoToday();
    var currentYear = Number(today.slice(0, 4));
    var currentMonth = Number(today.slice(5, 7)) - 1;
    var years = [];
    EVENTS.forEach(function (event) {
      var year = Number(String(event.date_start || '').slice(0, 4));
      if (year && years.indexOf(year) < 0) years.push(year);
    });
    years.sort();
    state.year = years.indexOf(currentYear) >= 0 ? currentYear : (years[years.length - 1] || currentYear);
    state.month = state.year === currentYear ? currentMonth : 0;
    var yearSelect = document.getElementById('yearSelect');
    yearSelect.innerHTML = years.map(function (year) {
      return '<option value="' + year + '">' + year + '年</option>';
    }).join('');
    yearSelect.value = String(state.year);
    document.getElementById('monthSelect').innerHTML = MONTHS.map(function (month, index) {
      return '<option value="' + index + '">' + month + '</option>';
    }).join('');
    document.getElementById('monthSelect').value = String(state.month);
  }

  function monthKey() {
    return state.year + '-' + String(state.month + 1).padStart(2, '0');
  }

  var BY_DATE = {};
  EVENTS.forEach(function (event) {
    if (!BY_DATE[event.date_start]) BY_DATE[event.date_start] = [];
    BY_DATE[event.date_start].push(event);
  });

  function renderCalendar() {
    var first = new Date(state.year, state.month, 1);
    var last = new Date(state.year, state.month + 1, 0);
    var today = OKIP.tokyoToday();
    var html = '';
    var prevLast = new Date(state.year, state.month, 0).getDate();
    for (var i = first.getDay() - 1; i >= 0; i--) {
      html += '<button class="cal-day other" type="button" disabled>' + (prevLast - i) + '</button>';
    }
    for (var day = 1; day <= last.getDate(); day++) {
      var iso = monthKey() + '-' + String(day).padStart(2, '0');
      var events = BY_DATE[iso] || [];
      var dots = events.slice(0, 4).map(function (event) {
        return '<i class="' + (event.source === 'today_is' ? 'culture' : '') + '"></i>';
      }).join('');
      html += '<button class="cal-day' + (iso === today ? ' today' : '') +
        (iso === state.selectedDate ? ' selected' : '') + '" type="button" data-date="' + iso +
        '" aria-label="' + (state.month + 1) + '月' + day + '日，' + events.length + '個活動"><span>' +
        day + '</span><span class="date-dots">' + dots + '</span></button>';
    }
    var used = first.getDay() + last.getDate();
    for (var tail = 1; tail <= 42 - used; tail++) {
      html += '<button class="cal-day other" type="button" disabled>' + tail + '</button>';
    }
    document.getElementById('calGrid').innerHTML = html;
    document.getElementById('yearSelect').value = String(state.year);
    document.getElementById('monthSelect').value = String(state.month);
  }

  function filteredEvents() {
    var query = state.search.trim().toLowerCase();
    var events;
    if (query) {
      events = EVENTS.filter(function (event) {
        return [event.name, event.name_zh, event.description, event.category, event.location]
          .join(' ').toLowerCase().indexOf(query) >= 0;
      });
    } else {
      events = EVENTS.filter(function (event) {
        return String(event.date_start || '').indexOf(monthKey()) === 0;
      });
      if (state.selectedDate) {
        events = events.filter(function (event) { return event.date_start === state.selectedDate; });
      }
    }
    if (state.filter === 'activity') events = events.filter(function (e) { return e.source !== 'today_is'; });
    if (state.filter === 'today_is') events = events.filter(function (e) { return e.source === 'today_is'; });
    if (state.filter === 'saved') events = events.filter(function (e) { return OKIP.inPlan(eventId(e)); });
    return events.sort(function (a, b) { return String(a.date_start).localeCompare(String(b.date_start)); });
  }

  function eventCard(event, index) {
    var culture = event.source === 'today_is';
    var end = event.date_end && event.date_end !== event.date_start ? '～' + fmtDate(event.date_end) : '';
    // 只連我們自己的活動介紹頁（有找到官方網站才會有）；絕不直接連到其他旅遊平台。
    var detailHref = event._detail_slug ? escapeHTML(event._detail_slug) + '/' : '';
    var saved = OKIP.inPlan(eventId(event));
    var title = detailHref
      ? '<a href="' + detailHref + '">' + escapeHTML(displayName(event)) + '</a>'
      : escapeHTML(displayName(event));
    var ja = event.name && event.name !== displayName(event)
      ? '<div class="event-ja">' + escapeHTML(event.name) + '</div>' : '';
    var loc = event.location
      ? '<p class="event-location">📍 ' + escapeHTML(event.location) +
        (event.price ? '<span class="event-price">' + escapeHTML(event.price) + '</span>' : '') + '</p>' : '';
    var source = culture ? '' : '<p class="event-source-note">資料來源：' + escapeHTML(sourceName(event)) + '</p>';
    return '<article class="event-card' + (culture ? ' culture' : '') +
      '" id="event-' + escapeHTML(encodeURIComponent(eventId(event))) +
      '" style="animation-delay:' + Math.min(index, 10) * 0.025 + 's">' +
      '<div class="event-date">' + escapeHTML(fmtDate(event.date_start)) +
      '<small>' + escapeHTML(end || event.category || '活動') + '</small></div>' +
      '<div class="event-body"><span class="event-source">' + escapeHTML(sourceName(event)) +
      '</span><h4>' + title + '</h4>' + ja +
      (event.description ? '<p class="event-desc">' + escapeHTML(event.description) + '</p>' : '') + loc + source + '</div>' +
      '<div class="event-actions">' +
      '<button class="save-btn' + (saved ? ' saved' : '') + '" type="button" data-save-index="' + event._index +
      '" aria-label="' + (saved ? '從行程移除' : '加入我的行程') + '">' + (saved ? '♥' : '♡') + '</button>' +
      (detailHref ? '<a class="source-btn" href="' + detailHref + '" aria-label="查看活動介紹">→</a>' : '') +
      '</div></article>';
  }

  function renderEvents() {
    var events = filteredEvents();
    var shown = events.slice(0, state.limit);
    var heading = state.search ? '「' + state.search + '」搜尋結果'
      : state.selectedDate ? fmtDate(state.selectedDate, true)
        : state.year + '年' + (state.month + 1) + '月活動';
    document.getElementById('eventHeading').textContent = heading;
    document.getElementById('eventCount').textContent = events.length + ' 筆';
    document.getElementById('eventList').innerHTML = shown.length
      ? shown.map(eventCard).join('')
      : '<div class="empty-state"><strong>這個條件暫時沒有活動</strong>換個月份或關鍵字再找找看。</div>';
    var more = document.getElementById('moreBtn');
    more.hidden = shown.length >= events.length;
    more.textContent = '再看一些（還有 ' + (events.length - shown.length) + ' 筆）';
  }

  function renderAll() { renderCalendar(); renderEvents(); }

  function changeMonth(delta) {
    state.month += delta;
    if (state.month < 0) { state.month = 11; state.year--; }
    if (state.month > 11) { state.month = 0; state.year++; }
    if (!document.querySelector('#yearSelect option[value="' + state.year + '"]')) {
      state.year -= delta > 0 ? 1 : -1;
      state.month = delta > 0 ? 11 : 0;
    }
    state.selectedDate = null; state.search = ''; state.limit = 10;
    document.getElementById('eventSearch').value = '';
    renderAll();
  }

  function runSearch(query) {
    state.search = String(query || '').trim();
    state.selectedDate = null; state.filter = 'all'; state.limit = 10;
    document.getElementById('eventSearch').value = state.search;
    var tabs = document.querySelectorAll('.filter-tab');
    for (var i = 0; i < tabs.length; i++) tabs[i].classList.toggle('active', tabs[i].dataset.filter === 'all');
    renderEvents();
  }

  document.getElementById('eventSearch').addEventListener('input', function (event) {
    state.search = event.target.value; state.selectedDate = null; state.limit = 10; renderEvents();
  });
  document.querySelectorAll('.filter-tab').forEach(function (button) {
    button.addEventListener('click', function () {
      state.filter = button.dataset.filter; state.search = ''; state.selectedDate = null; state.limit = 10;
      document.getElementById('eventSearch').value = '';
      document.querySelectorAll('.filter-tab').forEach(function (tab) {
        tab.classList.toggle('active', tab === button);
      });
      renderEvents();
    });
  });
  document.getElementById('calGrid').addEventListener('click', function (event) {
    var button = event.target.closest('[data-date]');
    if (!button) return;
    state.selectedDate = state.selectedDate === button.dataset.date ? null : button.dataset.date;
    state.search = ''; state.limit = 10;
    document.getElementById('eventSearch').value = '';
    renderAll();
  });
  document.getElementById('eventList').addEventListener('click', function (event) {
    var button = event.target.closest('[data-save-index]');
    if (!button) return;
    OKIP.togglePlan(planItem(EVENTS[Number(button.dataset.saveIndex)]));
    renderEvents();
  });
  document.getElementById('yearSelect').addEventListener('change', function (event) {
    state.year = Number(event.target.value); state.selectedDate = null; renderAll();
  });
  document.getElementById('monthSelect').addEventListener('change', function (event) {
    state.month = Number(event.target.value); state.selectedDate = null; renderAll();
  });
  document.getElementById('prevMonth').addEventListener('click', function () { changeMonth(-1); });
  document.getElementById('nextMonth').addEventListener('click', function () { changeMonth(1); });
  document.getElementById('moreBtn').addEventListener('click', function () { state.limit += 10; renderEvents(); });
  document.addEventListener('okip:plan-change', function () {
    if (state.filter === 'saved') renderEvents();
  });

  initDate();
  renderAll();

  var initial = new URLSearchParams(location.search).get('q');
  if (initial) runSearch(initial);
})();
