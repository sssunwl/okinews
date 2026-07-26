/* 首頁：今日看板 + 近期活動 + 一週天氣 */
(function () {
  'use strict';

  var escapeHTML = OKIP.escapeHTML, safeURL = OKIP.safeURL, fmtDate = OKIP.fmtDate;

  function readJSON(id) {
    var node = document.getElementById(id);
    if (!node) return [];
    try { return JSON.parse(node.textContent) || []; } catch (err) { return []; }
  }

  var EVENTS = readJSON('eventData');
  var WEATHER = readJSON('weatherData');
  var NEWS = readJSON('newsData');
  var today = OKIP.tokyoToday();

  function displayName(event) { return event.name_zh || event.name || '未命名活動'; }
  function truncate(text, max) {
    text = String(text || '');
    return text.length > max ? text.slice(0, max).trim() + '…' : text;
  }
  function eventId(event) {
    return [event.source, event.date_start, event.url || event.name_zh || event.name].join('|');
  }

  /* ── 今日日期 ── */
  var dateEl = document.getElementById('todayLabel');
  if (dateEl) {
    var d = new Date(today + 'T00:00:00');
    dateEl.textContent = '沖繩時間 ' + (d.getMonth() + 1) + '月' + d.getDate() + '日 ' +
      OKIP.WEEKDAYS[d.getDay()] + '曜日';
  }

  /* ── 今日天氣 ── */
  var todayWx = WEATHER.filter(function (day) { return day.date === today; })[0] || WEATHER[0];
  var wxNow = document.getElementById('wxNow');
  if (wxNow) {
    if (todayWx) {
      wxNow.innerHTML =
        '<div class="wx-now-main"><span class="wx-now-icon">' + escapeHTML(todayWx.icon) + '</span>' +
        '<span class="wx-now-temp"><strong>' + escapeHTML(todayWx.temp_max) + '°</strong>' +
        '<small>最低 ' + escapeHTML(todayWx.temp_min) + '°</small></span></div>' +
        '<ul class="wx-now-meta">' +
        '<li><span>降雨機率</span><strong>' + escapeHTML(todayWx.rain_chance) + '%</strong></li>' +
        '<li><span>紫外線</span><strong>' + escapeHTML(todayWx.uv) + '・' + escapeHTML(todayWx.uv_label) + '</strong></li>' +
        '</ul>' +
        '<p class="wx-now-tip">' + escapeHTML(weatherTip(todayWx)) + '</p>';
    } else {
      wxNow.innerHTML = '<div class="empty-state"><strong>天氣資料整理中</strong>晚點再回來看看。</div>';
    }
  }

  function weatherTip(day) {
    if (day.rain_chance >= 70) return '降雨機率高，先在同一區備一個室內行程，別跨區追晴。';
    if (day.uv >= 8) return '紫外線很強，防曬、帽子與水一樣都不要省。';
    if (day.temp_max >= 31) return '偏熱，戶外行程盡量安排在上午或傍晚。';
    return '天氣還算穩定，適合把戶外行程排滿一點。';
  }

  /* ── 一週天氣 ── */
  var strip = document.getElementById('weatherStrip');
  if (strip) {
    strip.innerHTML = WEATHER.length ? WEATHER.map(function (day) {
      var dt = new Date(day.date + 'T00:00:00');
      var weekend = dt.getDay() === 0 || dt.getDay() === 6;
      return '<article class="wx-card' + (day.date === today ? ' today' : '') + '">' +
        '<span class="wx-date' + (weekend ? ' weekend' : '') + '">' + (dt.getMonth() + 1) + '/' + dt.getDate() +
        '（' + escapeHTML(day.weekday) + '）</span>' +
        '<span class="wx-icon">' + escapeHTML(day.icon) + '</span>' +
        '<span class="wx-temp"><strong>' + escapeHTML(day.temp_max) + '°</strong><small>' + escapeHTML(day.temp_min) + '°</small></span>' +
        '<span class="wx-rain">💧 ' + escapeHTML(day.rain_chance) + '%</span>' +
        '<span class="wx-uv">UV ' + escapeHTML(day.uv) + '・' + escapeHTML(day.uv_label) + '</span>' +
        '</article>';
    }).join('') : '<div class="empty-state"><strong>天氣資料整理中</strong>晚點再回來看看。</div>';
  }

  /* ── 今天是什麼日子 ── */
  var cultureEl = document.getElementById('todayCulture');
  if (cultureEl) {
    var culture = EVENTS.filter(function (event) {
      return event.source === 'today_is' && event.date_start >= today;
    }).sort(function (a, b) { return a.date_start.localeCompare(b.date_start); })[0];
    if (culture) {
      var isToday = culture.date_start === today;
      cultureEl.innerHTML = '<span class="today-tag">' + (isToday ? '今天是' : fmtDate(culture.date_start)) + '</span>' +
        '<strong>' + escapeHTML(displayName(culture)) + '</strong>' +
        (culture.description ? '<p>' + escapeHTML(culture.description) + '</p>' : '');
    } else {
      cultureEl.hidden = true;
    }
  }

  /* ── 今日新聞 ── */
  var newsEl = document.getElementById('todayNews');
  if (newsEl) {
    newsEl.innerHTML = NEWS.length ? NEWS.slice(0, 3).map(function (item) {
      return '<li><a href="' + escapeHTML(newsEl.dataset.newsHref || 'news/') + '">' +
        (item.alert ? '<span class="news-alert">要注意</span>' : '') +
        escapeHTML(item.title) + '</a><small>' + escapeHTML(item.source || '') + '</small></li>';
    }).join('') : '<li class="news-empty">今日新聞整理中。</li>';
  }

  /* ── 近期活動 ── */
  var pickGrid = document.getElementById('pickGrid');
  if (pickGrid) {
    var upcoming = EVENTS.filter(function (event) {
      return event.source !== 'today_is' && event.date_start >= today;
    }).sort(function (a, b) { return a.date_start.localeCompare(b.date_start); }).slice(0, 4);
    var icons = ['☀️', '🥁', '🌊', '🌙'];
    pickGrid.innerHTML = upcoming.length ? upcoming.map(function (event, index) {
      var img = safeURL(event.image);
      var style = img ? ' style="background-image:url(\'' + escapeHTML(img) + '\')"' : '';
      var loc = event.location ? '<p class="pick-loc">📍 ' + escapeHTML(event.location) + '</p>' : '';
      return '<article class="pick-card' + (img ? ' has-image' : '') +
        '" data-pick-id="' + escapeHTML(eventId(event)) + '" tabindex="0"' + style + '>' +
        '<span class="pick-no">0' + (index + 1) + '・' + escapeHTML(fmtDate(event.date_start)) + '</span>' +
        '<span class="pick-arrow">↗</span>' + (img ? '' : '<span class="pick-icon">' + icons[index] + '</span>') +
        '<h3>' + escapeHTML(displayName(event)) + '</h3>' +
        '<p>' + escapeHTML(truncate(event.description, 46) || '點開看活動詳情與官方資訊。') + '</p>' + loc +
        '</article>';
    }).join('') : '<div class="empty-state"><strong>近期活動整理中</strong>晚點再回來看看。</div>';

    var eventsHref = pickGrid.dataset.eventsHref || 'events/';
    function openPick(card) {
      if (!card) return;
      location.href = eventsHref + '?q=' + encodeURIComponent(card.querySelector('h3').textContent);
    }
    pickGrid.addEventListener('click', function (event) {
      openPick(event.target.closest('[data-pick-id]'));
    });
    pickGrid.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        openPick(event.target.closest('[data-pick-id]'));
      }
    });
  }

  /* ── 1-12 月預覽列：滑過／focus 換文字，觸控裝置直接點進去看當月詳細 ── */
  var monthRow = document.getElementById('monthRow');
  var monthPreview = document.getElementById('monthPreview');
  if (monthRow && monthPreview) {
    var showPreview = function (tile) {
      if (!tile) return;
      monthPreview.textContent = tile.dataset.blurb || '';
    };
    monthRow.addEventListener('mouseover', function (event) {
      showPreview(event.target.closest('.month-tile'));
    });
    monthRow.addEventListener('focusin', function (event) {
      showPreview(event.target.closest('.month-tile'));
    });
  }
})();
