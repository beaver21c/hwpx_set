/**
 * 자동 생성 파일 — 직접 고치지 말 것.
 * `python tools/build_web.py`로 다시 만든다.
 *
 * 담고 있는 것
 *  - HWPX_TEMPLATE_B64: python-hwpx의 빈 문서 템플릿(base64)
 *  - HWPX_PROFILES:     hwpx_studio/profiles/*.json 사본
 *  - FORM_SCRIPTS:      양식 꾸러미에 넣을 파이썬 도구(빌더·되돌리기)
 *  - FORM_TEMPLATES:    꾸러미 안내문 틀(README·SKILL·AGENTS)
 */

export const HWPX_TEMPLATE_B64 = "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";

export const HWPX_PROFILES = {
  "policy-default": {
    "schema": "hwpx-studio.profile.v1",
    "name": "정책보고서 기본",
    "mode": "outline",
    "fonts": {
      "bold": "KoPub돋움체 Bold",
      "light": "KoPub돋움체 Light",
      "fallback": "KoPub돋움체 Light"
    },
    "page": {
      "size": "A4",
      "margin_mm": {
        "left": 20,
        "right": 20,
        "top": 10,
        "bottom": 10,
        "header": 10,
        "footer": 10
      }
    },
    "levels": [
      {
        "key": "title",
        "name": "로마자",
        "marker": "#",
        "prefix": "AUTO_ROMAN",
        "size_pt": 18,
        "bold": true,
        "font": "bold",
        "color": "#2a56a1",
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_below_pt": 10,
        "line_spacing": 180,
        "align": "JUSTIFY"
      },
      {
        "key": "title2",
        "name": "숫자",
        "marker": "##",
        "prefix": "AUTO_NUM",
        "size_pt": 16,
        "bold": true,
        "font": "bold",
        "color": "#1F3864",
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_below_pt": 10,
        "line_spacing": 180,
        "align": "JUSTIFY"
      },
      {
        "key": "L1",
        "name": "네모",
        "marker": "□",
        "prefix": "□ ",
        "size_pt": 14,
        "bold": true,
        "font": "bold",
        "color": "#4c4c4c",
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_below_pt": 5,
        "line_spacing": 170,
        "align": "JUSTIFY"
      },
      {
        "key": "L2",
        "name": "원",
        "marker": "○",
        "prefix": "○ ",
        "size_pt": 13,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "left_pt": 10,
        "indent_pt": 15,
        "spacing_below_pt": 3,
        "line_spacing": 170,
        "align": "JUSTIFY"
      },
      {
        "key": "L3",
        "name": "하이픈",
        "marker": "-",
        "prefix": "- ",
        "size_pt": 12.5,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "left_pt": 20,
        "indent_pt": 15,
        "spacing_below_pt": 1,
        "line_spacing": 165,
        "align": "JUSTIFY"
      },
      {
        "key": "L4",
        "name": "점",
        "marker": "·",
        "prefix": "· ",
        "size_pt": 12,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "left_pt": 32,
        "indent_pt": 15,
        "spacing_below_pt": 1,
        "line_spacing": 160,
        "align": "JUSTIFY"
      },
      {
        "key": "L5",
        "name": "참고",
        "marker": "※",
        "prefix": "※ ",
        "size_pt": 10,
        "bold": false,
        "font": "light",
        "color": "#666666",
        "left_pt": 40,
        "indent_pt": 15,
        "spacing_below_pt": 1,
        "line_spacing": 130,
        "align": "JUSTIFY"
      }
    ],
    "body": {
      "size_pt": 12,
      "font": "light",
      "line_spacing": 160,
      "first_line_indent_pt": 0
    },
    "table": {
      "border_color": "#999999",
      "header_bg": "#4472C4",
      "width_mm": 162.5,
      "cell_margin_mm": 0.3,
      "treat_as_char": true,
      "anchor_level": "L3",
      "top": {
        "name": "표(위)",
        "eng_name": "Table(Top)",
        "size_pt": 11,
        "bold": true,
        "font": "bold",
        "color": "#FFFFFF",
        "left_pt": 0,
        "indent_pt": 0,
        "prefix": "",
        "spacing_below_pt": 0,
        "line_spacing": 120,
        "align": "CENTER"
      },
      "mid": {
        "name": "표(중간)",
        "eng_name": "Table(Mid)",
        "size_pt": 11,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "left_pt": 0,
        "indent_pt": 0,
        "prefix": "",
        "spacing_below_pt": 0,
        "line_spacing": 120,
        "align": "CENTER"
      },
      "left": {
        "name": "표(왼쪽)",
        "eng_name": "Table(Left)",
        "size_pt": 11,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "left_pt": 0,
        "indent_pt": 12,
        "prefix": "· ",
        "spacing_below_pt": 0,
        "line_spacing": 120,
        "align": "LEFT"
      }
    },
    "image": {
      "default_width_mm": 120,
      "treat_as_char": true
    },
    "rules": {
      "min_children": {
        "title2": 2,
        "L1": 2,
        "L2": 2
      },
      "period_policy": "single_sentence_no_period"
    }
  },
  "kihasa-research": {
    "schema": "hwpx-studio.profile.v1",
    "name": "연구보고서 크라운판(166×241)",
    "mode": "outline",
    "fonts": {
      "bold": "KoPub돋움체 Bold",
      "light": "KoPub바탕체 Light",
      "fallback": "KoPub바탕체 Light"
    },
    "page": {
      "size": "크라운판",
      "width_mm": 166,
      "height_mm": 241,
      "margin_mm": {
        "left": 30,
        "right": 26,
        "top": 26,
        "bottom": 28,
        "header": 16,
        "footer": 0
      }
    },
    "levels": [
      {
        "key": "chapter",
        "name": "타이틀-장제목",
        "marker": "#",
        "prefix": "AUTO_CHAPTER",
        "size_pt": 18,
        "bold": true,
        "font": "bold",
        "color": "#000000",
        "letter_spacing": -5,
        "left_pt": 0,
        "indent_pt": 0,
        "first_line_indent_pt": 10.5,
        "spacing_above_pt": 0,
        "spacing_below_pt": 12,
        "line_spacing": 182,
        "align": "JUSTIFY"
      },
      {
        "key": "section",
        "name": "절",
        "marker": "##",
        "prefix": "AUTO_SECTION",
        "size_pt": 14,
        "bold": true,
        "font": "bold",
        "color": "#000000",
        "letter_spacing": -2,
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_above_pt": 0,
        "spacing_below_pt": 8,
        "line_spacing": 125,
        "align": "JUSTIFY"
      },
      {
        "key": "num",
        "name": "1. 가",
        "marker": "###",
        "prefix": "AUTO_NUM",
        "size_pt": 11.5,
        "bold": true,
        "font": "bold",
        "color": "#000000",
        "letter_spacing": -5,
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_above_pt": 2,
        "spacing_below_pt": 4,
        "line_spacing": 150,
        "align": "JUSTIFY"
      },
      {
        "key": "hangul",
        "name": "가.",
        "marker": "####",
        "prefix": "AUTO_HANGUL",
        "size_pt": 11.5,
        "bold": true,
        "font": "bold",
        "color": "#000000",
        "letter_spacing": -5,
        "left_pt": 10,
        "indent_pt": 0,
        "spacing_above_pt": 2,
        "spacing_below_pt": 4,
        "line_spacing": 150,
        "align": "JUSTIFY"
      },
      {
        "key": "paren",
        "name": "1)",
        "marker": "#####",
        "prefix": "AUTO_PAREN",
        "size_pt": 11.5,
        "bold": false,
        "font": "bold",
        "color": "#000000",
        "letter_spacing": -5,
        "left_pt": 21,
        "indent_pt": 0,
        "spacing_above_pt": 2,
        "spacing_below_pt": 3,
        "line_spacing": 150,
        "align": "JUSTIFY"
      },
      {
        "key": "tcap",
        "name": "표제목",
        "marker": "표)",
        "prefix": "AUTO_TABLE",
        "size_pt": 9,
        "bold": false,
        "font": "bold",
        "color": "#000000",
        "letter_spacing": -5,
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_above_pt": 0,
        "spacing_below_pt": 1,
        "line_spacing": 180,
        "align": "JUSTIFY"
      },
      {
        "key": "fcap",
        "name": "그림제목",
        "marker": "그림)",
        "prefix": "AUTO_FIGURE",
        "size_pt": 9,
        "bold": false,
        "font": "bold",
        "color": "#000000",
        "letter_spacing": -5,
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_above_pt": 0,
        "spacing_below_pt": 1,
        "line_spacing": 180,
        "align": "JUSTIFY"
      },
      {
        "key": "box",
        "name": "요약_네모",
        "marker": "□",
        "prefix": "",
        "size_pt": 10.5,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "letter_spacing": -2,
        "left_pt": 10,
        "indent_pt": 0,
        "spacing_above_pt": 15,
        "spacing_below_pt": 0,
        "line_spacing": 182,
        "align": "JUSTIFY"
      },
      {
        "key": "circle",
        "name": "요약_원",
        "marker": "○",
        "prefix": "",
        "size_pt": 10.5,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "letter_spacing": -2,
        "left_pt": 21,
        "indent_pt": 0,
        "spacing_above_pt": 5,
        "spacing_below_pt": 0,
        "line_spacing": 182,
        "align": "JUSTIFY"
      },
      {
        "key": "hyphen",
        "name": "요약_하이픈",
        "marker": "-",
        "prefix": "",
        "size_pt": 10.5,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "letter_spacing": -2,
        "left_pt": 34,
        "indent_pt": 0,
        "spacing_above_pt": 3,
        "spacing_below_pt": 0,
        "line_spacing": 182,
        "align": "JUSTIFY"
      },
      {
        "key": "dot",
        "name": "요약_점",
        "marker": "·",
        "prefix": "",
        "size_pt": 10.5,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "letter_spacing": -2,
        "left_pt": 45,
        "indent_pt": 0,
        "spacing_above_pt": 3,
        "spacing_below_pt": 0,
        "line_spacing": 182,
        "align": "JUSTIFY"
      },
      {
        "key": "text",
        "name": "바탕글",
        "marker": "",
        "prefix": "",
        "size_pt": 10.5,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "letter_spacing": -2,
        "left_pt": 0,
        "indent_pt": 0,
        "first_line_indent_pt": 10.5,
        "spacing_above_pt": 0,
        "spacing_below_pt": 0,
        "line_spacing": 182,
        "align": "JUSTIFY"
      },
      {
        "key": "note",
        "name": "주, 자료",
        "marker": "※",
        "prefix": "",
        "size_pt": 8,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "letter_spacing": -5,
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_above_pt": 0,
        "spacing_below_pt": 6,
        "line_spacing": 130,
        "align": "JUSTIFY"
      },
      {
        "key": "ref",
        "name": "참고문헌",
        "marker": "[참고문헌]",
        "prefix": "",
        "size_pt": 9.5,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "letter_spacing": -2,
        "left_pt": 0,
        "indent_pt": 26.16,
        "spacing_above_pt": 0,
        "spacing_below_pt": 0,
        "line_spacing": 182,
        "align": "JUSTIFY"
      }
    ],
    "body": {
      "name": "바탕글",
      "size_pt": 10.5,
      "font": "light",
      "color": "#000000",
      "bold": false,
      "letter_spacing": -2,
      "left_pt": 0,
      "indent_pt": 0,
      "spacing_above_pt": 0,
      "spacing_below_pt": 0,
      "line_spacing": 182,
      "align": "JUSTIFY",
      "first_line_indent_pt": 10.5
    },
    "footnote": {
      "name": "각주",
      "eng_name": "Footnote",
      "size_pt": 8,
      "bold": false,
      "font": "light",
      "color": "#000000",
      "letter_spacing": -3,
      "left_pt": 0,
      "indent_pt": 11.08,
      "spacing_above_pt": 0,
      "spacing_below_pt": 0,
      "line_spacing": 130,
      "align": "JUSTIFY"
    },
    "rules": {
      "period_policy": "always_period",
      "footnote_position": "before_period",
      "min_children": {},
      "head_pattern": {}
    }
  },
  "gov-3level": {
    "schema": "hwpx-studio.profile.v1",
    "name": "공문서 3레벨",
    "mode": "outline",
    "fonts": {
      "bold": "맑은 고딕",
      "light": "맑은 고딕",
      "fallback": "맑은 고딕"
    },
    "page": {
      "size": "A4",
      "margin_mm": {
        "left": 20,
        "right": 20,
        "top": 10,
        "bottom": 10,
        "header": 10,
        "footer": 10
      }
    },
    "levels": [
      {
        "key": "title",
        "name": "로마자",
        "marker": "#",
        "prefix": "AUTO_ROMAN",
        "size_pt": 18,
        "bold": true,
        "font": "bold",
        "color": "#000000",
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_below_pt": 10,
        "line_spacing": 180,
        "align": "JUSTIFY"
      },
      {
        "key": "title2",
        "name": "숫자",
        "marker": "##",
        "prefix": "AUTO_NUM",
        "size_pt": 16,
        "bold": true,
        "font": "bold",
        "color": "#000000",
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_below_pt": 10,
        "line_spacing": 180,
        "align": "JUSTIFY"
      },
      {
        "key": "L1",
        "name": "네모",
        "marker": "□",
        "prefix": "□ ",
        "size_pt": 14,
        "bold": true,
        "font": "bold",
        "color": "#000000",
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_below_pt": 5,
        "line_spacing": 170,
        "align": "JUSTIFY"
      },
      {
        "key": "L2",
        "name": "원",
        "marker": "○",
        "prefix": "○ ",
        "size_pt": 13,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "left_pt": 10,
        "indent_pt": 15,
        "spacing_below_pt": 3,
        "line_spacing": 170,
        "align": "JUSTIFY"
      },
      {
        "key": "L3",
        "name": "하이픈",
        "marker": "-",
        "prefix": "- ",
        "size_pt": 12.5,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "left_pt": 20,
        "indent_pt": 15,
        "spacing_below_pt": 1,
        "line_spacing": 165,
        "align": "JUSTIFY"
      }
    ],
    "body": {
      "size_pt": 12,
      "font": "light",
      "line_spacing": 160,
      "first_line_indent_pt": 0
    },
    "table": {
      "border_color": "#999999",
      "header_bg": "#4472C4",
      "width_mm": 162.5,
      "cell_margin_mm": 0.3,
      "treat_as_char": true,
      "anchor_level": "L3",
      "top": {
        "name": "표(위)",
        "eng_name": "Table(Top)",
        "size_pt": 11,
        "bold": true,
        "font": "bold",
        "color": "#FFFFFF",
        "left_pt": 0,
        "indent_pt": 0,
        "prefix": "",
        "spacing_below_pt": 0,
        "line_spacing": 120,
        "align": "CENTER"
      },
      "mid": {
        "name": "표(중간)",
        "eng_name": "Table(Mid)",
        "size_pt": 11,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "left_pt": 0,
        "indent_pt": 0,
        "prefix": "",
        "spacing_below_pt": 0,
        "line_spacing": 120,
        "align": "CENTER"
      },
      "left": {
        "name": "표(왼쪽)",
        "eng_name": "Table(Left)",
        "size_pt": 11,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "left_pt": 0,
        "indent_pt": 12,
        "prefix": "· ",
        "spacing_below_pt": 0,
        "line_spacing": 120,
        "align": "LEFT"
      }
    },
    "image": {
      "default_width_mm": 120,
      "treat_as_char": true
    },
    "rules": {
      "min_children": {
        "title2": 2,
        "L1": 2
      },
      "period_policy": "single_sentence_no_period"
    }
  },
  "narrative": {
    "schema": "hwpx-studio.profile.v1",
    "name": "서술식 보고서",
    "mode": "narrative",
    "fonts": {
      "bold": "맑은 고딕",
      "light": "맑은 고딕",
      "fallback": "맑은 고딕"
    },
    "page": {
      "size": "A4",
      "margin_mm": {
        "left": 20,
        "right": 20,
        "top": 10,
        "bottom": 10,
        "header": 10,
        "footer": 10
      }
    },
    "levels": [
      {
        "key": "title",
        "name": "로마자",
        "marker": "#",
        "prefix": "AUTO_ROMAN",
        "size_pt": 18,
        "bold": true,
        "font": "bold",
        "color": "#2a56a1",
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_below_pt": 10,
        "line_spacing": 180,
        "align": "JUSTIFY"
      },
      {
        "key": "title2",
        "name": "숫자",
        "marker": "##",
        "prefix": "AUTO_NUM",
        "size_pt": 16,
        "bold": true,
        "font": "bold",
        "color": "#1F3864",
        "left_pt": 0,
        "indent_pt": 0,
        "spacing_below_pt": 10,
        "line_spacing": 180,
        "align": "JUSTIFY"
      }
    ],
    "body": {
      "name": "본문",
      "size_pt": 12,
      "font": "light",
      "line_spacing": 180,
      "first_line_indent_pt": 10,
      "spacing_below_pt": 4,
      "align": "JUSTIFY"
    },
    "table": {
      "border_color": "#999999",
      "header_bg": "#4472C4",
      "width_mm": 162.5,
      "cell_margin_mm": 0.3,
      "treat_as_char": true,
      "anchor_level": null,
      "top": {
        "name": "표(위)",
        "eng_name": "Table(Top)",
        "size_pt": 11,
        "bold": true,
        "font": "bold",
        "color": "#FFFFFF",
        "left_pt": 0,
        "indent_pt": 0,
        "prefix": "",
        "spacing_below_pt": 0,
        "line_spacing": 120,
        "align": "CENTER"
      },
      "mid": {
        "name": "표(중간)",
        "eng_name": "Table(Mid)",
        "size_pt": 11,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "left_pt": 0,
        "indent_pt": 0,
        "prefix": "",
        "spacing_below_pt": 0,
        "line_spacing": 120,
        "align": "CENTER"
      },
      "left": {
        "name": "표(왼쪽)",
        "eng_name": "Table(Left)",
        "size_pt": 11,
        "bold": false,
        "font": "light",
        "color": "#000000",
        "left_pt": 0,
        "indent_pt": 12,
        "prefix": "· ",
        "spacing_below_pt": 0,
        "line_spacing": 120,
        "align": "LEFT"
      }
    },
    "image": {
      "default_width_mm": 120,
      "treat_as_char": true
    },
    "rules": {
      "min_children": {},
      "period_policy": "always_period"
    }
  }
};

