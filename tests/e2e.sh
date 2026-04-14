#!/usr/bin/env bash
# circle-map.html E2E テスト (agent-browser)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCREENSHOTS_DIR="$SCRIPT_DIR/screenshots"
PORT=8765
BASE_URL="http://localhost:${PORT}/circle-map.html"

PASS=0
FAIL=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

REPORT_FILE="$SCRIPT_DIR/report.txt"

mkdir -p "$SCREENSHOTS_DIR"
printf "" > "$REPORT_FILE"

ab() { agent-browser "$@"; }

pass() { printf "  ${GREEN}✓${NC} %s\n" "$1"; PASS=$((PASS + 1)); printf "PASS: %s\n" "$1" >> "$REPORT_FILE"; }
fail() { printf "  ${RED}✗${NC} %s\n" "$1"; FAIL=$((FAIL + 1)); printf "FAIL: %s\n" "$1" >> "$REPORT_FILE"; }

assert_eval_eq() {
  local label="$1" expected="$2" js="$3"
  local actual
  actual=$(ab eval "$js" 2>&1)
  if [[ "$actual" == "$expected" ]]; then
    pass "$label"
  else
    fail "$label (期待値: '$expected', 実際: '$actual')"
  fi
}

assert_eval_gt() {
  local label="$1" threshold="$2" js="$3"
  local actual
  actual=$(ab eval "$js" 2>&1)
  if [[ "$actual" -gt "$threshold" ]] 2>/dev/null; then
    pass "$label (${actual} > ${threshold})"
  else
    fail "$label (期待値: > ${threshold}, 実際: '${actual}')"
  fi
}

assert_visible() {
  local label="$1" sel="$2"
  local result
  result=$(ab is visible "$sel" 2>&1)
  if [[ "$result" == "true" ]]; then
    pass "$label"
  else
    fail "$label (selector: $sel)"
  fi
}

assert_checked() {
  local label="$1" sel="$2" expected="$3"
  local result
  result=$(ab is checked "$sel" 2>&1)
  if [[ "$result" == "$expected" ]]; then
    pass "$label"
  else
    fail "$label (期待値: $expected, 実際: $result)"
  fi
}

# ---- サーバー起動 ----
cd "$PROJECT_DIR"
python3 -m http.server $PORT --bind 127.0.0.1 &>/tmp/circle_map_test_server.log &
SERVER_PID=$!
trap "kill $SERVER_PID 2>/dev/null; printf '\n${YELLOW}サーバーを停止しました${NC}\n'" EXIT
sleep 2

echo ""
printf "${BOLD}=== circle-map.html E2E テスト ===${NC}\n"
echo ""

# -------- [1] ページ読み込み --------
printf "${BOLD}[1] ページ読み込み${NC}\n"
ab open "$BASE_URL" &>/dev/null
ab wait 2000 &>/dev/null

title=$(ab get title 2>&1)
if [[ "$title" == "円描画マップ" ]]; then
  pass "タイトルが正しい"
else
  fail "タイトルが正しい (実際: '$title')"
fi
assert_visible "マップ (#map) が表示されている" "#map"
ab screenshot "$SCREENSHOTS_DIR/01_page_load.png" &>/dev/null

# -------- [2] 精霊データロード --------
echo ""
printf "${BOLD}[2] 精霊データロード${NC}\n"
assert_eval_gt "spirits.csv が読み込まれる" 0 "allSpiritData.length"
assert_eval_gt "精霊マーカーがプロットされる" 0 "spiritMarkers.length"
ab screenshot "$SCREENSHOTS_DIR/02_spirits.png" &>/dev/null

# -------- [3] 日付フィルタ --------
echo ""
printf "${BOLD}[3] 日付フィルタ${NC}\n"
assert_eval_gt "日付の選択肢が存在する" 1 "document.getElementById('dateFilter').options.length"

ab select "#dateFilter" "2026/04/13" &>/dev/null
ab wait 500 &>/dev/null
count_apr13=$(ab eval "spiritMarkers.length" 2>&1)

ab select "#dateFilter" "2026/04/12" &>/dev/null
ab wait 500 &>/dev/null
count_apr12=$(ab eval "spiritMarkers.length" 2>&1)

ab select "#dateFilter" "all" &>/dev/null
ab wait 500 &>/dev/null
count_all=$(ab eval "spiritMarkers.length" 2>&1)

if [[ "$count_all" -gt "$count_apr13" ]] 2>/dev/null; then
  pass "日付フィルタで件数が絞り込まれる (all:${count_all} > 2026/04/13:${count_apr13})"
else
  fail "日付フィルタが機能していない (all:${count_all}, 2026/04/13:${count_apr13})"
