(function() {
  var buttons = document.querySelectorAll('.btn-copy-aicid');
  buttons.forEach(function(btn) {
    btn.addEventListener('click', function() {
      var text = btn.getAttribute('data-copy');
      if (!text) return;

      function onSuccess() {
        btn.classList.add('copied');
        var icon = btn.querySelector('.copy-icon');
        var original = icon ? icon.textContent : '📋';
        if (icon) icon.textContent = '✓';
        setTimeout(function() {
          btn.classList.remove('copied');
          if (icon) icon.textContent = original;
        }, 1800);
      }

      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(onSuccess).catch(function() {
          fallback(text, onSuccess);
        });
      } else {
        fallback(text, onSuccess);
      }
    });
  });

  function fallback(text, cb) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.top = '-9999px';
    ta.style.left = '-9999px';
    ta.setAttribute('readonly', '');
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
      if (document.execCommand('copy') && cb) cb();
    } catch (e) {}
    document.body.removeChild(ta);
  }
})();
