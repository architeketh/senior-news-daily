// site/assets/thanks.js
(function () {
  function mount() {
    var html = ''
      + '<div id="support-note" style="text-align:center;margin:2rem auto 1.5rem;'
      + 'max-width:1000px;padding:12px 14px;border:1px solid rgba(0,0,0,.08);'
      + 'border-radius:12px;font-size:.95rem;opacity:.9;background:color-mix(in oklab, canvas 96%, canvastext 4%);">'
      + 'If you like what you are seeing, Venmo: '
      + '<a href="https://venmo.com/MikeHnastchenko" target="_blank">@MikeHnastchenko</a>'
      + ' or Email: '
      + '<a href="mailto:Architek.eth@gmail.com">Architek.eth@gmail.com</a>'
      + '</div>';

    // Prefer placing before closing </main>, else at end of body
    var main = document.querySelector('main');
    var container = document.createElement('div');
    container.innerHTML = html;

    if (main) main.appendChild(container.firstChild);
    else document.body.appendChild(container.firstChild);
  }

  if (document.getElementById('support-note')) return;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
