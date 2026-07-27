/* 月份頁的氣候小儀表板：捲到看得到才展開長條/圓點，
   跟站上其他卡片用 hover 展開的手感刻意做出區隔。 */
(function () {
  'use strict';

  var dash = document.querySelector('[data-month-dash]');
  if (!dash) return;

  var reveal = function () {
    dash.classList.add('in-view');
  };

  if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    reveal();
    return;
  }

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        reveal();
        observer.disconnect();
      }
    });
  }, { threshold: 0.3 });

  observer.observe(dash);
})();
