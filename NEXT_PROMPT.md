Проект: workspace infrastructure — створення meta-репо.

Стан: У попередній сесії (23.04, commit e3257a6 у sam-репо) завершено міграцію всіх 6 ботів на триярусну пам'ять через chkp3. Тепер треба винести адмін-інфраструктуру (chkp3 + шаблони + projects.yaml + BACKLOG) з kit/ у окремий meta-репо.

Репо готовий: https://github.com/sandalya/workspace-meta

Детальний план і архітектурна філософія — у файлі:
cat /home/sashok/.openclaw/workspace/sam/NEXT_SESSION.md

Також для контексту:
cat /home/sashok/.openclaw/workspace/sam/HOT.md
cat /home/sashok/.openclaw/workspace/sam/WARM.md

Після читання цих трьох файлів — обговоримо чи архітектура ок, і почнемо по кроках з NEXT_SESSION.md.
