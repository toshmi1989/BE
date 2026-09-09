# DOCX Mapping

Исходный шаблон: `templates/protocol/BE_Protocol_Template_v2.0.docx`

Фактическая структура (из SPEC / inspection):

- ~1432 абзаца
- 33 таблицы
- 74 встроенных комментария
- TOC + тело с расхождениями (не копировать слепо ошибочную структуру)

## Принцип

Не find/replace строк. Mapping:

```text
Study fields → ProtocolSection / TextBlock / Table → DOCX bookmarks & numbered refs
```

Inventories (Phase 9):

- [DOCX_TEMPLATE_INVENTORY.md](DOCX_TEMPLATE_INVENTORY.md)
- [DOCX_TABLE_INVENTORY.md](DOCX_TABLE_INVENTORY.md)

TOC fields are left as Word fields; update TOC on open in Microsoft Word.

## Phase 0

Только хранение исходного шаблона. Assembly — Phase 8; DOCX engine — Phase 9 (implemented).
