# SESSION — 2026-04-18 23:05

## Проект
sam-v2

## Що зробили
Phase 1 FULLY RUNNING: /cur2 works in @sam_dev_sasha_bot on Pi5. Real migration done, curriculum_v2.json rendered correctly in Telegram, all 16 topics across 7 islands visible to user. Production sam untouched and running.

## Наступний крок
NEXT SESSION: 1) Fix markdown rendering in /cur2 (fallback-to-plain kicked in — either use MARKDOWN_V2 with strict escaping, HTML, or just live with plain). 2) Start Phase 2: pinned editable panel with checkboxes per format, inline-keyboard expand/collapse per topic, 'start consuming'/'test' buttons. 3) Review aggressive visual-first classification from migration — flip some to audio when style-toggle button appears in Phase 2.

## Контекст
sam-v2 running in background via nohup, PID tracked in /tmp/sam_v2.log. When need to restart: ps aux | grep sam-v2, kill, relaunch same way. @sam_dev_sasha_bot uses separate token in sam-v2/.env. Main sam on production token unchanged. Branches: curriculum-v2 (sam-v2) and master (shared) pushed to GitHub. Files to review on start: sam-v2/modules/curriculum_v2.py, shared/curriculum/{models,storage,islands,migration}.py. Backups in data/_legacy_*_20260418_191912.json.
