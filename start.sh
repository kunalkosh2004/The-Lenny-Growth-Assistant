#!/bin/bash
set -e

# Source the root .env file so all API keys are available
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
  set -a
  source "$SCRIPT_DIR/.env"
  set +a
fi

POSTGRES_PORT="${POSTGRES_PORT:-5432}"
export DATABASE_URL="postgresql+psycopg://lenny:lenny_dev_password@localhost:${POSTGRES_PORT}/lenny_growth_assistant"

echo "=== The Lenny Growth Assistant ==="
echo ""

# Check PostgreSQL
echo "Checking PostgreSQL on port ${POSTGRES_PORT}..."

if ! docker compose exec -T postgres pg_isready -U lenny -d lenny_growth_assistant > /dev/null 2>&1; then
  echo "❌ PostgreSQL is not running. Starting it..."
  docker compose up -d postgres

  echo "Waiting for PostgreSQL..."
  until docker compose exec -T postgres pg_isready -U lenny -d lenny_growth_assistant > /dev/null 2>&1; do
    sleep 1
  done
fi

echo "✅ PostgreSQL is running"

# Check Ollama
echo "Checking Ollama..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
  echo "✅ Ollama is running"
  MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; print(', '.join(m['name'] for m in json.load(sys.stdin).get('models',[])))" 2>/dev/null || echo "unknown")
  echo "   Models: $MODELS"
else
  echo "⚠️  Ollama is not running. Start it with: ollama serve"
fi

# Show configured cloud providers
echo ""
echo "Configured cloud providers:"
[ -n "$OPENAI_API_KEY" ] && echo "  ✅ OpenAI" || echo "  ⬜ OpenAI (set OPENAI_API_KEY)"
[ -n "$ANTHROPIC_API_KEY" ] && echo "  ✅ Anthropic" || echo "  ⬜ Anthropic (set ANTHROPIC_API_KEY)"
[ -n "$GOOGLE_API_KEY" ] && echo "  ✅ Google Gemini" || echo "  ⬜ Google Gemini (set GOOGLE_API_KEY)"

echo ""
echo "Starting backend on http://localhost:8001 ..."
cd "$SCRIPT_DIR/backend"
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload --reload-exclude ".venv/*"
