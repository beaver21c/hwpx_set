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
import re
import shutil
import sys
import zipfile
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


NAME_RE = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


def check_skill(target: Path) -> list[str]:
    """스킬이 등록될 수 있는 모양인지 본다. 문제를 문자열 목록으로 돌려준다.

    프론트매터는 줄 단위로 읽히는 곳이 있어, `description: >-` 같은 여러 줄
    표기는 스킬이 통째로 무시되는 원인이 된다. 그래서 한 줄인지까지 본다.
    """
    problems: list[str] = []
    path = target / "SKILL.md"
    if not path.exists():
        return [f"SKILL.md가 없다: {path}"]

    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        problems.append("첫 줄이 `---`가 아니다(프론트매터 없음)")
        return problems
    end = text.find("\n---\n", 3)
    if end < 0:
        problems.append("프론트매터를 닫는 `---`가 없다")
        return problems

    front = text[4:end]
    fields: dict[str, str] = {}
    for line in front.split("\n"):
        if not line.strip():
            continue
        if line[0].isspace() or ":" not in line:
            problems.append(f"프론트매터는 `키: 값` 한 줄이어야 한다: {line[:40]!r}")
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()

    name = fields.get("name", "")
    if not name:
        problems.append("name이 없다")
    elif not NAME_RE.match(name):
        problems.append(f"name은 영소문자·숫자·하이픈만 쓴다: {name!r}")
    elif name != target.name:
        problems.append(f"name({name})과 폴더 이름({target.name})이 다르다")

    desc = fields.get("description", "")
    if not desc:
        problems.append("description이 없다(여러 줄 `>-` 표기를 썼는지 확인)")
    elif len(desc) > 1024:
        problems.append(f"description이 너무 길다({len(desc)}자)")
    elif desc.startswith((">", "|", "&", "*", "[", "{")):
        problems.append(f"description이 YAML 특수 문자로 시작한다: {desc[:10]!r}")

    for extra in set(fields) - {"name", "description", "license", "allowed-tools"}:
        problems.append(f"알 수 없는 프론트매터 항목: {extra!r}")
    return problems


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

쓰는 곳에 따라 방법이 다르다.

## claude.ai / 데스크톱 앱 (스킬이 계정에 동기화되는 환경)

`hwpx-report-studio.skill` 파일을 claude.ai 설정의 스킬 화면에서 **업로드**한다.
`.zip`이 아니라 **`.skill` 확장자**여야 한다(내용이 같아도 확장자를 본다).
`python skills/build.py --pack`으로 만든다.

## Claude Code CLI (내 컴퓨터의 폴더를 읽는 환경)

폴더를 통째로 넣고 Claude Code를 다시 연다.

| 어디에 | 경로 |
|---|---|
| 개인 스킬(모든 프로젝트) | `~/.claude/skills/hwpx-report-studio/` |
| 프로젝트 전용 | `<프로젝트>/.claude/skills/hwpx-report-studio/` |

```bash
cp -r hwpx-report-studio ~/.claude/skills/
ls ~/.claude/skills/hwpx-report-studio/SKILL.md    # 이 경로에 바로 있어야 한다
```

압축을 풀 때 `hwpx-report-studio/hwpx-report-studio/`처럼 **한 겹 더 들어가면 안 잡힌다.**
`SKILL.md`가 스킬 폴더 바로 아래 있어야 한다.

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


def pack(target: Path) -> Path:
    """claude.ai 스킬 업로드에 쓰는 `.skill` 파일(폴더를 담은 zip)."""
    out = target.parent / f"{target.name}.skill"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(target.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(target.parent)
            if "__pycache__" in rel.parts or path.suffix == ".pyc":
                continue
            zf.write(path, rel)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", "--out", default="dist", help="스킬 폴더를 만들 상위 경로")
    ap.add_argument("-p", "--profile", default="policy-default")
    ap.add_argument("--pack", action="store_true",
                    help="claude.ai에 올릴 .skill 파일도 만든다")
    args = ap.parse_args()

    out = Path(args.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    target = build(out, args.profile)
    problems = check_skill(target)
    for problem in problems:
        print(f"  ✘ {problem}")
    if problems:
        print("스킬이 등록되지 않을 수 있다. 위 항목을 고칠 것")
        return 1

    files = sum(1 for _ in target.rglob("*") if _.is_file())
    print(f"생성: {target} (파일 {files}개) — 프론트매터 검사 통과")

    if args.pack:
        print(f"생성: {pack(target)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
