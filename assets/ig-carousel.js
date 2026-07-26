/* 文章內的 IG 輪播位：捲動時做半立體景深效果，並提供浮標可點跳頁。
   尊重 prefers-reduced-motion：直接退化成普通橫向捲動，不做 3D 變形。 */
(function () {
  'use strict';

  var tracks = document.querySelectorAll('.ig-track');
  if (!tracks.length) return;

  var reduceMotion = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  tracks.forEach(function (track) {
    var slides = Array.prototype.slice.call(track.querySelectorAll('.ig-slide'));
    if (slides.length < 2) return;

    var dots = document.createElement('div');
    dots.className = 'ig-dots';
    dots.setAttribute('role', 'tablist');
    dots.setAttribute('aria-label', '輪播頁碼');
    slides.forEach(function (slide, index) {
      var dot = document.createElement('button');
      dot.type = 'button';
      dot.className = 'ig-dot';
      dot.setAttribute('aria-label', '第 ' + (index + 1) + ' 張');
      dot.addEventListener('click', function () {
        slide.scrollIntoView({
          behavior: reduceMotion ? 'auto' : 'smooth',
          inline: 'center',
          block: 'nearest'
        });
      });
      dots.appendChild(dot);
    });
    track.insertAdjacentElement('afterend', dots);
    var dotEls = Array.prototype.slice.call(dots.children);

    function update() {
      var trackRect = track.getBoundingClientRect();
      var center = trackRect.left + trackRect.width / 2;
      var closestIndex = 0;
      var closestDist = Infinity;

      slides.forEach(function (slide, index) {
        var rect = slide.getBoundingClientRect();
        var slideCenter = rect.left + rect.width / 2;
        var delta = slideCenter - center;
        var dist = Math.abs(delta);
        if (dist < closestDist) { closestDist = dist; closestIndex = index; }

        if (!reduceMotion) {
          var t = Math.max(-1, Math.min(1, delta / (trackRect.width / 2)));
          var scale = 1 - Math.abs(t) * 0.14;
          var rotate = t * -12;
          slide.style.transform = 'scale(' + scale.toFixed(3) + ') rotateY(' + rotate.toFixed(1) + 'deg)';
          slide.style.opacity = String(1 - Math.abs(t) * 0.35);
        }
      });

      dotEls.forEach(function (dot, index) {
        dot.classList.toggle('active', index === closestIndex);
      });
    }

    // 只有 7 張卡、每次算 boundingClientRect，成本低到不需要 rAF 節流——
    // 節流反而在部分環境下卡住（rAF 沒被觸發時，旗標會卡死不再更新）。
    track.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    update();
  });
})();
