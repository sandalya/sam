#!/bin/bash
WORKSPACE="/home/sashok/.openclaw/workspace"
PROJECTS=("abby" "household_agent" "insilver-v3" "kit")

if [ -n "$1" ]; then
    PROJECT="$1"
else
    echo "Проект:"
    select p in "${PROJECTS[@]}"; do PROJECT="$p"; break; done
fi

PROJECT_DIR="$WORKSPACE/$PROJECT"

if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Проект '$PROJECT' не знайдено"; exit 1
fi

if [ -n "$2" ]; then
    DESCRIPTION="$2"
else
    echo "Що зробили (одне речення):"
    read -r DESCRIPTION
fi

if [ -n "$3" ]; then
    NEXT_STEP="$3"
else
    echo "Наступний крок:"
    read -r NEXT_STEP
fi

if [ "$#" -ge 4 ]; then
    EXTRA="$4"
else
    echo "Важливий контекст (Enter щоб пропустити):"
    read -r EXTRA
fi

DATE=$(date '+%Y-%m-%d %H:%M')
SESSION_FILE="$PROJECT_DIR/SESSION.md"

cat > "$SESSION_FILE" << SESSION
# SESSION — $DATE

## Проект
$PROJECT

## Що зробили
$DESCRIPTION

## Наступний крок
$NEXT_STEP
SESSION

if [ -n "$EXTRA" ] && [ "$EXTRA" != "немає" ]; then
    echo "" >> "$SESSION_FILE"
    echo "## Контекст" >> "$SESSION_FILE"
    echo "$EXTRA" >> "$SESSION_FILE"
fi

echo "✅ SESSION.md → $SESSION_FILE"

cd "$PROJECT_DIR" || exit 1
git add "$SESSION_FILE" "$PROJECT_DIR/" 2>/dev/null
COMMIT_MSG="chkp: $PROJECT — $DESCRIPTION"
git commit --no-verify -m "$COMMIT_MSG" 2>/dev/null && git push 2>/dev/null && echo "✅ Git: $COMMIT_MSG" || echo "⚠️  Git: нічого або push не вдався"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 ПРОМПТ ДЛЯ НАСТУПНОЇ СЕСІЇ:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Працюємо з $PROJECT на Pi5."
cat "$SESSION_FILE"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
