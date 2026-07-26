/* 旅行小抄：日語發音卡 */
(function () {
  'use strict';

  var grid = document.getElementById('phraseGrid');
  if (!grid) return;

  var PHRASES = [
    { jp: 'すみません', romaji: 'sumimasen', zh: '不好意思／請問一下（叫人、道歉都用它）' },
    { jp: 'これください', romaji: 'kore kudasai', zh: '我要這個（指著點就好）' },
    { jp: 'いくらですか', romaji: 'ikura desu ka', zh: '多少錢？' },
    { jp: 'お会計お願いします', romaji: 'okaikei onegaishimasu', zh: '麻煩結帳' },
    { jp: '英語のメニューはありますか', romaji: 'eigo no menyū wa arimasu ka', zh: '有英文菜單嗎？' },
    { jp: 'トイレはどこですか', romaji: 'toire wa doko desu ka', zh: '洗手間在哪裡？' },
    { jp: '大丈夫です', romaji: 'daijōbu desu', zh: '不用了／沒關係（婉拒推銷很好用）' },
    { jp: '助けてください', romaji: 'tasukete kudasai', zh: '請幫幫我（緊急時）' }
  ];

  var canSpeak = 'speechSynthesis' in window;

  grid.innerHTML = PHRASES.map(function (item, index) {
    return '<article class="phrase-card">' +
      '<div class="phrase-jp">' + OKIP.escapeHTML(item.jp) + '</div>' +
      '<div class="phrase-romaji">' + OKIP.escapeHTML(item.romaji) + '</div>' +
      '<div class="phrase-zh">' + OKIP.escapeHTML(item.zh) + '</div>' +
      (canSpeak ? '<button class="phrase-play" type="button" data-phrase="' + index +
        '" aria-label="播放「' + OKIP.escapeHTML(item.jp) + '」發音">🔊 聽發音</button>' : '') +
      '</article>';
  }).join('');

  if (!canSpeak) {
    grid.insertAdjacentHTML('afterend',
      '<p class="tool-note">這個瀏覽器不支援語音朗讀，羅馬拼音可以直接照著念。</p>');
    return;
  }

  grid.addEventListener('click', function (event) {
    var button = event.target.closest('[data-phrase]');
    if (!button) return;
    var phrase = PHRASES[Number(button.dataset.phrase)];
    window.speechSynthesis.cancel();
    var utterance = new SpeechSynthesisUtterance(phrase.jp);
    utterance.lang = 'ja-JP';
    utterance.rate = 0.85;
    window.speechSynthesis.speak(utterance);
  });
})();

/* 旅行小抄：匯率換算（純前端讀 rates.json 產生的靜態資料，沒有 API key） */
(function () {
  'use strict';

  var input = document.getElementById('rateJpyInput');
  var results = document.getElementById('rateResults');
  var updatedEl = document.getElementById('rateUpdated');
  if (!input || !results) return;

  var dataNode = document.getElementById('ratesData');
  var data = {};
  try { data = dataNode ? JSON.parse(dataNode.textContent) : {}; } catch (err) { data = {}; }
  var rates = data.rates || {};

  var CURRENCIES = [
    { code: 'TWD', label: '新台幣', flag: '🇹🇼' },
    { code: 'HKD', label: '港幣', flag: '🇭🇰' },
    { code: 'USD', label: '美金', flag: '🇺🇸' },
    { code: 'CNY', label: '人民幣', flag: '🇨🇳' },
    { code: 'KRW', label: '韓元', flag: '🇰🇷' }
  ].filter(function (c) { return typeof rates[c.code] === 'number'; });

  if (!CURRENCIES.length) {
    results.innerHTML = '<div class="empty-state"><strong>匯率資料整理中</strong>晚點再回來看看。</div>';
    return;
  }

  function render() {
    var jpy = Number(input.value);
    if (!isFinite(jpy) || jpy < 0) jpy = 0;
    results.innerHTML = CURRENCIES.map(function (c) {
      var value = jpy * rates[c.code];
      var formatted = value.toLocaleString('zh-Hant', {
        maximumFractionDigits: value >= 100 ? 0 : 2
      });
      return '<div class="rate-result-row"><span>' + c.flag + ' ' + c.label + '</span><strong>' +
        formatted + '</strong></div>';
    }).join('');
  }

  input.addEventListener('input', render);
  render();

  if (data.updated) {
    updatedEl.textContent = '匯率更新於 ' + data.updated + ' JST・資料來源 open.er-api.com';
  }
})();
