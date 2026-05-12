#!/bin/bash
set -e
cd /root/advertwise/backend
source venv/bin/activate

# Load env into current shell
eval $(python3 -c "
from pathlib import Path
lines = Path('.env').read_text().splitlines()
for line in lines:
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    key, _, val = line.partition('=')
    val = val.strip().strip('\"').strip(\"'\")
    print(f'export {key.strip()}=\"{val}\"')
")
echo "DATABASE_URL loaded: $([ -n \"$DATABASE_URL\" ] && echo YES || echo NO)"

# Kill existing processes
pkill -f "uvicorn app.main" 2>/dev/null
pkill -f "arq app.arq_worker" 2>/dev/null
sleep 3

# Export all env vars to a file for worker subshells
env | grep -E "DATABASE_URL|REDIS|R2_|GROQ|TOGETHER|GEMINI|SARVAM|ELEVENLABS|FAL|OPENAI|DEEPSEEK|MINIMAX|NOVITA|SILICONFLOW|POSTHOG" \
  > /tmp/advertwise_env.sh
sed -i 's/^/export /' /tmp/advertwise_env.sh

# Start API
nohup python3 -m uvicorn app.main:app \
  --host 0.0.0.0 --port 8000 \
  --workers 1 --log-level info \
  > /var/log/advertwise-api.log 2>&1 &
echo "API started PID $!"

# Start Worker A with env
nohup bash -c 'source /tmp/advertwise_env.sh && cd /root/advertwise/backend && source venv/bin/activate && python3 -m arq app.arq_worker_a.WorkerSettings' \
  > /var/log/advertwise-worker-a.log 2>&1 &
echo "Worker A started PID $!"

# Start Worker B with env
nohup bash -c 'source /tmp/advertwise_env.sh && cd /root/advertwise/backend && source venv/bin/activate && python3 -m arq app.arq_worker_b.WorkerSettings' \
  > /var/log/advertwise-worker-b.log 2>&1 &
echo "Worker B started PID $!"

sleep 8
echo "=== Running processes ==="
ps aux | grep -E "uvicorn|arq" | grep -v grep

echo "=== API check ==="
curl -s http://localhost:8000/openapi.json | python3 -c "
import json,sys
d=json.load(sys.stdin)
print('Routes:', len(d['paths']))
" 2>/dev/null || echo "API not responding — check /var/log/advertwise-api.log"
