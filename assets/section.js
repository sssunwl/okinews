/* 內容區塊：多維 tag 篩選（交集） */
(function () {
  'use strict';

  var filters = document.getElementById('postFilters');
  var grid = document.getElementById('postGrid');
  var empty = document.getElementById('postEmpty');
  if (!filters || !grid) return;

  var active = [];

  function apply() {
    var cards = grid.querySelectorAll('.post-card');
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
})();
