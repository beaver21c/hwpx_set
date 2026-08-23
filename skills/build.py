#!/usr/bin/env python3
"""스킬 폴더를 조립한다: export-skill 결과 + 이 폴더의 손으로 쓴 문서.

`hwpx-studio export-skill`이 만드는 것(프로파일·스크립트·엔진)에, 여기 있는
SKILL.md와 reference/를 덮어씌운다. 그래서 엔진이 바뀌어도 다시 만들면 되고,
KIHASA 작성 규칙은 사람이 손으로 관리한다.

    python skills/build.py                      # dist/hwpx-report-studio/
    python skills/build.py -o ~/.claude/skills  # 바로 설치
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hwpx_studio.export_skill import export_skill      # noqa: E402
from hwpx_studio.profile import load_profile           # noqa: E402

SLUG = "hwpx-report-studio"

#: 이 스킬이 쓰는 집필 규칙. 프로파일의 rules에 얹는다
HOUSE_RULES = {
    "min_children": {"title2": 2, "L1": 2, "L2": 2},
    "head_pattern": {"L1": r"^【[^】]+】", "L2": r"^\([^)]+\)"},
    "period_policy": "single_sentence_no_period",
}


def build(out_dir: Path, base_profile: str = "policy-default") -> Path:
    target = out_dir / SLUG
    if target.exists():
        shutil.rmtree(target)

    profile = load_profile(base_profile)
    profile["rules"] = dict(profile.get("rules") or {}, **HOUSE_RULES)
    export_skill(profile, str(target), slug=SLUG, standalone=True)

    here = Path(__file__).resolve().parent / SLUG
    shutil.copy2(here / "SKILL.md", target / "SKILL.md")       # 손으로 쓴 쪽이 이긴다
    shutil.copytree(here / "reference", target / "reference", dirs_exist_ok=True)
    (target / "설치.md").write_text(INSTALL, encoding="utf-8")

    profile_path = target / "profile.json"
    profile_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


INSTALL = """# 설치

이 폴더를 통째로 스킬 폴더에 넣는다.

| 어디에 | 경로 |
|---|---|
| 개인 스킬(모든 프로젝트) | `~/.claude/skills/hwpx-report-studio/` |
| 프로젝트 전용 | `<프로젝트>/.claude/skills/hwpx-report-studio/` |

```bash
cp -r hwpx-report-studio ~/.claude/skills/
```

Claude Code를 다시 열면 목록에 잡힌다.

## 필요한 것

`python-hwpx` 하나뿐이다(엔진은 `scripts/hwpx_studio/`에 동봉).

```bash
pip install "python-hwpx>=6.2,<7"
```

한글 프로그램은 필요 없다.

## 기존 hwpx-report 스킬

같은 일을 하는 스킬이 둘이면 어느 쪽이 걸릴지 헷갈린다. 이 스킬을 쓰기로 했다면
기존 `hwpx-report`는 꺼 두는 편이 낫다(claude.ai 설정에서 비활성화하거나 폴더를 옮긴다).

옮겨온 것: 6단계 작업 절차, 레벨 체계, 계층 균형, 머릿글 규칙, 개조식 서술 규칙,
자동 부여 vs 직접 입력, 체크리스트.
새로 생긴 것: 도식 네 가지, 규칙 자동 검사(lint), 도식 가져오기.
바뀐 것: 파이썬 코드(`REPORT_CONTENTS`)를 고치는 대신 **마커 텍스트 파일**을 쓴다.

## 확인

```bash
cd ~/.claude/skills/hwpx-report-studio
printf '# 시험\\n## 개요\\n□ 【확인 1】 동작 점검\\n○ (1) 생성 확인\\n- 첫째\\n- 둘째\\n○ (2) 검사 확인\\n- 셋째\\n- 넷째\\n' > /tmp/t.md
python scripts/build.py /tmp/t.md -o /tmp/시험.hwpx
```
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="dist", help="스킬 폴더를 만들 상위 경로")
    ap.add_argument("-p", "--profile", default="policy-default")
    args = ap.parse_args()

    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    target = build(out, args.profile)
    files = sum(1 for _ in target.rglob("*") if _.is_file())
    print(f"생성: {target} (파일 {files}개)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
