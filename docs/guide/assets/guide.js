// backlog-mcp-sandbox 学習ガイド 共通スクリプト
//
// やることは 2 つだけである。
//   1. コードブロックの syntax highlight
//   2. mermaid 図の描画
//
// どちらも CDN から読む。読めなかったときに本文が壊れないことを、
// この読み込み側で保証する。ハイライトが無くてもコードは読めるが、
// mermaid が無いと図の要素が空欄になり、何が書いてあったか分からなくなる。
// そのため mermaid だけはソースを見せるフォールバックを持つ。

(function () {
  "use strict";

  function highlight() {
    if (typeof window.hljs === "undefined") return;
    document.querySelectorAll("pre code").forEach(function (element) {
      if (element.closest(".mermaid")) return;
      // plaintext はディレクトリ構成や SSE のワイヤ形式に使う。
      // 色を付けると却って読みにくい。
      if (element.classList.contains("language-plaintext")) return;
      window.hljs.highlightElement(element);
    });
  }

  var darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

  // 描画すると要素の中身が SVG に変わり、元の定義が読めなくなる。
  // 配色が変わったときに描き直せるよう、最初に退避しておく。
  var SOURCE = "data-mermaid-source";

  // 描画前の状態に戻す。初回は退避するだけで、中身はまだソースのままである。
  function resetToSource(block) {
    if (block.hasAttribute(SOURCE)) {
      block.textContent = block.getAttribute(SOURCE);
      block.removeAttribute("data-processed");
      // 前回フォールバックしていても、描き直しに成功すれば図に戻す。
      block.removeAttribute("data-fallback");
    } else {
      block.setAttribute(SOURCE, block.textContent);
    }
  }

  function renderDiagrams(blocks) {
    if (typeof window.mermaid === "undefined") {
      showDiagramSource(blocks);
      return;
    }

    blocks.forEach(resetToSource);

    window.mermaid.initialize({
      startOnLoad: false,
      // 本文だけが暗くなり図がライトのまま取り残される、を避ける。
      theme: darkQuery.matches ? "dark" : "neutral",
      securityLevel: "loose",
      flowchart: { curve: "basis", htmlLabels: true },
      themeVariables: {
        fontFamily: "Hiragino Sans, Noto Sans JP, sans-serif",
        fontSize: "14px",
      },
    });

    window.mermaid.run({ nodes: blocks }).catch(function (error) {
      console.error("mermaid の描画に失敗しました", error);
      showDiagramSource(blocks);
    });
  }

  // 図として描けないときは、mermaid のソースをそのまま見せる。
  function showDiagramSource(blocks) {
    blocks.forEach(function (block) {
      if (block.hasAttribute("data-fallback")) return;
      block.setAttribute("data-fallback", "");
      block.textContent = block.textContent.trim();
    });
  }

  function start() {
    highlight();

    var blocks = document.querySelectorAll(".diagram .mermaid");
    if (!blocks.length) return;

    renderDiagrams(blocks);

    // OS の配色はページを開いたまま切り替わりうる。
    // CSS 変数は自動で追従するが、描画済みの SVG は追従しないので描き直す。
    darkQuery.addEventListener("change", function () {
      renderDiagrams(blocks);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