fi
if [[ "$count_apr13" -gt 0 && "$count_apr12" -gt 0 ]] 2>/dev/null; then
  pass "各日付で精霊が存在する (2026/04/13:${count_apr13}件, 2026/04/12:${count_apr12}件)"
else
  fail "日付別データが存在しない (2026/04/13:${count_apr13}, 2026/04/12:${count_apr12})"
fi

# -------- [4] 精霊クリックで円描画 --------
echo ""
printf "${BOLD}[4] 精霊クリックで円描画${NC}\n"
assert_eval_eq "クリック前は円がない" "0" "circles.length"

ab eval "spiritMarkers[0].fire('click')" &>/dev/null
ab wait 500 &>/dev/null
assert_eval_eq "クリックで 750m + 3km の円が2本描画される" "2" "circles.length"
ab screenshot "$SCREENSHOTS_DIR/03_circles.png" &>/dev/null

# -------- [5] クリアボタン --------
echo ""
printf "${BOLD}[5] クリアボタン${NC}\n"
ab click ".btn-clear" &>/dev/null
ab wait 300 &>/dev/null
assert_eval_eq "クリア後に円が消える" "0" "circles.length"

# -------- [6] GeoHex トグル --------
echo ""
printf "${BOLD}[6] GeoHex トグル${NC}\n"

# ビューポートがセルで覆われているかチェックするJS
COVERS_VIEWPORT="(function(){
  var lv = arguments[0];
  var layers = hexLayers[lv].getLayers();
  if (layers.length === 0) return 'no layers';
  var mb = map.getBounds();
  var hb = L.latLngBounds();
  layers.forEach(function(l){ hb.extend(l.getBounds()); });
  return (hb.getSouth() <= mb.getSouth() &&
          hb.getNorth() >= mb.getNorth() &&
          hb.getWest()  <= mb.getWest()  &&
          hb.getEast()  >= mb.getEast()) ? 'true' : 'false';
})()"

for LV in 3 4 5; do
  assert_checked "Lv${LV} は初期状態でオフ" "#hex${LV}" "false"

  ab check "#hex${LV}" &>/dev/null
  ab wait 800 &>/dev/null
  assert_checked "Lv${LV} チェック後はオン" "#hex${LV}" "true"
  assert_eval_gt "Lv${LV} セルが描画される" 0 "hexLayers[${LV}].getLayers().length"

  JS="(function(){var layers=hexLayers[${LV}].getLayers();if(layers.length===0)return 0;var mb=map.getBounds();var hb=L.latLngBounds();layers.forEach(function(l){hb.extend(l.getBounds());});return(hb.getSouth()<=mb.getSouth()&&hb.getNorth()>=mb.getNorth()&&hb.getWest()<=mb.getWest()&&hb.getEast()>=mb.getEast())?1:0;})()"
  assert_eval_eq "Lv${LV} セルがビューポート全体をカバーする（境界欠け検知）" "1" "$JS"

  ab screenshot "$SCREENSHOTS_DIR/06_geohex_lv${LV}.png" &>/dev/null

  ab uncheck "#hex${LV}" &>/dev/null
  ab wait 300 &>/dev/null
  assert_eval_eq "Lv${LV} チェック解除でセルが消える" "0" "hexLayers[${LV}].getLayers().length"
done

# -------- [7] バス停トグル --------
echo ""
printf "${BOLD}[7] バス停トグル${NC}\n"
assert_checked "バス停は初期状態でオフ" "#busToggle" "false"

ab check "#busToggle" &>/dev/null
ab wait 2000 &>/dev/null
assert_eval_eq "バス停データが読み込まれる" "true" "busLoaded"
assert_eval_gt "バス停マーカーがプロットされる" 0 "busLayer.getLayers().length"
ab screenshot "$SCREENSHOTS_DIR/05_busstops.png" &>/dev/null

ab uncheck "#busToggle" &>/dev/null
ab wait 300 &>/dev/null
assert_checked "バス停チェック解除でオフになる" "#busToggle" "false"

# -------- 結果 --------
echo ""
echo "=================================="
TOTAL=$((PASS + FAIL))
if [[ "$FAIL" -eq 0 ]]; then
  printf "結果: ${GREEN}${BOLD}全 ${TOTAL} テスト合格${NC}\n"
  printf "\n結果: 全 %s テスト合格\n" "$TOTAL" >> "$REPORT_FILE"
else
  printf "結果: ${GREEN}${PASS} passed${NC} / ${RED}${FAIL} failed${NC} (計 ${TOTAL})\n"
  printf "\n結果: %s passed / %s failed (計 %s)\n" "$PASS" "$FAIL" "$TOTAL" >> "$REPORT_FILE"
fi
echo "スクリーンショット: $SCREENSHOTS_DIR/"
printf "レポート: %s\n" "$REPORT_FILE"
echo "=================================="
echo ""

[[ "$FAIL" -eq 0 ]]