export const FORM_SCRIPTS = {
  "build_form.py": "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\"\"\"양식 보존 방식 한글 문서 빌더.\n\n`form.json`(양식 카드) + `template.hwpx`(양식 원본) + 마커 텍스트 → `.hwpx`.\n\n## 왜 이렇게 만드나\n\n서식을 새로 지어 내면 한글의 자동 글머리표·번호매기기·글꼴·쪽 설정처럼\n문단 속성 바깥에 있는 것들을 잃는다. 그래서 이 빌더는 **양식을 고치지 않는다.**\n\n  - `Contents/header.xml` — 한 바이트도 건드리지 않는다\n  - `Contents/section0.xml` — 앞부분(용지 설정·표지·머리글)은 그대로 두고\n    **본문 문단만** 새로 만들어 갈아 끼운다\n\n따라서 산출물의 서식은 양식과 같다. 재현이 아니라 보존이다.\n\n## 쓰는 법\n\n    python build_form.py 원고.md -o 결과.hwpx\n\n    python build_form.py 원고.md --check-only     # 입력 검사만\n    python build_form.py --markers                # 이 양식의 마커 목록 보기\n\n줄머리 기호를 **누가** 붙일지 고를 수 있다. 양식마다 다르기 때문이다.\n\n    --bullets auto      양식을 해부해 정해 둔 대로(기본값)\n    --bullets hangul    한글에 맡긴다. 본문에 기호를 적지 않는다\n    --bullets text      도구가 본문 텍스트에 적어 넣는다\n\n고른 값이 양식과 어긋나면 — 한글이 붙이는데 도구까지 적거나, 한글에 맡겼는데\n양식에 글머리표가 없거나 — 1층 검사가 알려 준다.\n\n`form.json`·`template.hwpx`는 이 스크립트와 같은 폴더에 있으면 저절로 찾는다.\n\n## 입력 문법\n\n마커는 양식마다 다르다. `--markers`로 확인할 것. 공통 문법은 다음과 같다.\n\n    (빈 줄)             문단 사이 간격\n    | a | b |           표. 첫 행이 머리행. `|---|` 줄은 무시\n    [표: 제목]          바로 다음 표의 제목(양식에 표 번호가 있으면 <표 Ⅱ-1>처럼)\n    {cols=20,50,30}     바로 다음 표의 열 너비 백분율\n    셀 안 <br>          셀 안에서 줄 나눔\n    ※ 자료：…           표 주. 표 바로 아래에 둔다(양식에 표 주 스타일이 있을 때)\n    [장: 제목]          장 표지의 제목. 문서에 하나\n    앞말[^1]            각주 번호 자리\n    [^1]: 내용          각주 내용(문서 어디에 적어도 된다)\n\n장 번호는 `--chapter 3`으로 정한다(Ⅲ). 표지 로마자와 표 번호 접두가 함께 바뀐다.\n\n각주 번호는 한글이 문서 순서대로 매긴다. 라벨은 이름표일 뿐이다.\n\n의존성 없음(파이썬 표준 라이브러리만). 파이썬 3.9 이상.\n\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport io\nimport json\nimport re\nimport sys\nimport xml.dom.minidom\nimport zipfile\nfrom dataclasses import dataclass, field\nfrom pathlib import Path\nfrom typing import Any, Dict, List, Optional, Sequence, Tuple\n\nHERE = Path(__file__).resolve().parent\n\nROMAN = [\"Ⅰ\", \"Ⅱ\", \"Ⅲ\", \"Ⅳ\", \"Ⅴ\", \"Ⅵ\", \"Ⅶ\", \"Ⅷ\", \"Ⅸ\", \"Ⅹ\", \"Ⅺ\", \"Ⅻ\"]\nROMAN_CHARS = \"\".join(ROMAN)\nCIRCLED = \"①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮\"\nHANGUL_ORDER = \"가나다라마바사아자차카타파하\"\n\n#: 문장 끝으로 보는 문장부호(각주 번호 자리 검사)\nSENTENCE_END = \".。!?\"\n\nFOOTNOTE_REF_RE = re.compile(r\"\\[\\^([^\\]\\s]+)\\]\")\nFOOTNOTE_DEF_RE = re.compile(r\"^\\[\\^([^\\]\\s]+)\\]:\\s*(.*)$\")\nCAPTION_RE = re.compile(r\"^\\[표\\s*[:：]\\s*(.+?)\\]\\s*$\")\nCHAPTER_RE = re.compile(r\"^\\[장\\s*[:：]\\s*(.+?)\\]\\s*$\")\nCOLS_RE = re.compile(r\"^\\{cols\\s*=\\s*([\\d.,\\s]+)\\}\\s*$\")\nSEP_ROW_RE = re.compile(r\"^\\|[\\s:|\\-]+\\|$\")\n\n\n# ---------------------------------------------------------------------------\n# 양식 카드\n# ---------------------------------------------------------------------------\nclass Form:\n    \"\"\"`form.json`을 읽어 쓰기 좋게 감싼 것.\"\"\"\n\n    def __init__(self, data: Dict[str, Any]) -> None:\n        self.data = data\n        self.levels: List[Dict[str, Any]] = list(data.get(\"levels\") or [])\n        self.by_key = {lv[\"key\"]: lv for lv in self.levels}\n        # 긴 마커부터 맞춰 본다('##'가 '#'보다 먼저)\n        self.markers: List[Tuple[str, Dict[str, Any]]] = sorted(\n            ((lv[\"marker\"], lv) for lv in self.levels if lv.get(\"marker\")),\n            key=lambda kv: -len(kv[0]))\n\n    @property\n    def name(self) -> str:\n        return self.data.get(\"name\") or \"양식\"\n\n    @property\n    def section(self) -> str:\n        return self.data.get(\"section\") or \"Contents/section0.xml\"\n\n    @property\n    def body_styles(self) -> List[int]:\n        return [int(lv[\"style\"]) for lv in self.levels]\n\n    def plain_level(self) -> Optional[Dict[str, Any]]:\n        \"\"\"마커 없는 줄이 갈 **제 자리**. 없으면 None.\n\n        양식이 이런 레벨을 두었다면(크라운판의 '바탕글' 같은) 마커 없는 줄은\n        서술식 본문이라는 뜻이다. 앞 문단에 이어 붙이면 안 된다.\n        \"\"\"\n        for lv in self.levels:\n            if not lv.get(\"marker\"):\n                return lv\n        return None\n\n    def fallback(self) -> Optional[Dict[str, Any]]:\n        \"\"\"마커가 없는 줄에 쓸 레벨. 마커 없는 레벨 → 없으면 가장 얕은 레벨.\"\"\"\n        return self.plain_level() or (self.levels[-1] if self.levels else None)\n\n    @property\n    def table_note(self) -> Optional[Dict[str, Any]]:\n        return self.data.get(\"table_note\")\n\n    @property\n    def chapter_roman(self) -> Optional[str]:\n        \"\"\"양식에 들어 있던 장 로마자(표지·표 번호에 쓰인 값).\"\"\"\n        chapter = self.data.get(\"chapter\") or {}\n        caption = (self.data.get(\"table\") or {}).get(\"caption\") or {}\n        return chapter.get(\"roman\") or caption.get(\"chapter_roman\")\n\n    def refs(self, block: str) -> Tuple[int, int, int]:\n        node = self.data.get(block) or {}\n        return int(node.get(\"style\", 0)), int(node.get(\"para\", 0)), int(node.get(\"char\", 0))\n\n    def apply_bullet_source(self, source: str) -> List[str]:\n        \"\"\"줄머리 기호를 누가 붙일지 이 자리에서 바꾼다(form.json은 그대로 둔다).\n\n        `auto`는 양식을 해부해 정해 둔 값을 그대로 쓴다. `hangul`은 한글에 맡기고,\n        `text`는 도구가 본문에 적는다. 고른 값이 양식과 어긋나면 말한다.\n        \"\"\"\n        if source not in (\"auto\", \"hangul\", \"text\"):\n            raise SystemExit(f\"[중단] --bullets는 auto·hangul·text 중 하나여야 한다: {source}\")\n        warnings: List[str] = []\n        if source == \"auto\":\n            return warnings\n        for level in self.levels:\n            marker = level.get(\"marker\") or \"\"\n            if not marker or marker.startswith(\"#\"):\n                continue\n            if source == \"hangul\":\n                level[\"write_marker\"] = False\n                if not level.get(\"auto_bullet\"):\n                    warnings.append(\n                        f\"'{level.get('name', '')}' 레벨을 한글에 맡겼지만 이 양식에는 \"\n                        f\"자동 글머리표가 없다 → '{marker}' 기호가 아무 데서도 찍히지 않는다\")\n            else:\n                level[\"write_marker\"] = True\n                if level.get(\"auto_bullet\"):\n                    warnings.append(\n                        f\"'{level.get('name', '')}' 레벨은 한글이 \"\n                        f\"'{level['auto_bullet']}'를 자동으로 붙이는데 도구까지 적도록 \"\n                        \"골랐다 → 기호가 두 번 찍힌다\")\n        return warnings\n\n    def marker_table(self) -> str:\n        rows = [\"| 마커 | 레벨 | 스타일 | 기호·번호 |\", \"|---|---|---|---|\"]\n        for lv in self.levels:\n            if lv.get(\"auto_bullet\"):\n                who = f\"한글이 자동으로 {lv['auto_bullet']}\"\n            elif lv.get(\"auto_number\"):\n                who = \"한글이 자동으로 번호\"\n            elif lv.get(\"numbering\"):\n                who = f\"도구가 번호({lv['numbering']})\"\n            elif lv.get(\"write_marker\"):\n                who = f\"도구가 {lv['marker']}\"\n            else:\n                who = \"없음\"\n            rows.append(f\"| `{lv.get('marker') or '(없음)'}` | {lv['key']} | \"\n                        f\"{lv.get('name', '')} | {who} |\")\n        return \"\\n\".join(rows)\n\n\ndef load_form(path: Optional[Path] = None) -> Form:\n    path = path or (HERE / \"form.json\")\n    if not path.exists():\n        raise SystemExit(f\"[중단] 양식 카드가 없다: {path}\")\n    return Form(json.loads(path.read_text(encoding=\"utf-8\")))\n\n\n# ---------------------------------------------------------------------------\n# 입력 파서\n# ---------------------------------------------------------------------------\n@dataclass\nclass Item:\n    kind: str                                   # para / table / blank / table_note\n    level: Optional[Dict[str, Any]] = None\n    text: str = \"\"\n    notes: List[Dict[str, Any]] = field(default_factory=list)\n    rows: List[List[str]] = field(default_factory=list)\n    caption: str = \"\"\n    col_pct: Optional[List[float]] = None\n    line: int = 0\n\n\n@dataclass\nclass Parsed:\n    items: List[Item] = field(default_factory=list)\n    warnings: List[str] = field(default_factory=list)\n    chapter: Optional[str] = None          # [장: 제목]으로 적은 장 제목\n\n\ndef parse_input(text: str, form: Form) -> Parsed:\n    out = Parsed()\n    warn = out.warnings.append\n    lines = text.splitlines()\n    notes: Dict[str, Dict[str, Any]] = {}\n    pend_cap, pend_cols = \"\", None\n    i = 0\n\n    while i < len(lines):\n        raw = lines[i].rstrip()\n        ln = i + 1\n        i += 1\n\n        if not raw.strip():\n            if out.items and out.items[-1].kind != \"blank\":\n                out.items.append(Item(\"blank\", line=ln))\n            continue\n\n        m = FOOTNOTE_DEF_RE.match(raw.strip())\n        if m:\n            label, body = m.group(1), m.group(2).strip()\n            if label in notes:\n                warn(f\"{ln}행: 각주 [^{label}]의 내용 줄이 두 번 → 뒤엣것을 쓴다\")\n            if not body:\n                warn(f\"{ln}행: 각주 [^{label}]의 내용이 비었다\")\n            notes[label] = {\"text\": body, \"used\": 0}\n            if out.items and out.items[-1].kind == \"blank\":\n                out.items.pop()\n            continue\n\n        m = CHAPTER_RE.match(raw.strip())\n        if m:\n            if out.chapter is not None:\n                warn(f\"{ln}행: [장: …]이 두 번 나왔다 → 뒤엣것을 쓴다\")\n            out.chapter = m.group(1).strip()\n            continue\n\n        m = CAPTION_RE.match(raw.strip())\n        if m:\n            pend_cap = m.group(1).strip()\n            continue\n        m = COLS_RE.match(raw.strip())\n        if m:\n            try:\n                pend_cols = [float(x) for x in m.group(1).split(\",\")]\n            except ValueError:\n                warn(f\"{ln}행: {{cols=…}}의 숫자를 읽지 못했다 → 균등 분배\")\n                pend_cols = None\n            continue\n\n        if raw.lstrip().startswith(\"|\"):\n            rows: List[List[str]] = []\n            j = i - 1\n            while j < len(lines) and lines[j].lstrip().startswith(\"|\"):\n                row = lines[j].strip()\n                if not SEP_ROW_RE.match(row):\n                    rows.append([c.strip() for c in row.strip(\"|\").split(\"|\")])\n                j += 1\n            i = j\n            if rows:\n                width = len(rows[0])\n                for k, row in enumerate(rows):\n                    if len(row) != width:\n                        warn(f\"{ln}행 표: {k + 1}번째 행의 칸이 {len(row)}개 \"\n                             f\"(머리행은 {width}개) → 빈 칸을 채우거나 잘라 맞췄다\")\n                        rows[k] = (row + [\"\"] * width)[:width]\n                if pend_cols and len(pend_cols) != width:\n                    warn(f\"{ln}행 표: {{cols}}가 {len(pend_cols)}개인데 칸은 {width}개 \"\n                         \"→ 무시하고 균등 분배\")\n                    pend_cols = None\n                if any(FOOTNOTE_REF_RE.search(c) for row in rows for c in row):\n                    warn(f\"{ln}행: 표 안에는 각주를 달 수 없다 → 표 아래 문단에 달 것\")\n                if pend_cap and not ((form.data.get(\"table\") or {}).get(\"caption\")):\n                    warn(f\"{ln}행: 이 양식에는 표 제목(캡션) 자리가 없어 \"\n                         f\"'{pend_cap}'을 넣지 못한다 → 표 위 문단으로 쓸 것\")\n                out.items.append(Item(\"table\", rows=rows, caption=pend_cap,\n                                      col_pct=pend_cols, line=ln))\n            pend_cap, pend_cols = \"\", None\n            continue\n\n        if pend_cap:\n            warn(f\"{ln}행: [표: {pend_cap}] 다음에 표가 없다 → 제목을 버렸다\")\n            pend_cap = \"\"\n\n        note_level = form.table_note\n        if note_level and note_level.get(\"marker\"):\n            head = f\"{note_level['marker']} \"\n            if raw.strip().startswith(head):\n                out.items.append(Item(\"table_note\", level=note_level,\n                                      text=raw.strip()[len(head):].strip(), line=ln))\n                continue\n\n        level, body = _match_marker(raw, form)\n        if level is None:\n            body = raw.strip()\n            plain = form.plain_level()\n            if plain is not None:\n                # 양식에 서술식 본문 자리가 있다 → 새 문단이다. 알릴 것 없다\n                level = plain\n            else:\n                level = form.fallback()\n                if out.items and out.items[-1].kind == \"para\":\n                    out.items[-1].text += \" \" + body\n                    warn(f\"{ln}행: 마커가 없는 줄 → 앞 문단에 이어 붙였다\")\n                    continue\n                warn(f\"{ln}행: 마커가 없는 줄 → \"\n                     f\"'{(level or {}).get('name', '기본')}' 레벨로 넣었다\")\n        if level is None:\n            warn(f\"{ln}행: 쓸 수 있는 레벨이 없어 줄을 버렸다\")\n            continue\n\n        if level.get(\"auto_bullet\") and body[:1] in \"□○-·･•▪◦∙※\":\n            warn(f\"{ln}행: 이 양식은 한글이 기호를 자동으로 붙인다\"\n                 f\"('{raw[:8]}…') → 마커 뒤에 기호를 또 쓰지 말 것\")\n        out.items.append(Item(\"para\", level=level, text=body, line=ln))\n\n    _resolve_notes(out, notes)\n    return out\n\n\ndef _match_marker(raw: str, form: Form) -> Tuple[Optional[Dict[str, Any]], str]:\n    stripped = raw.strip()\n    for marker, level in form.markers:\n        if stripped.startswith(marker + \" \"):\n            return level, stripped[len(marker) + 1:].strip()\n    return None, stripped\n\n\ndef _resolve_notes(out: Parsed, notes: Dict[str, Dict[str, Any]]) -> None:\n    for item in out.items:\n        if item.kind != \"para\":\n            continue\n        item.text, item.notes = _split_notes(item.text, notes, out.warnings, item.line)\n    for label, note in notes.items():\n        if not note[\"used\"]:\n            out.warnings.append(f\"각주 [^{label}]의 내용만 있고 본문에서 부르지 않았다 \"\n                                \"→ 각주를 만들지 않았다\")\n\n\ndef _split_notes(text: str, notes: Dict[str, Dict[str, Any]],\n                 warnings: List[str], line: int) -> Tuple[str, List[Dict[str, Any]]]:\n    out: List[str] = []\n    found: List[Dict[str, Any]] = []\n    pos = 0\n    for m in FOOTNOTE_REF_RE.finditer(text):\n        out.append(text[pos:m.start()])\n        pos = m.end()\n        label = m.group(1)\n        note = notes.get(label)\n        if note is None:\n            warnings.append(f\"{line}행: 각주 [^{label}]의 내용을 찾지 못했다 \"\n                            f\"(`[^{label}]: 내용` 줄이 없다) → 본문에 그대로 남긴다\")\n            out.append(m.group())\n            continue\n        note[\"used\"] += 1\n        if note[\"used\"] > 1:\n            warnings.append(f\"{line}행: 각주 [^{label}]을 두 번 이상 불렀다 \"\n                            \"→ 한글에는 각주 재사용이 없어 따로 만들어진다\")\n        before = \"\".join(out)\n        found.append({\"label\": label, \"text\": note[\"text\"], \"offset\": len(before),\n                      \"before\": before[-1:], \"after\": text[m.end():m.end() + 1]})\n    out.append(text[pos:])\n    return \"\".join(out), found\n\n\n# ---------------------------------------------------------------------------\n# 검사\n# ---------------------------------------------------------------------------\ndef lint(parsed: Parsed, form: Form) -> List[str]:\n    issues: List[str] = list(parsed.warnings)\n    depth = {lv[\"key\"]: i for i, lv in enumerate(form.levels)}\n    # 마커도 자동 번호도 없는 레벨(서술식 본문·참고문헌 따위)은 어느 제목 밑에나\n    # 온다. 계층 순서를 따질 대상이 아니라 레벨 점프 검사에서 뺀다.\n    free_keys = {lv[\"key\"] for lv in form.levels\n                 if not lv.get(\"marker\") or not (lv.get(\"auto_bullet\")\n                                                 or lv.get(\"auto_number\")\n                                                 or lv.get(\"write_marker\"))}\n    prev_key: Optional[str] = None\n    note_no = 0\n\n    for index, item in enumerate(parsed.items):\n        if item.kind == \"table_note\":\n            before = _previous_kind(parsed.items, index)\n            if before != \"table\":\n                issues.append(f\"{item.line}행: 표 주는 표 바로 아래에 두는 줄이다 \"\n                              f\"(지금은 {'문서 맨 앞' if before is None else before} 뒤) \"\n                              \"→ 자리를 옮기거나 본문 레벨로 쓸 것\")\n            continue\n        if item.kind == \"table\":\n            continue\n        if item.kind == \"blank\":\n            continue\n        key = (item.level or {}).get(\"key\", \"\")\n        if not item.text.strip():\n            issues.append(f\"{item.line}행: 내용이 빈 문단\")\n        if (prev_key is not None and key in depth and prev_key in depth\n                and key not in free_keys and prev_key not in free_keys):\n            if depth[key] - depth[prev_key] > 1:\n                issues.append(f\"{item.line}행: {prev_key} 다음에 {key}가 왔다 \"\n                              \"→ 중간 레벨을 건너뛰었다\")\n        prev_key = key\n\n        for note in item.notes:\n            note_no += 1\n            issues += _note_issues(note, note_no, item.line, item.level or {})\n\n    for idx, item in enumerate(parsed.items):\n        if item.kind != \"table\":\n            continue\n        before = parsed.items[idx - 1].kind if idx > 0 else \"blank\"\n        after = parsed.items[idx + 1].kind if idx + 1 < len(parsed.items) else \"blank\"\n        if before != \"blank\":\n            issues.append(f\"{item.line}행: 표 앞에 빈 줄이 없다\")\n        # 표 주는 표에 딸린 줄이라 사이에 빈 줄을 두지 않는다\n        if after not in (\"blank\", \"table_note\"):\n            issues.append(f\"{item.line}행: 표 뒤에 빈 줄이 없다\")\n    return issues\n\n\ndef _previous_kind(items: Sequence[Item], index: int) -> Optional[str]:\n    \"\"\"빈 줄을 건너뛰고 바로 앞 블록의 종류.\"\"\"\n    for item in reversed(items[:index]):\n        if item.kind != \"blank\":\n            return item.kind\n    return None\n\n\ndef _note_issues(note: Dict[str, Any], number: int, line: int,\n                 level: Dict[str, Any]) -> List[str]:\n    out: List[str] = []\n    where = f\"각주 {number}\"\n    before, after = str(note.get(\"before\", \"\")), str(note.get(\"after\", \"\"))\n    label = str(note.get(\"label\", \"\"))\n    if (level.get(\"marker\") or \"\") in (\"#\", \"##\", \"###\", \"####\") or level.get(\"auto_number\"):\n        out.append(f\"{line}행: {where} — 제목에 각주를 달았다 → 본문 문단으로 옮길 것\")\n    if not before:\n        out.append(f\"{line}행: {where} — 문단 맨 앞에 번호가 왔다 → 근거가 되는 말 뒤에 붙일 것\")\n    elif before.isspace():\n        out.append(f\"{line}행: {where} — 번호 앞에 빈칸이 있다 → 앞말에 붙여 쓸 것\")\n    if before and before in SENTENCE_END:\n        out.append(f\"{line}행: {where} — 마침표 뒤에 번호가 왔다 → 마침표 앞에 붙일 것\")\n    if label.isdigit() and int(label) != number:\n        out.append(f\"{line}행: {where} — [^{label}]로 적었지만 문서 순서로는 {number}번째다 \"\n                   \"→ 번호는 한글이 매긴다\")\n    return out\n\n\n# ---------------------------------------------------------------------------\n# XML 만들기\n# ---------------------------------------------------------------------------\ndef esc(text: str) -> str:\n    return (text.replace(\"&\", \"&amp;\").replace(\"<\", \"&lt;\").replace(\">\", \"&gt;\"))\n\n\ndef _t(text: str) -> str:\n    return f\"<hp:t>{esc(text)}</hp:t>\" if text else \"<hp:t/>\"\n\n\ndef paragraph(style: int, para: int, char: int, text: str,\n              notes: Sequence[Dict[str, Any]] = (), first_note: int = 1,\n              note_refs: Tuple[int, int, int] = (0, 0, 0)) -> str:\n    if notes:\n        runs = _runs_with_notes(char, text, notes, first_note, note_refs)\n    else:\n        runs = f'<hp:run charPrIDRef=\"{char}\">{_t(text)}</hp:run>'\n    return (f'<hp:p id=\"0\" paraPrIDRef=\"{para}\" styleIDRef=\"{style}\" '\n            f'pageBreak=\"0\" columnBreak=\"0\" merged=\"0\">{runs}</hp:p>')\n\n\n_note_instid = [1500000000]\n\n\ndef foot_note_xml(number: int, refs: Tuple[int, int, int], text: str) -> str:\n    style, para, char = refs\n    _note_instid[0] += 1\n    return (\n        '<hp:ctrl>'                                   # 각주는 ctrl로 감싼다\n        f'<hp:footNote number=\"{number}\" suffixChar=\"41\" instid=\"{_note_instid[0]}\">'\n        f'<hp:subList id=\"\" textDirection=\"HORIZONTAL\" lineWrap=\"BREAK\" vertAlign=\"TOP\" '\n        f'linkListIDRef=\"0\" linkListNextIDRef=\"0\" textWidth=\"0\" textHeight=\"0\" '\n        f'hasTextRef=\"0\" hasNumRef=\"0\">'\n        f'<hp:p id=\"0\" paraPrIDRef=\"{para}\" styleIDRef=\"{style}\" '\n        f'pageBreak=\"0\" columnBreak=\"0\" merged=\"0\">'\n        f'<hp:run charPrIDRef=\"{char}\"><hp:ctrl>'\n        f'<hp:autoNum num=\"{number}\" numType=\"FOOTNOTE\">'\n        f'<hp:autoNumFormat type=\"DIGIT\" userChar=\"\" prefixChar=\"\" suffixChar=\")\" '\n        f'supscript=\"0\"/></hp:autoNum></hp:ctrl>'\n        f'{_t(text)}</hp:run></hp:p></hp:subList></hp:footNote></hp:ctrl>')\n\n\ndef _runs_with_notes(char: int, text: str, notes: Sequence[Dict[str, Any]],\n                     first_number: int, refs: Tuple[int, int, int]) -> str:\n    \"\"\"각주 번호가 놓일 자리에서 run을 끊는다. 자리가 지켜지는 근거다.\"\"\"\n    marks = sorted(min(max(int(n.get(\"offset\", 0)), 0), len(text)) for n in notes)\n    order = sorted(range(len(notes)),\n                   key=lambda i: min(max(int(notes[i].get(\"offset\", 0)), 0), len(text)))\n    chunks: List[Dict[str, Any]] = [{\"text\": text[:marks[0]], \"notes\": []}]\n    for pos, idx in enumerate(order):\n        chunks[-1][\"notes\"].append(\n            foot_note_xml(first_number + pos, refs, str(notes[idx].get(\"text\", \"\"))))\n        end = marks[pos + 1] if pos + 1 < len(marks) else len(text)\n        piece = text[marks[pos]:end]\n        if piece:\n            chunks.append({\"text\": piece, \"notes\": []})\n    return \"\".join(\n        f'<hp:run charPrIDRef=\"{char}\">{_t(c[\"text\"])}{\"\".join(c[\"notes\"])}</hp:run>'\n        for c in chunks)\n\n\ndef cell_paragraphs(text: str, refs: Tuple[int, int, int]) -> str:\n    style, para, char = refs\n    parts = [p.strip() for p in re.split(r\"<br\\s*/?>\", text)] or [\"\"]\n    return \"\".join(paragraph(style, para, char, part) for part in parts)\n\n\ndef caption_xml(title: str, shape: Dict[str, Any], width: int,\n                roman: Optional[str] = None) -> str:\n    before = shape.get(\"before\") or \"<표 \"\n    after = shape.get(\"after\") or \"> \"\n    old = shape.get(\"chapter_roman\")\n    if roman and old and old != roman:\n        before = before.replace(old, roman)      # <표 Ⅱ- → <표 Ⅲ-\n    fmt = shape.get(\"auto_num_format\") or (\n        '<hp:autoNumFormat type=\"DIGIT\" userChar=\"\" prefixChar=\"\" suffixChar=\"\" '\n        'supscript=\"0\"/>')\n    number = (\"<hp:ctrl><hp:autoNum num=\\\"1\\\" numType=\\\"TABLE\\\">\"\n              f\"{fmt}</hp:autoNum></hp:ctrl>\") if shape.get(\"auto_num\") else \"\"\n    return (\n        f'<hp:caption side=\"{shape.get(\"side\", \"TOP\")}\" fullSz=\"0\" '\n        f'width=\"{shape.get(\"width\", 8504)}\" gap=\"{shape.get(\"gap\", 850)}\" '\n        f'lastWidth=\"{width}\">'\n        f'<hp:subList id=\"\" textDirection=\"HORIZONTAL\" lineWrap=\"BREAK\" vertAlign=\"TOP\" '\n        f'linkListIDRef=\"0\" linkListNextIDRef=\"0\" textWidth=\"0\" textHeight=\"0\" '\n        f'hasTextRef=\"0\" hasNumRef=\"0\">'\n        f'<hp:p id=\"0\" paraPrIDRef=\"{shape.get(\"para\", 0)}\" '\n        f'styleIDRef=\"{shape.get(\"style\", 0)}\" pageBreak=\"0\" columnBreak=\"0\" merged=\"0\">'\n        f'<hp:run charPrIDRef=\"{shape.get(\"char\", 0)}\">'\n        f'{_t(before)}{number}{_t(after + title)}'\n        f'</hp:run></hp:p></hp:subList></hp:caption>')\n\n\n_table_seq = [900000000]\n\n\ndef table_xml(item: Item, form: Form, roman: Optional[str] = None) -> str:\n    spec = form.data.get(\"table\") or {}\n    cell_refs = (int((spec.get(\"cell_para\") or {}).get(\"style\", 0)),\n                 int((spec.get(\"cell_para\") or {}).get(\"para\", 0)),\n                 int((spec.get(\"cell_para\") or {}).get(\"char\", 0)))\n    width = int(spec.get(\"width\", 39456))\n    row_h = int(spec.get(\"row_min_height\", 1182))\n    header_fill = int(spec.get(\"header_fill\", 1))\n    body_fill = int(spec.get(\"body_fill\", 1))\n    margin = spec.get(\"cell_margin\") or {\"left\": 494, \"right\": 494, \"top\": 0, \"bottom\": 0}\n    in_margin = spec.get(\"in_margin\") or {\"left\": 141, \"right\": 141, \"top\": 141, \"bottom\": 141}\n\n    ncols = len(item.rows[0])\n    if item.col_pct:\n        total = sum(item.col_pct)\n        widths = [int(width * p / total) for p in item.col_pct]\n    else:\n        widths = [width // ncols] * ncols\n    widths[-1] = width - sum(widths[:-1])          # 합이 표 폭과 어긋나지 않게\n\n    _table_seq[0] += 1\n    tid = _table_seq[0]\n\n    rows_xml = []\n    for r, row in enumerate(item.rows):\n        fill = header_fill if r == 0 else body_fill\n        cells = []\n        for c, cell in enumerate(row):\n            cells.append(\n                f'<hp:tc name=\"\" header=\"{1 if r == 0 else 0}\" hasMargin=\"0\" protect=\"0\" '\n                f'editable=\"0\" dirty=\"0\" borderFillIDRef=\"{fill}\">'\n                f'<hp:subList id=\"\" textDirection=\"HORIZONTAL\" lineWrap=\"BREAK\" '\n                f'vertAlign=\"CENTER\" linkListIDRef=\"0\" linkListNextIDRef=\"0\" '\n                f'textWidth=\"0\" textHeight=\"0\" hasTextRef=\"0\" hasNumRef=\"0\">'\n                f'{cell_paragraphs(cell, cell_refs)}</hp:subList>'\n                f'<hp:cellAddr colAddr=\"{c}\" rowAddr=\"{r}\"/>'\n                f'<hp:cellSpan colSpan=\"1\" rowSpan=\"1\"/>'\n                f'<hp:cellSz width=\"{widths[c]}\" height=\"{row_h}\"/>'\n                f'<hp:cellMargin left=\"{margin[\"left\"]}\" right=\"{margin[\"right\"]}\" '\n                f'top=\"{margin[\"top\"]}\" bottom=\"{margin[\"bottom\"]}\"/></hp:tc>')\n        rows_xml.append(\"<hp:tr>\" + \"\".join(cells) + \"</hp:tr>\")\n\n    caption_shape = spec.get(\"caption\")\n    caption = (caption_xml(item.caption, caption_shape, width, roman)\n               if (item.caption and caption_shape) else \"\")\n\n    tbl = (\n        f'<hp:tbl id=\"{tid}\" zOrder=\"{tid % 1000}\" numberingType=\"TABLE\" '\n        f'textWrap=\"TOP_AND_BOTTOM\" textFlow=\"BOTH_SIDES\" lock=\"0\" dropcapstyle=\"None\" '\n        f'pageBreak=\"CELL\" repeatHeader=\"1\" rowCnt=\"{len(item.rows)}\" colCnt=\"{ncols}\" '\n        f'cellSpacing=\"0\" borderFillIDRef=\"{spec.get(\"border_fill\", 1)}\" noAdjust=\"0\">'\n        f'<hp:sz width=\"{width}\" widthRelTo=\"ABSOLUTE\" '\n        f'height=\"{row_h * len(item.rows)}\" heightRelTo=\"ABSOLUTE\" protect=\"0\"/>'\n        f'<hp:pos treatAsChar=\"1\" affectLSpacing=\"0\" flowWithText=\"1\" allowOverlap=\"0\" '\n        f'holdAnchorAndSO=\"0\" vertRelTo=\"PARA\" horzRelTo=\"PARA\" vertAlign=\"TOP\" '\n        f'horzAlign=\"LEFT\" vertOffset=\"0\" horzOffset=\"0\"/>'\n        f'<hp:outMargin left=\"0\" right=\"0\" top=\"0\" bottom=\"0\"/>'\n        f'{caption}'\n        f'<hp:inMargin left=\"{in_margin[\"left\"]}\" right=\"{in_margin[\"right\"]}\" '\n        f'top=\"{in_margin[\"top\"]}\" bottom=\"{in_margin[\"bottom\"]}\"/>'\n        + \"\".join(rows_xml) + \"</hp:tbl>\")\n\n    style, para, char = form.refs(\"table_wrap\")\n    return (f'<hp:p id=\"0\" paraPrIDRef=\"{para}\" styleIDRef=\"{style}\" '\n            f'pageBreak=\"0\" columnBreak=\"0\" merged=\"0\">'\n            f'<hp:run charPrIDRef=\"{char}\">{tbl}<hp:t/></hp:run></hp:p>')\n\n\nclass Numbering:\n    \"\"\"도구가 직접 매기는 번호(양식이 한글 번호매기기를 안 쓸 때).\"\"\"\n\n    def __init__(self, form: Form) -> None:\n        self.depth = {lv[\"key\"]: i for i, lv in enumerate(form.levels)}\n        self.counts: Dict[str, int] = {}\n\n    def next(self, key: str, kind: str) -> str:\n        self.counts[key] = self.counts.get(key, 0) + 1\n        n = self.counts[key]\n        for other, level in list(self.counts.items()):     # 아래 레벨은 다시 1부터\n            if other != key and self.depth.get(other, 0) > self.depth.get(key, 0):\n                self.counts[other] = 0\n        if kind == \"AUTO_ROMAN\":\n            return f\"{ROMAN[(n - 1) % len(ROMAN)]}. \"\n        if kind == \"AUTO_NUM\":\n            return f\"{n}. \"\n        if kind == \"AUTO_ALPHA\":\n            return f\"{chr(ord('A') + (n - 1) % 26)}. \"\n        if kind == \"AUTO_CIRCLED\":\n            return f\"{CIRCLED[(n - 1) % len(CIRCLED)]} \"\n        if kind == \"AUTO_HANGUL\":\n            return f\"{HANGUL_ORDER[(n - 1) % len(HANGUL_ORDER)]}. \"\n        return \"\"\n\n\ndef build_body(parsed: Parsed, form: Form,\n               roman: Optional[str] = None) -> Tuple[str, Dict[str, int]]:\n    stats = {\"문단\": 0, \"표\": 0, \"각주\": 0, \"표 주\": 0}\n    note_refs = form.refs(\"footnote\") if form.data.get(\"footnote\") else (0, 0, 0)\n    numbering = Numbering(form)\n    note_no = 1\n    out: List[str] = []\n    for item in parsed.items:\n        if item.kind == \"blank\":\n            out.append(paragraph(*form.refs(\"blank\"), \"\"))\n            continue\n        if item.kind == \"table\":\n            out.append(table_xml(item, form, roman))\n            stats[\"표\"] += 1\n            continue\n        if item.kind == \"table_note\":\n            note = item.level or {}\n            text = (f\"{note.get('marker', '')} {item.text}\".strip()\n                    if note.get(\"write_marker\") else item.text)\n            out.append(paragraph(int(note.get(\"style\", 0)), int(note.get(\"para\", 0)),\n                                 int(note.get(\"char\", 0)), text))\n            stats[\"표 주\"] += 1\n            continue\n        level = item.level or {}\n        text = item.text\n        shift = 0\n        prefix = \"\"\n        if level.get(\"numbering\"):\n            prefix = numbering.next(level[\"key\"], level[\"numbering\"])\n        elif level.get(\"write_marker\"):\n            prefix = f\"{level['marker']} \"\n        if prefix:\n            text = prefix + text\n            shift = len(prefix)\n        notes = [dict(n, offset=int(n[\"offset\"]) + shift) for n in item.notes]\n        out.append(paragraph(int(level.get(\"style\", 0)), int(level.get(\"para\", 0)),\n                             int(level.get(\"char\", 0)), text, notes, note_no,\n                             note_refs))\n        note_no += len(notes)\n        stats[\"각주\"] += len(notes)\n        stats[\"문단\"] += 1\n    return \"\".join(out), stats\n\n\n# ---------------------------------------------------------------------------\n# 템플릿 조작\n# ---------------------------------------------------------------------------\ndef top_level_paragraphs(section_xml: str) -> List[Tuple[int, int, str]]:\n    depth = 0\n    tops: List[List[Any]] = []\n    for m in re.finditer(r\"<hp:p[ >][^>]*>|<hp:p/>|</hp:p>\", section_xml):\n        token = m.group(0)\n        if token.startswith(\"</\"):\n            depth -= 1\n            if depth == 0 and tops:\n                tops[-1][1] = m.end()\n        elif token == \"<hp:p/>\":\n            if depth == 0:\n                tops.append([m.start(), m.end(), token])\n        else:\n            if depth == 0:\n                tops.append([m.start(), None, token])\n            depth += 1\n    return [(s, e, t) for s, e, t in tops if e is not None]\n\n\n#: 이 태그가 든 문단은 본문이 아니라 **구역 정의**다. 스타일이 무엇이든 자른 앞에\n#: 남겨야 한다. 한글은 용지·여백을 `hp:secPr`로 읽고, 이것이 빠지면 문서를\n#: **기본 용지 A4로 연다** — 크라운판(166×241mm) 같은 양식이 통째로 어긋난다.\nSECTION_TAGS = (\"<hp:secPr\", \"<hp:colPr\")\n\n\ndef split_preamble(section_xml: str, body_styles: Sequence[int]) -> Tuple[str, str]:\n    \"\"\"(보존할 앞부분, 닫는 꼬리). 본문 스타일이 처음 나오는 문단에서 자른다.\n\n    구역 정의를 담은 문단은 건너뛴다. 빈 양식은 본문 문단이 하나뿐이고 그 하나가\n    용지 설정을 지고 있는 일이 흔한데, 거기서 자르면 용지가 날아간다.\n    \"\"\"\n    wanted = {str(s) for s in body_styles}\n    cut = None\n    for start, end, tag in top_level_paragraphs(section_xml):\n        if any(t in section_xml[start:end] for t in SECTION_TAGS):\n            continue\n        m = re.search(r'styleIDRef=\"(\\d+)\"', tag)\n        if m and m.group(1) in wanted:\n            cut = start\n            break\n    if cut is None:\n        cut = section_xml.rfind(\"</hs:sec>\")\n        if cut < 0:\n            raise SystemExit(\"[중단] 템플릿 본문에서 </hs:sec>를 찾지 못했다\")\n    return section_xml[:cut], \"</hs:sec>\"\n\n\ndef replace_chapter(preamble: str, roman: Optional[str],\n                    title: Optional[str]) -> Tuple[str, List[str]]:\n    \"\"\"장 표지의 로마자와 'Ⅱ. 제목'을 바꾼다.\n\n    보존 구간을 건드리는 유일한 곳이다. 그래서 **찾은 것만** 바꾸고, 못 찾으면\n    바꾸지 않고 그 사실을 말한다. 조용히 지나가면 옛 장 번호가 남은 문서가 나온다.\n    \"\"\"\n    notes: List[str] = []\n    if not roman and not title:\n        return preamble, notes\n\n    if roman:\n        head = preamble.find(\"<hp:container\")\n        tail = preamble.find(\"</hp:container>\", head) if head >= 0 else -1\n        if head >= 0 and tail >= 0:\n            segment, hits = re.subn(rf\"(<hp:t>)[{ROMAN_CHARS}](</hp:t>)\",\n                                    rf\"\\g<1>{roman}\\g<2>\", preamble[head:tail])\n            preamble = preamble[:head] + segment + preamble[tail:]\n            if not hits:\n                notes.append(\"표지 상자에서 로마자를 찾지 못해 장 번호를 바꾸지 않았다\")\n        else:\n            notes.append(\"표지 상자(hp:container)가 없어 장 번호를 바꾸지 않았다\")\n\n    if title:\n        pattern = re.compile(rf\"(<hp:t>)[{ROMAN_CHARS}]\\.\\s*[^<]*(</hp:t>)\")\n        preamble, hits = pattern.subn(\n            rf\"\\g<1>{roman or ''}. {esc(title)}\\g<2>\", preamble, count=1)\n        if not hits:\n            notes.append(\"장 제목('Ⅱ. …' 꼴)을 찾지 못해 제목을 바꾸지 않았다 \"\n                         \"→ 이 양식은 장 표지에 제목이 없을 수 있다\")\n    return preamble, notes\n\n\n# ---------------------------------------------------------------------------\n# 산출물 검사\n# ---------------------------------------------------------------------------\ndef check_refs(section_xml: str, header_xml: str) -> List[str]:\n    \"\"\"새로 쓴 본문이 양식에 없는 번호를 가리키지 않는지.\"\"\"\n    pools = {\n        \"styleIDRef\": set(re.findall(r'<hh:style id=\"(\\d+)\"', header_xml)),\n        \"paraPrIDRef\": set(re.findall(r'<hh:paraPr id=\"(\\d+)\"', header_xml)),\n        \"charPrIDRef\": set(re.findall(r'<hh:charPr id=\"(\\d+)\"', header_xml)),\n        \"borderFillIDRef\": set(re.findall(r'<hh:borderFill id=\"(\\d+)\"', header_xml)),\n    }\n    errs = []\n    for attr, pool in pools.items():\n        missing = set(re.findall(rf'{attr}=\"(\\d+)\"', section_xml)) - pool\n        if missing:\n            errs.append(f\"[참조 오류] 양식에 없는 {attr}: {sorted(missing)}\")\n    return errs\n\n\ndef check_double_bullets(section_xml: str, form: Form) -> List[str]:\n    \"\"\"한글이 기호를 붙이는 문단인데 텍스트도 기호로 시작하면 이중이다.\"\"\"\n    auto = {str(lv[\"para\"]): lv[\"auto_bullet\"] for lv in form.levels if lv.get(\"auto_bullet\")}\n    if not auto:\n        return []\n    errs = []\n    for m in re.finditer(r'<hp:p [^>]*paraPrIDRef=\"(\\d+)\"[^>]*>(.*?)</hp:p>',\n                         section_xml, re.S):\n        para_id, body = m.group(1), m.group(2)\n        if para_id not in auto:\n            continue\n        text = \"\".join(re.findall(r\"<hp:t>([^<]*)</hp:t>\", body)).lstrip()\n        if text[:1] in \"□○-·･•▪◦∙※\":\n            errs.append(f\"[이중 기호] 한글이 '{auto[para_id]}'를 붙이는 문단인데 \"\n                        f\"텍스트도 기호로 시작한다: {text[:24]!r} \"\n                        \"→ 본문에서 기호를 빼거나 --bullets hangul 로 만들 것\")\n    return errs\n\n\ndef check_output(path: Path) -> List[str]:\n    errs: List[str] = []\n    try:\n        with zipfile.ZipFile(path) as z:\n            broken = z.testzip()\n            if broken:\n                errs.append(f\"[zip 손상] {broken}\")\n            names = set(z.namelist())\n            for need in (\"mimetype\", \"Contents/header.xml\", \"Contents/content.hpf\",\n                         \"META-INF/container.xml\"):\n                if need not in names:\n                    errs.append(f\"[zip 누락] {need}\")\n            for name in names:\n                if name.endswith((\".xml\", \".hpf\")):\n                    try:\n                        xml.dom.minidom.parseString(z.read(name))\n                    except Exception as exc:                        # noqa: BLE001\n                        errs.append(f\"[XML 오류] {name}: {exc}\")\n    except Exception as exc:                                        # noqa: BLE001\n        errs.append(f\"[열기 실패] {exc}\")\n    return errs\n\n\n# ---------------------------------------------------------------------------\n# 조립\n# ---------------------------------------------------------------------------\ndef build(form: Form, template: Path, source: Path, out: Path,\n          check_only: bool, strict: bool, bullets: str = \"auto\",\n          chapter: Optional[int] = None) -> int:\n    chosen = form.apply_bullet_source(bullets)\n    parsed = parse_input(source.read_text(encoding=\"utf-8\"), form)\n    issues = lint(parsed, form) + chosen\n\n    roman = form.chapter_roman\n    if chapter is not None:\n        if not 1 <= chapter <= len(ROMAN):\n            raise SystemExit(f\"[중단] --chapter는 1~{len(ROMAN)} 사이여야 한다: {chapter}\")\n        roman = ROMAN[chapter - 1]\n    if parsed.chapter and not (form.data.get(\"chapter\") or {}):\n        issues.append(\"[장: …]을 적었지만 이 양식에는 장 표지가 없다 → 반영되지 않는다\")\n\n    print(\"── 1층 입력 검사 \" + \"─\" * 30)\n    for issue in issues:\n        print(\"  [경고]\", issue)\n    if not issues:\n        print(\"  이상 없음\")\n    if check_only:\n        return 1 if issues else 0\n    if issues and strict:\n        print(\"  → --strict라서 생성을 멈춘다\")\n        return 1\n\n    with zipfile.ZipFile(template) as z:\n        entries = {name: z.read(name) for name in z.namelist()}\n    if form.section not in entries:\n        raise SystemExit(f\"[중단] 템플릿에 {form.section}이 없다\")\n    section_xml = entries[form.section].decode(\"utf-8\")\n    header_xml = entries[\"Contents/header.xml\"].decode(\"utf-8\")\n\n    if not form.data.get(\"footnote\") and any(item.notes for item in parsed.items):\n        print(\"  [경고] 이 양식에는 각주 스타일이 없다 → 한글에서 각주 서식이 흐트러질 수 있다\")\n\n    preamble, tail = split_preamble(section_xml, form.body_styles)\n    if parsed.chapter or (chapter is not None and roman):\n        preamble, changed = replace_chapter(preamble, roman, parsed.chapter)\n        for note in changed:\n            print(\"  [알림]\", note)\n    body, stats = build_body(parsed, form, roman)\n    new_section = preamble + body + tail\n\n    print(\"── 2층 구조 검사 \" + \"─\" * 30)\n    errs = check_refs(new_section, header_xml) + check_double_bullets(new_section, form)\n    if errs:\n        for err in errs:\n            print(\" \", err)\n        print(\"  → 생성 중단\")\n        return 2\n    print(f\"  참조·이중 기호 이상 없음 \"\n          f\"(문단 {stats['문단']}, 표 {stats['표']}, 표 주 {stats['표 주']}, \"\n          f\"각주 {stats['각주']})\")\n\n    entries[form.section] = new_section.encode(\"utf-8\")\n    entries[\"Preview/PrvText.txt\"] = (\n        \"build_form.py로 만든 문서 — 한글에서 저장하면 미리보기가 갱신된다\"\n    ).encode(\"utf-16-le\")\n\n    buf = io.BytesIO()\n    with zipfile.ZipFile(buf, \"w\", zipfile.ZIP_DEFLATED) as z:\n        if \"mimetype\" in entries:\n            z.writestr(\"mimetype\", entries[\"mimetype\"], compress_type=zipfile.ZIP_STORED)\n        for name, data in entries.items():\n            if name != \"mimetype\":\n                z.writestr(name, data)\n    out.write_bytes(buf.getvalue())\n\n    print(\"── 3층 산출물 검사 \" + \"─\" * 29)\n    errs = check_output(out)\n    if errs:\n        for err in errs:\n            print(\" \", err)\n        return 3\n    print(\"  zip·XML 정상 →\", out)\n    print(\"  ※ 줄바꿈·쪽 나눔·표 높이는 한글이 열 때 다시 계산한다\")\n    return 0\n\n\ndef main(argv: Optional[Sequence[str]] = None) -> int:\n    ap = argparse.ArgumentParser(\n        description=\"양식 보존 방식 한글 문서 빌더\",\n        formatter_class=argparse.RawDescriptionHelpFormatter)\n    ap.add_argument(\"input\", nargs=\"?\", type=Path, help=\"마커 텍스트 파일\")\n    ap.add_argument(\"-o\", \"--output\", type=Path, default=Path(\"결과.hwpx\"))\n    ap.add_argument(\"--form\", type=Path, default=None, help=\"form.json 경로\")\n    ap.add_argument(\"--template\", type=Path, default=None, help=\"template.hwpx 경로\")\n    ap.add_argument(\"--check-only\", action=\"store_true\", help=\"입력 검사만\")\n    ap.add_argument(\"--strict\", action=\"store_true\", help=\"경고가 하나라도 있으면 만들지 않음\")\n    ap.add_argument(\"--markers\", action=\"store_true\", help=\"이 양식의 마커 목록\")\n    ap.add_argument(\"--chapter\", type=int, metavar=\"N\",\n                    help=\"장 번호(1=Ⅰ, 2=Ⅱ …). 표지 로마자와 표 번호 접두에 쓴다\")\n    ap.add_argument(\"--bullets\", default=\"auto\", choices=[\"auto\", \"hangul\", \"text\"],\n                    help=\"줄머리 기호를 누가 붙이나 \"\n                         \"(auto=양식대로, hangul=한글에 맡김, text=도구가 적음)\")\n    args = ap.parse_args(argv)\n\n    form = load_form(args.form)\n    if args.markers:\n        for warning in form.apply_bullet_source(args.bullets):\n            print(\"  [경고]\", warning)\n        print(f\"# {form.name} 마커\\n\")\n        print(form.marker_table())\n        return 0\n    if args.input is None:\n        ap.error(\"마커 텍스트 파일을 지정할 것 (또는 --markers)\")\n\n    template = args.template or (HERE / (form.data.get(\"template\") or \"template.hwpx\"))\n    if not template.exists():\n        raise SystemExit(f\"[중단] 양식 원본이 없다: {template}\")\n    if not args.input.exists():\n        raise SystemExit(f\"[중단] 입력 파일이 없다: {args.input}\")\n    return build(form, template, args.input, args.output, args.check_only,\n                 args.strict, args.bullets, args.chapter)\n\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n",
  "read_hwpx.py": "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\n\"\"\"서식 없는 한글 문서 → 마커 텍스트.\n\nAI가 만들었거나 손으로 대충 쓴 `.hwpx`를 읽어, 이 폴더의 양식으로 다시 만들 수 있는\n**마커 텍스트**로 되돌린다. 그 텍스트를 손본 뒤 `build_form.py`에 넣으면 양식대로\n갖춰진 문서가 나온다.\n\n    python read_hwpx.py 원본.hwpx -o 원고.md\n    python build_form.py 원고.md -o 결과.hwpx\n\n## 무엇을 어떻게 알아내나\n\n서식이 없는 문서에는 '이건 2단계 항목'이라는 표시가 없다. 그래서 다음을 근거로\n**추정한다.**\n\n  1. 줄머리 기호(`□ ○ - · ※`)\n  2. 줄머리 번호(`Ⅰ.` `1.` `가.` `1)`)\n  3. 글자 크기와 굵기\n  4. 들여쓰기\n\n추정한 결과는 `--report`로 볼 수 있다. **틀릴 수 있다.** 나온 텍스트를 사람이\n훑어보는 것을 전제로 만들었다.\n\n표는 파이프 표로, 각주는 `[^n]`과 `[^n]:` 줄로 되돌린다. 그림은 읽지 못하고\n`[그림 자리]`로 남긴다.\n\n의존성 없음(파이썬 표준 라이브러리만).\n\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport json\nimport re\nimport sys\nimport xml.etree.ElementTree as ET\nimport zipfile\nfrom dataclasses import dataclass, field\nfrom pathlib import Path\nfrom typing import Any, Dict, List, Optional, Sequence, Tuple\n\nHERE = Path(__file__).resolve().parent\n\nNS = {\n    \"hh\": \"http://www.hancom.co.kr/hwpml/2011/head\",\n    \"hp\": \"http://www.hancom.co.kr/hwpml/2011/paragraph\",\n}\nHWP_BINARY_MAGIC = b\"\\xd0\\xcf\\x11\\xe0\\xa1\\xb1\\x1a\\xe1\"\n\n#: 줄머리 기호 사다리. 앞에 있을수록 큰 단위다.\nSYMBOL_LADDER = [\"□\", \"■\", \"○\", \"●\", \"-\", \"–\", \"·\", \"･\", \"•\", \"※\"]\n\n#: 줄머리 번호 유형. 앞에 있을수록 큰 단위다.\nNUMBER_PATTERNS: List[Tuple[str, \"re.Pattern[str]\"]] = [\n    (\"ROMAN\", re.compile(r\"^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]+\\s*[.)]\\s+\")),\n    (\"DIGIT_DOT\", re.compile(r\"^\\d{1,2}\\.\\s+\")),\n    (\"HANGUL\", re.compile(r\"^[가-힣]\\.\\s+\")),\n    (\"DIGIT_PAREN\", re.compile(r\"^\\d{1,2}\\)\\s+\")),\n    (\"CIRCLED\", re.compile(r\"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]\\s*\")),\n]\n\n\n# ---------------------------------------------------------------------------\n# 읽기\n# ---------------------------------------------------------------------------\n@dataclass\nclass Block:\n    kind: str                    # para / table / picture\n    text: str = \"\"\n    rows: List[List[str]] = field(default_factory=list)\n    notes: List[Tuple[int, str]] = field(default_factory=list)   # (자리, 내용)\n    size_pt: float = 10.0\n    bold: bool = False\n    left_pt: float = 0.0\n    depth: int = 0\n    symbol: Optional[str] = None\n    number: Optional[str] = None\n\n\ndef _open_parts(path: Path) -> Dict[str, str]:\n    head = path.read_bytes()[:8]\n    if head.startswith(HWP_BINARY_MAGIC):\n        raise SystemExit(\n            f\"[중단] {path}는 한글 바이너리(.hwp)다. 한글에서 [다른 이름으로 저장] → \"\n            \"'HWPX 문서'로 저장한 뒤 다시 할 것\")\n    if not head.startswith(b\"PK\"):\n        raise SystemExit(f\"[중단] {path}를 hwpx로 열 수 없다(zip이 아니다)\")\n    with zipfile.ZipFile(path) as z:\n        return {name: z.read(name).decode(\"utf-8\", \"replace\")\n                for name in z.namelist() if name.startswith(\"Contents/\")\n                and name.endswith(\".xml\")}\n\n\ndef _char_sizes(header_xml: str) -> Dict[int, Tuple[float, bool]]:\n    out: Dict[int, Tuple[float, bool]] = {}\n    root = ET.fromstring(header_xml)\n    for cp in root.iter(f\"{{{NS['hh']}}}charPr\"):\n        bold = (cp.find(f\"{{{NS['hh']}}}bold\") is not None\n                or cp.get(\"bold\") in (\"1\", \"true\"))\n        out[int(cp.get(\"id\", \"0\"))] = (int(cp.get(\"height\", \"1000\")) / 100.0, bold)\n    return out\n\n\ndef _left_margins(header_xml: str) -> Dict[int, float]:\n    out: Dict[int, float] = {}\n    root = ET.fromstring(header_xml)\n    for pp in root.iter(f\"{{{NS['hh']}}}paraPr\"):\n        margin = pp.find(f\".//{{{NS['hh']}}}margin\")\n        left = 0.0\n        if margin is not None:\n            for child in margin:\n                if child.tag.endswith(\"}left\"):\n                    left = float(child.get(\"value\", \"0\")) / 100.0\n        out[int(pp.get(\"id\", \"0\"))] = left\n    return out\n\n\ndef read_blocks(path: Path) -> List[Block]:\n    parts = _open_parts(path)\n    header = parts.get(\"Contents/header.xml\", \"<x/>\")\n    sizes = _char_sizes(header)\n    lefts = _left_margins(header)\n    blocks: List[Block] = []\n\n    for name in sorted(n for n in parts if re.match(r\"Contents/section\\d+\\.xml$\", n)):\n        _read_section(ET.fromstring(parts[name]), sizes, lefts, blocks)\n    return blocks\n\n\ndef _paragraph_text(node) -> Tuple[str, List[Tuple[int, str]], Optional[int]]:\n    \"\"\"문단의 글자, 각주 자리, 첫 글자모양 번호.\"\"\"\n    text_parts: List[str] = []\n    notes: List[Tuple[int, str]] = []\n    char_id: Optional[int] = None\n    for run in node.findall(f\"{{{NS['hp']}}}run\"):\n        if char_id is None and run.get(\"charPrIDRef\") is not None:\n            char_id = int(run.get(\"charPrIDRef\"))\n        for child in run:\n            tag = child.tag.split(\"}\")[-1]\n            if tag == \"t\":\n                text_parts.append(\"\".join(child.itertext()))\n            elif tag == \"footNote\":\n                notes.append((sum(len(p) for p in text_parts), _note_text(child)))\n            elif tag == \"ctrl\":\n                # 한글은 각주를 hp:ctrl로 감싼다\n                for note in child.findall(f\"{{{NS['hp']}}}footNote\"):\n                    notes.append((sum(len(p) for p in text_parts), _note_text(note)))\n    return \"\".join(text_parts), notes, char_id\n\n\ndef _note_text(node) -> str:\n    out = []\n    for t in node.iter(f\"{{{NS['hp']}}}t\"):\n        out.append(\"\".join(t.itertext()))\n    return \"\".join(out).strip()\n\n\ndef _cell_text(cell) -> str:\n    lines = []\n    for p in cell.iter(f\"{{{NS['hp']}}}p\"):\n        text, _notes, _c = _paragraph_text(p)\n        if text.strip():\n            lines.append(text.strip())\n    return \"<br>\".join(lines)\n\n\ndef _read_section(root, sizes, lefts, blocks: List[Block]) -> None:\n    def walk(node) -> None:\n        for child in node:\n            tag = child.tag.split(\"}\")[-1]\n            if tag in (\"footNote\", \"endNote\", \"header\", \"footer\", \"caption\"):\n                continue\n            if tag == \"tbl\":\n                rows = []\n                for tr in child.findall(f\"{{{NS['hp']}}}tr\"):\n                    rows.append([_cell_text(tc)\n                                 for tc in tr.findall(f\"{{{NS['hp']}}}tc\")])\n                if rows:\n                    blocks.append(Block(\"table\", rows=rows))\n                continue\n            if tag == \"pic\":\n                blocks.append(Block(\"picture\"))\n                continue\n            if tag == \"p\":\n                text, notes, char_id = _paragraph_text(child)\n                if text.strip():\n                    size, bold = sizes.get(char_id or 0, (10.0, False))\n                    blocks.append(Block(\n                        \"para\", text=text.strip(), notes=notes,\n                        size_pt=size, bold=bold,\n                        left_pt=lefts.get(int(child.get(\"paraPrIDRef\", \"0\")), 0.0)))\n                walk(child)\n                continue\n            walk(child)\n\n    walk(root)\n\n\n# ---------------------------------------------------------------------------\n# 계층 추정\n# ---------------------------------------------------------------------------\ndef _cut_prefix(block: Block, size: int) -> None:\n    \"\"\"줄머리 기호·번호를 떼면서 각주 자리도 같이 당긴다.\"\"\"\n    rest = block.text[size:]\n    dropped = size + len(rest) - len(rest.lstrip())     # 기호 + 뒤따른 빈칸\n    block.text = rest.strip()\n    block.notes = [(max(offset - dropped, 0), note) for offset, note in block.notes]\n\n\ndef classify(blocks: Sequence[Block]) -> List[str]:\n    \"\"\"각 문단의 깊이를 매긴다. 근거를 문장으로 돌려준다.\"\"\"\n    notes: List[str] = []\n    for block in blocks:\n        if block.kind != \"para\":\n            continue\n        lead = block.text[:1]\n        if lead in SYMBOL_LADDER and block.text[1:2] in (\" \", \"　\"):\n            block.symbol = lead\n            _cut_prefix(block, 2)\n            continue\n        for kind, pattern in NUMBER_PATTERNS:\n            m = pattern.match(block.text)\n            if m:\n                block.number = kind\n                _cut_prefix(block, m.end())\n                break\n\n    sizes = sorted({b.size_pt for b in blocks if b.kind == \"para\"}, reverse=True)\n    number_kinds = [k for k, _ in NUMBER_PATTERNS\n                    if any(b.number == k for b in blocks if b.kind == \"para\")]\n    symbols = [s for s in SYMBOL_LADDER\n               if any(b.symbol == s for b in blocks if b.kind == \"para\")]\n\n    if number_kinds:\n        notes.append(\"줄머리 번호로 제목을 갈랐다: \" + \", \".join(number_kinds))\n    if symbols:\n        notes.append(\"줄머리 기호로 본문 단계를 갈랐다: \" + \" \".join(symbols))\n    if not number_kinds and not symbols:\n        notes.append(\"줄머리 기호·번호가 없어 **글자 크기만으로** 갈랐다 \"\n                     \"→ 결과를 반드시 훑어볼 것\")\n\n    for block in blocks:\n        if block.kind != \"para\":\n            continue\n        if block.number:\n            block.depth = number_kinds.index(block.number)\n        elif block.symbol:\n            block.depth = len(number_kinds) + symbols.index(block.symbol)\n        else:\n            rank = sizes.index(block.size_pt) if block.size_pt in sizes else len(sizes)\n            block.depth = len(number_kinds) + len(symbols) + rank\n    return notes\n\n\n# ---------------------------------------------------------------------------\n# 마커 텍스트로 쓰기\n# ---------------------------------------------------------------------------\ndef to_marker_text(blocks: Sequence[Block], markers: Sequence[str]) -> str:\n    depths = sorted({b.depth for b in blocks if b.kind == \"para\"})\n    mapping = {d: markers[min(i, len(markers) - 1)] if markers else \"\"\n               for i, d in enumerate(depths)}\n\n    lines: List[str] = []\n    note_no = 0\n    definitions: List[str] = []\n    prev_kind = \"\"\n\n    for block in blocks:\n        if block.kind == \"picture\":\n            _blank(lines, prev_kind)\n            lines.append(\"[그림 자리 — 도식이면 :::diagram 블록으로 옮길 것]\")\n            prev_kind = \"picture\"\n            continue\n        if block.kind == \"table\":\n            _blank(lines, prev_kind)\n            width = max(len(r) for r in block.rows)\n            for i, row in enumerate(block.rows):\n                cells = (row + [\"\"] * width)[:width]\n                lines.append(\"| \" + \" | \".join(cells) + \" |\")\n                if i == 0:\n                    lines.append(\"|\" + \"---|\" * width)\n            lines.append(\"\")\n            prev_kind = \"table\"\n            continue\n\n        text = block.text\n        # 번호는 앞에서부터 매기고, 글자는 뒤에서부터 끼워 넣는다(자리가 밀리지 않게)\n        numbered = [(offset, note, note_no + i + 1)\n                    for i, (offset, note) in enumerate(sorted(block.notes,\n                                                              key=lambda n: n[0]))]\n        note_no += len(numbered)\n        for offset, note, number in sorted(numbered, key=lambda n: -n[0]):\n            cut = min(max(offset, 0), len(text))\n            text = f\"{text[:cut]}[^{number}]{text[cut:]}\"\n        definitions += [f\"[^{number}]: {note}\" for _o, note, number in numbered]\n        marker = mapping.get(block.depth, \"\")\n        lines.append(f\"{marker} {text}\".strip() if marker else text)\n        prev_kind = \"para\"\n\n    if definitions:\n        lines.append(\"\")\n        lines += sorted(definitions, key=lambda d: int(re.findall(r\"\\d+\", d)[0]))\n    return \"\\n\".join(lines).rstrip() + \"\\n\"\n\n\ndef _blank(lines: List[str], prev_kind: str) -> None:\n    if lines and lines[-1] != \"\":\n        lines.append(\"\")\n\n\ndef pt(value: float) -> str:\n    \"\"\"11.0 대신 11로 적는다. 브라우저 쪽 표기와 같아야 한다.\"\"\"\n    return f\"{float(value):g}\"\n\n\ndef render_report(blocks: Sequence[Block], markers: Sequence[str],\n                  notes: Sequence[str]) -> str:\n    depths = sorted({b.depth for b in blocks if b.kind == \"para\"})\n    out = [\"# 읽어 들인 결과\", \"\",\n           \"**추정이다.** 아래 대응이 뜻과 다르면 나온 텍스트에서 마커를 고치면 된다.\",\n           \"\", \"| 원본의 단계 | 근거 | 문단 수 | 이 양식의 마커 |\", \"|---|---|---|---|\"]\n    for i, depth in enumerate(depths):\n        members = [b for b in blocks if b.kind == \"para\" and b.depth == depth]\n        why = (f\"번호 {members[0].number}\" if members[0].number\n               else f\"기호 `{members[0].symbol}`\" if members[0].symbol\n               else f\"글자 {pt(members[0].size_pt)}pt\")\n        marker = markers[min(i, len(markers) - 1)] if markers else \"(없음)\"\n        out.append(f\"| {i + 1}단계 | {why} | {len(members)} | `{marker}` |\")\n\n    tables = sum(1 for b in blocks if b.kind == \"table\")\n    pics = sum(1 for b in blocks if b.kind == \"picture\")\n    notes_n = sum(len(b.notes) for b in blocks)\n    out += [\"\", f\"- 표 {tables}개, 각주 {notes_n}개, 그림 {pics}개\"]\n    if pics:\n        out.append(\"- **그림은 읽지 못한다.** `[그림 자리]`로 남겼다. 조직도·절차도라면 \"\n                   \"그림을 보고 도식 블록으로 옮겨 적어야 한다\")\n    out += [\"\"] + [f\"- {n}\" for n in notes]\n    return \"\\n\".join(out) + \"\\n\"\n\n\ndef load_markers(form_path: Optional[Path]) -> Tuple[List[str], str]:\n    path = form_path or (HERE / \"form.json\")\n    if not path.exists():\n        return [], \"(양식 없음 — 기호를 그대로 둔다)\"\n    form = json.loads(path.read_text(encoding=\"utf-8\"))\n    return ([lv.get(\"marker\", \"\") for lv in form.get(\"levels\", []) if lv.get(\"marker\")],\n            form.get(\"name\", \"양식\"))\n\n\ndef main(argv: Optional[Sequence[str]] = None) -> int:\n    ap = argparse.ArgumentParser(description=\"서식 없는 hwpx → 마커 텍스트\")\n    ap.add_argument(\"source\", type=Path, help=\"읽어 들일 .hwpx\")\n    ap.add_argument(\"-o\", \"--output\", type=Path, help=\"저장할 마커 텍스트(.md)\")\n    ap.add_argument(\"--form\", type=Path, default=None, help=\"form.json 경로\")\n    ap.add_argument(\"--report\", type=Path, help=\"추정 근거를 저장할 경로\")\n    args = ap.parse_args(argv)\n\n    if not args.source.exists():\n        raise SystemExit(f\"[중단] 파일이 없다: {args.source}\")\n\n    blocks = read_blocks(args.source)\n    if not blocks:\n        raise SystemExit(\"[중단] 읽을 내용이 없다\")\n    notes = classify(blocks)\n    markers, form_name = load_markers(args.form)\n\n    text = to_marker_text(blocks, markers)\n    report = render_report(blocks, markers, notes)\n\n    if args.output:\n        args.output.write_text(text, encoding=\"utf-8\")\n        print(f\"마커 텍스트 저장 → {args.output}\")\n    else:\n        print(text)\n    if args.report:\n        args.report.write_text(report, encoding=\"utf-8\")\n        print(f\"근거 저장 → {args.report}\")\n    else:\n        print(report, file=sys.stderr)\n    print(f\"양식: {form_name} — 다음은 `python build_form.py \"\n          f\"{args.output or '원고.md'} -o 결과.hwpx`\", file=sys.stderr)\n    return 0\n\n\nif __name__ == \"__main__\":\n    sys.exit(main())\n"
};

