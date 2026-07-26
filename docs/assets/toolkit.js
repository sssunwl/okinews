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
