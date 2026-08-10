"""docs/guide の内部リンクとローカル参照が壊れていないか調べる。

学習ガイドは 3 冊が相互に参照し合うため、章を移動したときにリンクだけが取り残される。
壊れても表示は成立してしまうので、機械で確かめる。

外部 URL は対象にしない。到達性はネットワークの都合で変わり、CI の失敗理由として不安定である。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

GUIDE_DIR = Path(__file__).resolve().parent.parent / "docs" / "guide"

ID_PATTERN = re.compile(r'\sid="([^"]+)"')
HREF_PATTERN = re.compile(r'\shref="([^"]+)"')
SRC_PATTERN = re.compile(r'\ssrc="([^"]+)"')


def ids_in(text: str) -> set[str]:
    return set(ID_PATTERN.findall(text))


def local_references(text: str) -> list[str]:
    """外部 URL とデータ URI を除いた href / src を返す。"""
    found = HREF_PATTERN.findall(text) + SRC_PATTERN.findall(text)
    return [ref for ref in found if not re.match(r"^(https?:|data:|mailto:)", ref)]


def check(path: Path, all_ids: dict[Path, set[str]]) -> list[str]:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")

    for ref in local_references(text):
        target, _, fragment = ref.partition("#")

        if not target:
            # 同一ファイル内のアンカー
            if fragment not in all_ids[path]:
                problems.append(f"{path.name}: アンカー #{fragment} の宛先がない")
            continue

        resolved = (path.parent / target).resolve()
        if not resolved.exists():
            problems.append(f"{path.name}: {target} が存在しない")
            continue

        if fragment:
            if resolved not in all_ids:
                all_ids[resolved] = ids_in(resolved.read_text(encoding="utf-8"))
            if fragment not in all_ids[resolved]:
                problems.append(f"{path.name}: {target}#{fragment} の宛先がない")

    return problems


def main() -> int:
    pages = sorted(GUIDE_DIR.glob("*.html"))
    if not pages:
        print(f"{GUIDE_DIR} に HTML がない", file=sys.stderr)
        return 1

    all_ids = {page: ids_in(page.read_text(encoding="utf-8")) for page in pages}

    problems: list[str] = []
    for page in pages:
        problems.extend(check(page, all_ids))

    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1

    print(f"{len(pages)} 冊のリンクは壊れていない")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
