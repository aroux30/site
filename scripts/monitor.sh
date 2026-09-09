#!/bin/bash
# Manager Monitoring Loop - Every 5 minutes
# Checks both sessions and project state

SITE_DIR="/c/Users/Administrator/Desktop/site"
LOG_FILE="$SITE_DIR/docs/monitor_log.txt"

while true; do
    echo "========================================" >> "$LOG_FILE"
    echo "🔍 Monitor Check: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
    echo "========================================" >> "$LOG_FILE"

    # 1. Total file count
    TOTAL_FILES=$(find "$SITE_DIR" -type f 2>/dev/null | wc -l)
    echo "📁 Total files: $TOTAL_FILES" >> "$LOG_FILE"

    # 2. Git status
    if [ -d "$SITE_DIR/.git" ]; then
        echo "✅ Git: Initialized" >> "$LOG_FILE"
    else
        echo "❌ Git: NOT initialized" >> "$LOG_FILE"
    fi

    # 3. node_modules
    if [ -d "$SITE_DIR/frontend/node_modules" ]; then
        echo "✅ npm: Dependencies installed" >> "$LOG_FILE"
    else
        echo "❌ npm: NOT installed" >> "$LOG_FILE"
    fi

    # 4. Non-empty API route files
    API_FILES=$(find "$SITE_DIR/backend/app/modules" -path "*/api/*.py" ! -empty ! -name "__init__.py" 2>/dev/null | wc -l)
    echo "📡 API route files (non-empty): $API_FILES" >> "$LOG_FILE"

    # 5. Non-empty service files
    SVC_FILES=$(find "$SITE_DIR/backend/app/modules" -path "*/application/*.py" ! -empty ! -name "__init__.py" 2>/dev/null | wc -l)
    echo "⚙️  Service files (non-empty): $SVC_FILES" >> "$LOG_FILE"

    # 6. Non-empty schema files
    SCHEMA_FILES=$(find "$SITE_DIR/backend/app/modules" -path "*/schemas/*.py" ! -empty ! -name "__init__.py" 2>/dev/null | wc -l)
    echo "📋 Schema files (non-empty): $SCHEMA_FILES" >> "$LOG_FILE"

    # 7. Non-empty infrastructure files
    INFRA_FILES=$(find "$SITE_DIR/backend/app/modules" -path "*/infrastructure/*.py" ! -empty ! -name "__init__.py" 2>/dev/null | wc -l)
    echo "🏗️  Infrastructure files (non-empty): $INFRA_FILES" >> "$LOG_FILE"

    # 8. Alembic migrations
    MIGRATION_FILES=$(find "$SITE_DIR/backend/alembic/versions" -name "*.py" 2>/dev/null | wc -l)
    echo "🔄 Alembic migrations: $MIGRATION_FILES" >> "$LOG_FILE"

    # 9. Test files
    TEST_FILES=$(find "$SITE_DIR" -name "test_*.py" -o -name "*.test.ts" -o -name "*.test.tsx" -o -name "*.spec.ts" 2>/dev/null | wc -l)
    echo "🧪 Test files: $TEST_FILES" >> "$LOG_FILE"

    # 10. Frontend components
    UI_COMPONENTS=$(find "$SITE_DIR/frontend/components/ui" -name "*.tsx" 2>/dev/null | wc -l)
    LAYOUT_COMPONENTS=$(find "$SITE_DIR/frontend/components/layout" -name "*.tsx" 2>/dev/null | wc -l)
    PAGES=$(find "$SITE_DIR/frontend/app" -name "page.tsx" 2>/dev/null | wc -l)
    echo "🎨 UI components: $UI_COMPONENTS | Layout: $LAYOUT_COMPONENTS | Pages: $PAGES" >> "$LOG_FILE"

    # 11. Domain models
    MODEL_FILES=$(find "$SITE_DIR/backend/app/modules" -path "*/domain/models.py" ! -empty 2>/dev/null | wc -l)
    echo "📦 Domain models (non-empty): $MODEL_FILES" >> "$LOG_FILE"

    # 12. Backend Python files (non-empty, non-init)
    PY_REAL=$(find "$SITE_DIR/backend" -name "*.py" ! -empty ! -name "__init__.py" 2>/dev/null | wc -l)
    echo "🐍 Real Python files: $PY_REAL" >> "$LOG_FILE"

    # 13. Recently modified files (last 5 minutes)
    RECENT=$(find "$SITE_DIR" -type f -mmin -5 2>/dev/null | wc -l)
    echo "🕐 Files modified in last 5 min: $RECENT" >> "$LOG_FILE"
    if [ "$RECENT" -gt 0 ]; then
        echo "   Recent files:" >> "$LOG_FILE"
        find "$SITE_DIR" -type f -mmin -5 2>/dev/null | head -20 >> "$LOG_FILE"
    fi

    # Summary
    echo "" >> "$LOG_FILE"
    echo "📊 SUMMARY:" >> "$LOG_FILE"
    echo "   Phase 0 completion: Git=$([ -d "$SITE_DIR/.git" ] && echo 'YES' || echo 'NO') | Dockerfiles=$([ -f "$SITE_DIR/backend/Dockerfile" ] && echo 'YES' || echo 'NO')" >> "$LOG_FILE"
    echo "   Phase 1 progress: APIs=$API_FILES | Services=$SVC_FILES | Schemas=$SCHEMA_FILES | Migrations=$MIGRATION_FILES" >> "$LOG_FILE"
    echo "   Frontend progress: Components=$UI_COMPONENTS | Pages=$PAGES | npm=$([ -d "$SITE_DIR/frontend/node_modules" ] && echo 'YES' || echo 'NO')" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"

    # Sleep 5 minutes
    sleep 300
done
