/**
 * 検証 UI のエントリ。#root に App を載せる。
 *
 * @throws {Error} `#root` が無いとき
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App.tsx";

const root = document.getElementById("root");
if (root === null) {
  throw new Error("root 要素が見つかりません。");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
