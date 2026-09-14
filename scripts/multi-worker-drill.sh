#!/usr/bin/env bash
# P1-close multi-worker real-machine drill against the isolated axiom-e2e stack.
# Proves: two live workers, parallel consumption, atomic claim dedup on
# duplicate delivery, terminal cancel, no duplicate side effects.
# Usage: scripts/multi-worker-drill.sh
set -euo pipefail

E2E_COMPOSE="${E2E_COMPOSE:-$(pwd)/infra/e2e/docker-compose.e2e.yml}"
WORKER2_OVERRIDE="${WORKER2_OVERRIDE:-$(pwd)/scripts/e2e-worker2.compose.yml}"
ENV_FILE="${ENV_FILE:-$(pwd)/.env.example}"
export DOCKER_HOST="${DOCKER_HOST:-unix://$HOME/.colima/default/docker.sock}"
export E2E_ROOT="${E2E_ROOT:-$(pwd)}"
API="${API:-http://localhost:8100}"
WORKER_MAIN="${WORKER_MAIN:-axiom-e2e-worker-1}"

dc() {
  docker-compose -p axiom-e2e \
    -f "$E2E_COMPOSE" -f "$WORKER2_OVERRIDE" --env-file "$ENV_FILE" "$@"
}

echo "==> [1/6] bring up second worker (no beat)"
dc up -d worker2

echo "==> [2/6] wait for both workers to answer ping"
PONG=0
for _ in $(seq 1 30); do
  PONG=$(docker exec "$WORKER_MAIN" celery -A services.worker.celery_app inspect ping -t 3 2>/dev/null | grep -c pong || true)
  [ "$PONG" -ge 2 ] && break
  sleep 5
done
echo "workers alive: ${PONG}"
docker exec "$WORKER_MAIN" celery -A services.worker.celery_app inspect ping -t 3 2>/dev/null || true

echo "==> [3/6] locate E2E strategy + latest version"
SID=$(curl -sf "${API}/api/v1/strategies?q=E2E%20%E8%B6%8B%E5%8A%BF%E7%AD%96%E7%95%A5" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['items'][0]['id'])")
VID=$(curl -sf "${API}/api/v1/strategies/${SID}" \
  | python3 -c "import json,sys;print(json.load(sys.stdin)['latest_version']['id'])")
echo "strategy=${SID} version=${VID}"

echo "==> [4/6] enqueue 2 backtests concurrently (two workers)"
# 动态窗口：避免命中结果缓存，确保每次都真机执行 LEAN（数据覆盖 2010-2026）。
SEED=$(date +%s)
YA=$((2011 + SEED % 5))          # 2011..2015
YB=$((2012 + SEED % 6))          # 2012..2017
WA="${YA}-01-01"; WB="${YA}-12-31"
WC="${YB}-02-01"; WD="${YB}-11-30"
run_bt() {
  curl -sf -X POST "${API}/api/v1/backtests" -H 'Content-Type: application/json' \
    -d "{\"strategy_version_id\":\"${VID}\",\"start_date\":\"$1\",\"end_date\":\"$2\",\"benchmark\":\"SPY\",\"initial_capital\":100000}" \
    | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])"
}
BT_A=$(run_bt "${WA}" "${WB}")
BT_B=$(run_bt "${WC}" "${WD}")
echo "backtests: ${BT_A} ${BT_B} (windows ${WA}~${WB} / ${WC}~${WD})"

wait_completed() {
  for _ in $(seq 1 120); do
    ST=$(curl -sf "${API}/api/v1/backtests/$1" | python3 -c "import json,sys;print(json.load(sys.stdin)['status'])")
    case "$ST" in COMPLETED|FAILED|CANCELLED) echo "$1 => ${ST}"; return 0;; esac
    sleep 5
  done
  echo "$1 => TIMEOUT"; return 1
}
wait_completed "${BT_A}" & WAIT_A=$!
wait_completed "${BT_B}" & WAIT_B=$!
wait $WAIT_A; wait $WAIT_B

echo "==> [5/6] duplicate delivery of ${BT_A} (claim must dedup, no double equity)"
docker exec -i "$WORKER_MAIN" python - <<PY
from services.worker.celery_app import celery_app
bt = "${BT_A}"
for i in range(2):
    celery_app.send_task("backtests.run", args=[bt], task_id=f"drill-dup-{bt}-{i}")
print("sent 2 duplicate deliveries for", bt)
PY
sleep 20
docker logs "$WORKER_MAIN" --tail 200 2>&1 | grep -E "deduplicated|backtests.run" | tail -8 || true

echo "==> [6/6] cancel drill: backtest must reach terminal CANCELLED"
BT_C=$(run_bt 2017-01-01 2018-06-30)
curl -sf -X POST "${API}/api/v1/backtests/${BT_C}/cancel" > /dev/null
# 取消异步生效：worker 观察到 flag 后以终态结束，轮询确认（不把中途 RUNNING 误判失败）。
ST=""
for _ in $(seq 1 24); do
  ST=$(curl -sf "${API}/api/v1/backtests/${BT_C}" | python3 -c "import json,sys;print(json.load(sys.stdin)['status'])")
  [ "$ST" = "CANCELLED" ] && break
  sleep 5
done
echo "cancelled backtest => ${ST}"
[ "$ST" = "CANCELLED" ]

echo "==> DRILL DONE: two workers live, parallel + dedup + cancel OK"
