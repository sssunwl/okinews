/* 內容區塊：多維 tag 篩選（交集）。一個頁面可以有多組獨立的篩選器＋格子
   （例如 /goods/ 同時有好物卡片格跟文章格），靠 data-target 對應各自的 grid。 */
(function () {
  'use strict';

  var blocks = document.querySelectorAll('.filter-block[data-target]');
  if (!blocks.length) return;

  blocks.forEach(function (filters) {
    var grid = document.getElementById(filters.dataset.target);
    if (!grid) return;
    var empty = document.getElementById(filters.dataset.target.replace(/Grid$/, 'Empty'));
    var active = [];

    function apply() {
      var cards = grid.children;
      var shown = 0;
      for (var i = 0; i < cards.length; i++) {
        var tags = (cards[i].dataset.tags || '').split('|');
        var match = active.every(function (tag) { return tags.indexOf(tag) >= 0; });
        cards[i].hidden = !match;
        if (match) shown++;
      }
      if (empty) empty.hidden = shown > 0;

      var chips = filters.querySelectorAll('.tag-chip');
      for (var j = 0; j < chips.length; j++) {
        var tag = chips[j].dataset.tag;
        chips[j].classList.toggle('active', tag ? active.indexOf(tag) >= 0 : active.length === 0);
        chips[j].setAttribute('aria-pressed', String(chips[j].classList.contains('active')));
      }
    }

    filters.addEventListener('click', function (event) {
      var chip = event.target.closest('.tag-chip');
      if (!chip) return;
      var tag = chip.dataset.tag;
      if (!tag) {
        active = [];
      } else {
        var index = active.indexOf(tag);
        if (index >= 0) active.splice(index, 1); else active.push(tag);
      }
      apply();
    });

    apply();
  });

  /* 海況卡片的逐時時間軸：點鐘點按鈕，把卡片上面顯示的風／浪／潮位／結論換成那個時段的資料。
     所有鐘點的資料在 build 時就已經算好、寫進按鈕的 data-point，這裡純粹是切換顯示，不打任何 API。 */
  document.querySelectorAll('[data-cond-timeline]').forEach(function (timeline) {
    var card = timeline.closest('.cond-card');
    if (!card) return;
    var badge = card.querySelector('[data-cond-badge]');
    var wind = card.querySelector('[data-cond-wind]');
    var wave = card.querySelector('[data-cond-wave]');
    var tide = card.querySelector('[data-cond-tide]');
    var reason = card.querySelector('[data-cond-reason]');

    timeline.addEventListener('click', function (event) {
      var button = event.target.closest('.cond-hour');
      if (!button) return;
      var data;
      try {
        data = JSON.parse(button.dataset.point);
      } catch (error) {
        return;
      }

      var buttons = timeline.querySelectorAll('.cond-hour');
      for (var i = 0; i < buttons.length; i++) buttons[i].classList.remove('active');
      button.classList.add('active');

      if (badge) badge.textContent = data.label;
      if (wind) wind.textContent = data.wind;
      if (wave) wave.textContent = data.wave;
      if (tide) tide.textContent = data.tide;
      if (reason) reason.textContent = data.reason;

      card.classList.remove('cond-good', 'cond-caution', 'cond-avoid');
      card.classList.add('cond-' + data.verdict);
    });

    /* 自訂捲軸：原生灰色捲軸換成細細一條，跟著橫向捲動位置走。
       用 px（不是 %）算寬度／位移，避免 transform 百分比是「相對自己寬度」導致跑位；
       多數螢幕寬度下 11 個鐘點其實整行塞得下、根本沒東西可捲，這種情況直接把捲軸藏起來，
       不要放一條沒意義的滿版灰條。量測延到排版穩定後才做，避免抓到還沒排好版的暫時值。 */
    var row = timeline.querySelector('.cond-hour-row');
    var track = timeline.querySelector('.cond-scrollbar');
    var thumb = timeline.querySelector('.cond-scrollbar-thumb');
    if (row && track && thumb) {
      var updateThumb = function () {
        var scrollable = row.scrollWidth - row.clientWidth;
        if (scrollable <= 2) {
          track.hidden = true;
          return;
        }
        track.hidden = false;
        var trackWidth = track.clientWidth;
        var ratio = Math.min(row.clientWidth / row.scrollWidth, 1);
        var thumbWidth = Math.max(ratio * trackWidth, 24);
        thumb.style.width = thumbWidth + 'px';
        var travel = trackWidth - thumbWidth;
        var progress = row.scrollLeft / scrollable;
        thumb.style.transform = 'translateX(' + (progress * travel) + 'px)';
      };
      row.addEventListener('scroll', updateThumb, { passive: true });
      window.addEventListener('resize', updateThumb);
      requestAnimationFrame(function () { requestAnimationFrame(updateThumb); });
    }
  });

  /* 海況卡片的地點切換標籤：手機版一次只顯示一張卡，桌機版維持整排 grid。
     用 matchMedia 判斷目前是不是手機寬度，切回桌機時自動還原全部顯示。 */
  var mobileQuery = window.matchMedia('(max-width: 760px)');
  var applyFns = [];

  document.querySelectorAll('[data-cond-tabs]').forEach(function (tabs) {
    var group = tabs.nextElementSibling;
    if (!group || !group.matches('[data-cond-group]')) return;
    var cards = group.querySelectorAll('[data-cond-card]');
    var tabButtons = tabs.querySelectorAll('.cond-tab');
    var activeIndex = 0;

    function apply() {
      if (!mobileQuery.matches) {
        cards.forEach(function (card) { card.hidden = false; });
        return;
      }
      cards.forEach(function (card, i) { card.hidden = i !== activeIndex; });
    }

    tabs.addEventListener('click', function (event) {
      var button = event.target.closest('.cond-tab');
      if (!button) return;
      activeIndex = Number(button.dataset.condTab || 0);
      tabButtons.forEach(function (b) { b.classList.remove('active'); });
      button.classList.add('active');
      apply();
    });

    applyFns.push(apply);
    apply();
  });

  if (applyFns.length) {
    var applyAll = function () { applyFns.forEach(function (fn) { fn(); }); };
    if (mobileQuery.addEventListener) {
      mobileQuery.addEventListener('change', applyAll);
    } else if (mobileQuery.addListener) {
      mobileQuery.addListener(applyAll);
    }
    // 保險：部分環境（例如自動化工具改視窗大小）不一定會觸發 matchMedia 的
    // change 事件，這裡額外掛一個 resize 監聽確保切回桌機寬度時卡片一定會還原。
    window.addEventListener('resize', applyAll);
  }

  /* 認識沖繩的地區卡片：桌機滑過（:hover/:focus-visible）就看得到說明，
     這裡額外補一個點擊切換，讓觸控裝置（沒有 hover）也能打開/關掉說明。 */
  document.querySelectorAll('[data-okiregion-card]').forEach(function (card) {
    card.addEventListener('click', function () {
      var expanded = card.classList.toggle('expanded');
      card.setAttribute('aria-expanded', String(expanded));
    });
  });
})();
