# Testing

## Framework

- Backend: `pytest`, `httpx`, `pytest-asyncio`
- Root smoke: `tests/smoke` — наличие обязательных артефактов Phase 0
- Domain calc tests — обязательны с появлением calculations (Phase 2+)

## Команды

```bash
# backend unit + API
cd backend
pytest -q

# repository smoke
cd ..
python -m pytest tests -q
```

## Политика

1. Все расчёты покрыты unit-тестами.
2. Critical validation regressions — отдельные тесты.
3. Golden study (Bosutinib 400 mg / Bosulif / 2×2 / FED) — protocol assembly Phase 8; DOCX Phase 9.
4. AI on/off не ломает generation path; unit tests используют `MockAIProvider` (без реального LLM).
5. Protocol build блокируется CRITICAL/ERROR validation; не выдумывает `ХХ`/`XXX`.
6. DOCX FINAL блокируется без sponsor / protocol_number / critical unresolved; template checksum проверяется.
7. Phase 10: E2E golden Bosutinib — `tests/test_phase10_e2e_golden.py`; artifacts in `golden/` (versioned folders, no overwrite).
