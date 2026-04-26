Проект: sam
Стан: Phase 6.1 Flashcards завершено (18/18 тем, Ed тести 3/3 PASS). Перший живий тест Ed MessageEdited listener пройшов успішно — edit_message_text тепер працює в FSM-ботах. Наступний крок — Phase 6.2 SR або діагностика NBLM/chkp3 бага.

Баги: (1) chkp3 Haiku max_tokens overflow при WARM>13k, Sonnet fallback timeout 120s; (2) NBLM RPC ADD_SOURCE failed блокує slides/podcast_nblm; (3) 6 тем у `generating` після failed NBLM.

Перш ніж почти — поділись HOT.md + WARM.md із сесії 24.04, щоб я знав точний стан. Чи є нові розробки у Рэген/NBLM/инших фронтів?