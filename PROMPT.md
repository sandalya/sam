Проект: sam

Стан: Архітектурна міграція workspace завершена. chkp3 переведена на yaml-registry (kit/projects.yaml), шляхи оновлено на 6 проектах. Миграція alias — замість hardcode шляхів тепер викликаємо `chkp3 sam` / `chkp3 meggy` тощо.

Наступне: (1) оновити HOT всіх 5 інших проектів (Meggy, Ed, Garcia, Abby-v2, Insilver-v3), (2) створити README для meta-структури workspace (як користуватися chkp3, де жити non-project файлам), (3) очистити kit/ від legacy-файлів. Архітектурне питання відкритим залишається: де жити workspace-адміністративним файлам (окремий репо чи монолітна структура)?

Блокери: Abby-v2 image-gen баг (кнопка Image 4), Sam NBLM rate limit (моніторити).

Перш ніж почнемо — скинь HOT.md + WARM.md з workspace/sam/ для синхронізації контексту.