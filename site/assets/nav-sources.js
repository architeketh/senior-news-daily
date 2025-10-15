// site/assets/nav-sources.js
(function () {
  function baseUrl() {
    const { origin, pathname } = window.location;
    // drop filename (index.html) from the end, keep trailing slash
    return origin + pathname.replace(/[^/]*$/, "");
  }

  function textEquals(el, t) {
    return el && el.textContent && el.textContent.trim().toLowerCase() === t;
  }

  function insertAfter(node, newNode) {
    node.parentNode.insertBefore(newNode, node.nextSibling);
  }

  function makeLinkLike(node, href, label) {
    // If the menu uses <li><a>, clone the <li>; else clone the <a>
    let isLI = node.tagName === "LI";
    let shell = node.cloneNode(true);

    // Find the <a> inside (or use the node itself)
    let a = isLI ? shell.querySelector("a") : shell;
    if (!a) {
      a = document.createElement("a");
      if (isLI) shell.appendChild(a);
      else shell = a;
    }

    a.href = href;
    a.textContent = label;

    // Clear any "active" state copied from Home
    a.classList.remove("active", "is-active", "selected", "current");
    shell.classList.remove("active", "is-active", "selected", "current");

    // If aria-current was copied, remove it
    if (a.hasAttribute("aria-current")) a.removeAttribute("aria-current");
    if (shell.hasAttribute && shell.hasAttribute("aria-current")) shell.removeAttribute("aria-current");

    return shell;
  }

  function mount() {
    const root = baseUrl();
    const url = root + "sources.html";

    // Try to find your top nav: look for anchors labeled Home / Saved
    const anchors = Array.from(document.querySelectorAll("nav a, .nav a, .tabs a, .menu a, a"));
    const home = anchors.find(a => textEquals(a, "home"));
    const saved = anchors.find(a => textEquals(a, "saved"));

    if (!home) return; // no nav found; do nothing

    // Build a Sources item that looks like your existing items (clone Home’s element)
    const newItem = makeLinkLike(home.closest("li") || home, url, "Sources");

    // Insert between Home and Saved when possible; else just after Home
    if (saved && saved.parentElement === home.parentElement) {
      insertAfter(home.closest("li") || home, newItem);
    } else {
      insertAfter(home.closest("li") || home, newItem);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
