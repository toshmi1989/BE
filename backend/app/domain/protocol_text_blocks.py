"""Versioned TextBlock catalog — templates live here, not in UI."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TextBlockDef:
    block_code: str
    section_code: str
    text_template: str
    variables: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ("always",)
    source_ids: tuple[str, ...] = ()
    version: str = "v1"
    status: str = "ACTIVE"


TEXT_BLOCKS: dict[str, TextBlockDef] = {
    "CROSSOVER_DESCRIPTION": TextBlockDef(
        "CROSSOVER_DESCRIPTION",
        "4.2",
        "Исследование проводится по дизайну открытого рандомизированного перекрёстного "
        "исследования 2×2 с {periods} периодами и последовательностями: {sequences_text}.",
        ("periods", "sequences_text"),
        ("design_crossover_2x2",),
    ),
    "REPLICATE_DESCRIPTION": TextBlockDef(
        "REPLICATE_DESCRIPTION",
        "4.2",
        "Исследование проводится по репликативному дизайну ({design_type}) "
        "с {periods} периодами и последовательностями: {sequences_text}.",
        ("design_type", "periods", "sequences_text"),
        ("design_replicate",),
    ),
    "PARALLEL_DESCRIPTION": TextBlockDef(
        "PARALLEL_DESCRIPTION",
        "4.2",
        "Исследование проводится по параллельному дизайну с группами лечения: {treatments_text}.",
        ("treatments_text",),
        ("design_parallel",),
    ),
    "ADAPTIVE_DESCRIPTION": TextBlockDef(
        "ADAPTIVE_DESCRIPTION",
        "4.2",
        "Исследование проводится по адаптивному дизайну. Этап 1 и interim-анализ заданы в Study Model.",
        (),
        ("design_adaptive",),
    ),
    "FED_MEAL_DESCRIPTION": TextBlockDef(
        "FED_MEAL_DESCRIPTION",
        "6.2.1",
        "Референтный и тестовый препараты вводятся {food_condition} "
        "({meal_type}).",
        ("food_condition", "meal_type"),
        ("food_fed",),
    ),
    "FASTING_DESCRIPTION": TextBlockDef(
        "FASTING_DESCRIPTION",
        "6.2.1",
        "Препараты вводятся {food_condition}.",
        ("food_condition",),
        ("food_fasting",),
    ),
    "FASTING_AND_FED_DESCRIPTION": TextBlockDef(
        "FASTING_AND_FED_DESCRIPTION",
        "6.2.1",
        "Исследование включает условия: {food_condition}.",
        ("food_condition",),
        ("food_both",),
    ),
    "SAMPLING_RATIONALE": TextBlockDef(
        "SAMPLING_RATIONALE",
        "4.4.2",
        "План отбора проб крови включает {n_points} точек на период. "
        "Финальная точка наблюдения: {observation_duration} {observation_unit}.",
        ("n_points", "observation_duration", "observation_unit"),
        ("always",),
    ),
    "SAMPLE_SIZE_RATIONALE": TextBlockDef(
        "SAMPLE_SIZE_RATIONALE",
        "9.2",
        "Расчётный размер выборки: оцениваемых субъектов N={evaluable_n}, "
        "рандомизированных N={randomized_n} (dropout {dropout_pct}%). "
        "Использованный CVintra={cv_percent}% для параметра {cv_parameter}.",
        ("evaluable_n", "randomized_n", "dropout_pct", "cv_percent", "cv_parameter"),
        ("always",),
    ),
    "STATISTICAL_METHOD": TextBlockDef(
        "STATISTICAL_METHOD",
        "9.1",
        "Основной анализ биоэквивалентности выполняется на логарифмически преобразованных "
        "PK-параметрах с использованием ANOVA для дизайна ({design_type}). "
        "Критерий BE: 90% ДИ отношения средних в пределах 80.00–125.00%.",
        ("design_type",),
        ("always",),
    ),
    "SAFETY_STANDARD_TEXT": TextBlockDef(
        "SAFETY_STANDARD_TEXT",
        "8.1",
        "Безопасность оценивается по данным физического осмотра, жизненных показателей, "
        "лабораторных исследований и регистрации нежелательных явлений на протяжении исследования.",
        (),
        ("always",),
    ),
    "MULTI_ANALYTE_NOTE": TextBlockDef(
        "MULTI_ANALYTE_NOTE",
        "7.1",
        "В исследовании оценивается более одного аналита ({analyte_count}): {analyte_names}.",
        ("analyte_count", "analyte_names"),
        ("analyte_count_gt_1",),
    ),
    "REFERENCE_NOT_PURCHASED": TextBlockDef(
        "REFERENCE_NOT_PURCHASED",
        "2.1.2",
        "Статус закупки референтного препарата: {purchased_status}. "
        "Детали партии/регистрации не финализируются как фактически закупленные.",
        ("purchased_status",),
        ("reference_not_purchased",),
    ),
    "WASHOUT_DESCRIPTION": TextBlockDef(
        "WASHOUT_DESCRIPTION",
        "2.12",
        "Период отмывки (washout): {washout_value} {washout_unit} "
        "(минимум по расчёту: {washout_minimum} {washout_unit}).",
        ("washout_value", "washout_unit", "washout_minimum"),
        ("crossover",),
    ),
    "SYNOPSIS_CORE": TextBlockDef(
        "SYNOPSIS_CORE",
        "SYNOPSIS",
        "Протокол {protocol_number}. Спонсор: {sponsor_name}. Дизайн: {design_type}. Условие пищи: {food_condition}. "
        "Оцениваемых субъектов: {evaluable_n}; рандомизированных: {randomized_n}. "
        "Тест: {test_name}. Референт: {ref_name}.",
        (
            "protocol_number",
            "sponsor_name",
            "design_type",
            "food_condition",
            "evaluable_n",
            "randomized_n",
            "test_name",
            "ref_name",
        ),
        ("always",),
    ),
}


def get_text_block(block_code: str) -> TextBlockDef | None:
    return TEXT_BLOCKS.get(block_code)


def list_text_blocks() -> list[dict]:
    return [
        {
            "block_code": b.block_code,
            "section_code": b.section_code,
            "text_template": b.text_template,
            "variables": list(b.variables),
            "conditions": list(b.conditions),
            "source_ids": list(b.source_ids),
            "version": b.version,
            "status": b.status,
        }
        for b in TEXT_BLOCKS.values()
    ]
