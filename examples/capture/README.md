# 도식 가져오기 예시

`hwpx-studio capture`로 읽어 볼 수 있는 원본들이다.

```bash
hwpx-studio capture examples/capture/org.mmd --title "위원회 구성"
hwpx-studio capture examples/capture/org.svg --hwpx 조직도.hwpx
hwpx-studio capture examples/capture/process.mmd
```

| 파일 | 형식 | 담긴 것 |
|---|---|---|
| `org.mmd` | Mermaid | 3단 조직도, `style`·`classDef` 색, 점선 연결선(`-.->`) |
| `process.mmd` | Mermaid | 가로 절차도(`graph LR`) → `type=flow`로 나온다 |
| `org.svg` | SVG | 상자·글자·연결선, 채움색·테두리색·점선(`stroke-dasharray`) |

읽은 결과는 그냥 텍스트다. 틀린 줄이 있으면 고쳐서 `hwpx-studio build`에 넣으면 된다.