export const FORM_TEMPLATES = {
  "README.md": "# {{name}} — 한글 문서 꾸러미\n\n이 폴더 하나로 **{{name}} 서식 그대로** 한글 문서(.hwpx)를 만든다.\n\n## 어떻게 서식이 지켜지나\n\n`template.hwpx`(양식 원본)를 고치지 않는다. 스타일·글꼴·자동 글머리표·번호매기기·\n쪽 설정이 들어 있는 `header.xml`은 **한 바이트도 건드리지 않고**, 본문 문단만 새로\n만들어 갈아 끼운다. 그래서 서식이 재현이 아니라 **보존**된다.\n\n## 쓰는 법\n\n```bash\npython build_form.py 원고.md -o 결과.hwpx\npython build_form.py 원고.md --check-only    # 입력 검사만\npython build_form.py --markers               # 마커 목록\n```\n\n### 장 번호·표 번호\n\n양식에 장 표지나 표 번호(`<표 Ⅱ-1>`)가 있으면 장 번호를 바꿔 넣을 수 있다.\n\n```bash\npython build_form.py 원고.md -o 결과.hwpx --chapter 3     # Ⅲ장\n```\n\n표지 로마자와 표 번호 접두가 함께 바뀐다. 장 제목은 원고에 `[장: 제목]`으로 적는다\n(문서에 하나). 양식에 그 자리가 없으면 바꾸지 않고 그 사실을 알린다.\n\n### 표 주(자료 줄)\n\n양식에 표 주 스타일이 있으면 표 **바로 아래**에 `※ 자료：…`로 적는다. 사이에 빈 줄을\n두지 않는다. 표에서 떨어져 있으면 검사가 알려 준다.\n\n### 줄머리 기호를 누가 붙이나\n\n한글은 문단 스타일에 **자동 글머리표**를 걸어 둘 수 있다. 그런 양식이면 본문에\n기호를 또 적으면 두 번 찍히고, 그렇지 않은 양식이면 도구가 적어야 한다.\n해부할 때 양식을 보고 갈라 두었지만, 다르게 잡혔으면 만들 때 바꿀 수 있다.\n\n```bash\npython build_form.py 원고.md -o 결과.hwpx --bullets hangul   # 한글에 맡김\npython build_form.py 원고.md -o 결과.hwpx --bullets text     # 도구가 적음\n```\n\n고른 값이 양식과 어긋나면 검사가 알려 준다. 레벨마다 따로 정하려면 `form.json`의\n`levels[].write_marker`를 고친다(`--bullets auto`가 그 값을 그대로 쓴다).\n\n### 이미 있는 한글 파일을 이 양식으로 바꾸기\n\n서식이 안 갖춰진 `.hwpx`가 있으면 먼저 마커 텍스트로 되돌린 뒤 다시 만든다.\n\n```bash\npython read_hwpx.py 받은문서.hwpx -o 원고.md --report 추정근거.md\npython build_form.py 원고.md -o 결과.hwpx\n```\n\n되돌리기는 **추정**이다. `추정근거.md`에 무엇을 근거로 단계를 갈랐는지 적혀 있으니\n한 번 보고 `원고.md`의 마커를 고친 뒤 만드는 것이 좋다. 그림은 읽지 못하고\n`[그림 자리]`로 남는다.\n\nAI(Claude·GPT·codex)에게는 이 폴더를 통째로 주고 \"원고를 마커 텍스트로 쓴 뒤\n`build_form.py`로 만들어 달라\"고 하면 된다. 지시문은 `SKILL.md`(Claude)와\n`AGENTS.md`(codex·GPT)에 들어 있다.\n\n## 마커\n\n{{markers}}\n\n## 공통 문법\n\n| 쓰는 법 | 결과 |\n|---|---|\n| (빈 줄) | 문단 사이 간격 |\n| `\\| 구분 \\| 값 \\|` | 표. 첫 행이 머리행. `\\|---\\|` 줄은 무시 |\n| `[표: 제목]` | 바로 다음 표의 제목 |\n| `{cols=30,35,35}` | 바로 다음 표의 열 너비 백분율 |\n| 셀 안 `<br>` | 셀 안에서 줄 나눔 |\n| `앞말[^1]` | 각주 번호 자리 |\n| `[^1]: 내용` | 각주 내용(문서 어디에 적어도 된다) |\n\n## 확인할 것\n\n- 만든 문서를 **한글에서 한 번 열어 볼 것.** 줄바꿈·쪽 나눔·표 높이는 한글이 열 때\n  다시 계산한다\n- 마커가 뜻대로 잡혔는지는 `해부보고서.md`에 근거가 있다. 다르면 `form.json`의\n  `levels`를 고치면 된다\n",
  "SKILL.md": "---\nname: {{slug}}\ndescription: >-\n  {{name}} 서식 그대로 한글 문서(.hwpx)를 만든다. 마커를 붙인 텍스트로 본문을 쓰면\n  양식의 스타일·글꼴·자동 글머리표를 그대로 지킨 hwpx가 나온다. {{footnote}}'{{name}}',\n  '이 양식으로', '한글 보고서', '.hwpx로 만들어줘' 요청 시 사용.\n---\n\n# {{name}} 문서 만들기\n\n## 무엇을 하는 스킬인가\n\n`{{name}}` 양식 원본을 고치지 않고 본문만 갈아 끼워 한글 문서를 만든다. 서식을\n흉내 내는 것이 아니라 **양식 파일 자체를 쓰기 때문에** 글꼴·자동 글머리표·\n번호매기기·쪽 설정이 원본 그대로다.\n\n## 절차\n\n1. 사용자에게 무엇을 쓸지 듣는다. 자료가 있으면 먼저 읽는다\n2. 아래 마커로 **본문만** 텍스트로 쓴다. 서식 설명·코드블록을 넣지 않는다\n3. `python build_form.py 원고.md --check-only`로 검사한다\n4. 경고를 고친 뒤 `python build_form.py 원고.md -o 결과.hwpx`\n5. 사용자에게 파일을 주고 **한글에서 한 번 열어 보라고** 말한다\n\n## 서식이 안 갖춰진 한글 파일을 받았을 때\n\n사용자가 내용만 든 `.hwpx`를 주면 처음부터 다시 쓰지 말고 되돌려 쓴다.\n\n```bash\npython read_hwpx.py 받은문서.hwpx -o 원고.md --report 추정근거.md\n```\n\n`추정근거.md`를 **읽고** 단계 대응이 맞는지 본다. 틀렸으면 `원고.md`의 마커를\n고친다. 그림은 읽지 못하고 `[그림 자리]`로 남으니, 조직도·절차도라면 그림을 직접\n보고 표로 옮겨 적은 뒤 사용자에게 맞는지 물어본다. 그런 뒤 3번으로 간다.\n\n## 마커\n\n{{markers}}\n\n**기호를 두 번 쓰지 않는다.** 위 표에서 '한글이 자동으로'라고 적힌 레벨은 마커만\n쓰고 본문에 기호를 또 적으면 안 된다. 이중으로 찍힌다.\n\n표의 담당이 실제 양식과 다르면 `--bullets hangul`(한글에 맡김) 또는\n`--bullets text`(도구가 적음)로 바꾼다. 레벨마다 따로 정하려면 `form.json`의\n`levels[].write_marker`를 고친다.\n\n## 공통 문법\n\n```\n(빈 줄)            문단 사이 간격\n| 구분 | 값 |      표. 첫 행이 머리행\n[표: 제목]         바로 다음 표의 제목(양식에 표 번호가 있으면 <표 Ⅱ-1>처럼)\n{cols=30,35,35}    바로 다음 표의 열 너비 백분율\n셀 안 <br>         셀 안에서 줄 나눔\n※ 자료：…          표 주. 표 바로 아래에 둔다(양식에 표 주 스타일이 있을 때)\n[장: 제목]         장 표지의 제목. 문서에 하나\n앞말[^1]           각주 번호 자리\n[^1]: 내용         각주 내용\n```\n\n표 **앞**에는 빈 줄을 둔다. 표 **뒤**는 표 주가 오면 붙여 쓰고, 아니면 빈 줄을 둔다.\n장 번호는 `--chapter 3`으로 정한다(Ⅲ) — 표지 로마자와 표 번호가 함께 바뀐다.\n\n## 각주 번호를 놓는 자리\n\n- 근거가 되는 **말 바로 뒤**에 빈칸 없이 붙인다\n- 문장 전체의 근거이면 **마침표 앞**(`…이어졌다[^1].`) — 국내 학술·정부 보고서 관행\n- 인용문 **자체**가 각주 대상이면 닫는 **따옴표 안**(`\"…이다[^2]\"라고`),\n  인용을 쓴 문장 쪽의 근거이면 따옴표 밖\n- 제목·표 안에는 달지 않는다\n- 번호는 한글이 문서 순서대로 매긴다. `[^1]`의 숫자는 이름표일 뿐이다\n\n## 지켜야 할 것\n\n- **출처를 지어내지 않는다.** 확인한 자료만 적고, 확인하지 못했으면 `[확인 필요]`로\n  남겨 사용자에게 묻는다\n- 한 항목은 한 줄. 단문은 온점을 생략하고 두 문장 이상이면 온점을 찍는다\n- 검사에서 나온 경고를 그냥 지나치지 않는다. 고치거나, 왜 두는지 사용자에게 말한다\n- 만든 문서의 최종 모양은 **한글에서 열어야** 확인된다. 그 사실을 숨기지 않는다\n",
  "AGENTS.md": "# {{name}} 한글 문서 만들기 (codex·GPT용)\n\n이 폴더에는 `{{name}}` 양식으로 한글 문서(.hwpx)를 만드는 도구가 들어 있다.\n\n## 실행\n\n```bash\npython build_form.py 원고.md -o 결과.hwpx\n```\n\n파이썬 3.9 이상, 표준 라이브러리만 쓴다. 설치할 것이 없다.\n\n## 네가 할 일\n\n0. 사용자가 **내용만 든 hwpx**를 줬으면 먼저 되돌린다:\n   `python read_hwpx.py 받은문서.hwpx -o 원고.md --report 추정근거.md`\n   추정근거를 읽고 단계 대응이 맞는지 확인한 뒤 2번으로 간다\n1. 사용자의 요구대로 **본문만** `원고.md`에 마커 텍스트로 쓴다\n2. `python build_form.py 원고.md --check-only`로 검사하고 경고를 고친다\n3. 문서를 만들고 파일을 사용자에게 준다\n4. 한글에서 열어 확인해야 한다고 알린다\n\n## 마커\n\n{{markers}}\n\n'한글이 자동으로'라고 적힌 레벨은 마커만 쓴다. 본문에 기호를 또 적으면 이중이 된다.\n표의 담당이 실제 양식과 다르면 `--bullets hangul` 또는 `--bullets text`로 바꾼다.\n\n## 공통 문법\n\n```\n(빈 줄)            문단 사이 간격\n| 구분 | 값 |      표. 첫 행이 머리행\n[표: 제목]         표 제목(양식에 표 번호가 있으면 <표 Ⅱ-1>처럼)\n{cols=30,35,35}    열 너비 백분율\n셀 안 <br>         셀 안 줄 나눔\n※ 자료：…          표 주. 표 바로 아래\n[장: 제목]         장 표지의 제목\n앞말[^1]           각주 번호 자리\n[^1]: 내용         각주 내용\n```\n\n장 번호는 `--chapter N`으로 정한다. `해부보고서.md`의 *그 밖의 자리*에 이 양식이\n표 주·장 표지·표 번호를 쓰는지 적혀 있다. 없는 자리를 쓰면 검사가 알려 준다.\n\n## 금지\n\n- 출처를 지어내지 말 것. 확인하지 못한 것은 `[확인 필요]`로 남길 것\n- `form.json`의 스타일 번호를 임의로 바꾸지 말 것. 양식에 없는 번호를 쓰면 빌더가\n  2층 검사에서 멈춘다\n- `template.hwpx`를 고치지 말 것\n"
};


if (typeof window !== 'undefined') {
  window.HWPX_TEMPLATE_B64 = HWPX_TEMPLATE_B64;
  window.HWPX_PROFILES = HWPX_PROFILES;
  window.FORM_SCRIPTS = FORM_SCRIPTS;
  window.FORM_TEMPLATES = FORM_TEMPLATES;
}
