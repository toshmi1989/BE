# Expert Rule Status — Phase 12A.1

Only rules that are **implemented** in seed/code. All listed statuses are PROPOSED pending verified regulatory/expert confirmation.

| RULE ID | DOMAIN | RULE | SOURCE | STATUS | AUTOMATION | EXPERT REQUIRED |
|---------|--------|------|--------|--------|------------|-----------------|
| INPUT-01 | INPUT | Design is a required study input | Interview / infrastructure | PROPOSED | Gap if missing | YES |
| REF-01 | REFERENCE_SELECTION | Reference product justified per Decision 85 §18 | Decision 85 p.18 (hint) | PROPOSED | Decision flow only | YES |
| DESIGN-01 | DESIGN | CV/CI present, not high → propose 2×2 | Interview | PROPOSED | Propose | YES |
| DESIGN-02 | DESIGN | High variability indicated → propose 2×2×4 | Interview | PROPOSED | Propose | YES |
| DESIGN-03 | DESIGN | Expanded BE limits need separate decision | Interview | PROPOSED | Gap only | YES |
| DESIGN-04 | DESIGN | Missing CV/CI → propose adaptive | Interview | PROPOSED | Propose | YES |
| DESIGN-05 | DESIGN | Long HL may suggest parallel; no numeric threshold | Interview | PROPOSED | Gap + note | YES |
| DESIGN-06 | DESIGN | Final design via ExpertDecision | Architecture | PROPOSED | Gate | YES |
| FOOD-01 | FOOD | Food determination per Decision 85 p.44 | Decision 85 p.44 (hint) | PROPOSED | Propose layer | YES |
| FOOD-02 | FOOD | Fed meal concept per Decision 85 p.46 | Decision 85 p.46 (hint) | PROPOSED | No kcal auto-fill | YES |
| FOOD-03 | FOOD | Alternate food via FDA + evidence + expert | Interview | PROPOSED | Gap/decision | YES |
| SAMPLE-01 | SAMPLE_SIZE | CVintra is a primary sample-size input | Interview | PROPOSED | Provenance layer | YES |
| SAMPLE-02 | SAMPLE_SIZE | CV from literature evidence | Interview | PROPOSED | Provenance | YES |
| SAMPLE-03 | SAMPLE_SIZE | Writer may pool available CVs | Interview | PROPOSED | Note only | YES |
| SAMPLE-04 | SAMPLE_SIZE | Standard 2×2: power 80%, α 0.05 | Interview | PROPOSED | Defaults (proposed) | YES |
| SAMPLE-05 | SAMPLE_SIZE | Adaptive may use Potvin B/C | Interview | PROPOSED | Gap — no numerics | YES |
| WASH-01 | WASHOUT | washout ≥ 5 × half-life | Interview | PROPOSED | Propose minimum | YES |
| SAMPLING-01 | SAMPLING | ≥3 points before Tmax | Interview | PROPOSED | Evaluate | YES |
| SAMPLING-02 | SAMPLING | ≥3 points after Tmax | Interview | PROPOSED | Evaluate | YES |
| SAMPLING-03 | SAMPLING | Cmax not first / post-dose series | Interview | PROPOSED | Evaluate | YES |
| SAMPLING-04 | SAMPLING | Adequate terminal-phase coverage | Interview | PROPOSED | Evaluate | YES |
| SAMPLING-05 | SAMPLING | ≥3–4 terminal samples | Interview | PROPOSED | Evaluate | YES |
| SAMPLING-06 | SAMPLING | Last point ≥ 4 × half-life | Interview | PROPOSED | Evaluate | YES |
| SAMPLING-07 | SAMPLING | AUC0-t ≥ 80% AUC0-inf | Interview | PROPOSED | Evaluate | YES |
| SAMPLING-08 | SAMPLING | Long HL truncation to 72h (conditional) | Interview | PROPOSED | Gap | YES |
| SAMPLING-HEUR-01 | SAMPLING | Tmax density heuristic (not regulatory PASS) | Legacy / interview | PROPOSED | Heuristic only | YES |
| ANALYTE-01 | ANALYTE | Parent/metabolite per Rules §III.6 p.50 | Rules hint | PROPOSED | Propose | YES |
| CRIT-01 | ELIGIBILITY | Most criteria are standard | Interview | PROPOSED | Note | YES |
| CRIT-02 | ELIGIBILITY | Concomitant meds may depend on SmPC | Interview | PROPOSED | Overlay | YES |
| CRIT-03 | ELIGIBILITY | CYP restrictions need SmPC evidence | Interview | PROPOSED | Overlay | YES |
| CRIT-04 | ELIGIBILITY | SmPC contraindications may alter criteria | Interview | PROPOSED | Overlay | YES |
| CRIT-05 | ELIGIBILITY | Vomiting window = 2 × Tmax | Interview | PROPOSED | Propose only | YES |
| CRIT-06 | ELIGIBILITY | Smoking may depend on metabolic enzymes | Interview | PROPOSED | Overlay | YES |
| CRIT-07 | ELIGIBILITY | Contraception period from SmPC | Interview | PROPOSED | Gap if missing | YES |
| SAFETY-01 | SAFETY | Standard BE safety set (conceptual) | Interview | PROPOSED | Schema/gap only | YES |
| SOURCE-01 | SOURCE | Source class ordering conceptual only | Interview | PROPOSED | Gap for ranking | YES |

## Foundation KnowledgeGaps (seeded)

| Gap | Domain | Importance | Blocking |
|-----|--------|------------|----------|
| Potvin B/C sample-size specification not verified | SAMPLE_SIZE | HIGH | No |
| Final randomized N decision logic not specified | SAMPLE_SIZE | CRITICAL | Yes |
| Verified numeric long half-life definition missing | DESIGN | HIGH | No |
| Expanded BE limits require expert decision | DESIGN | HIGH | Yes |
| Specific PK exceptions not fully specified | PK | MEDIUM | No |
| Reference safety protocol after June 2026 not formalized | SAFETY | MEDIUM | No |
| Formal source conflict resolution needs confirmation | SOURCE | HIGH | No |
| Long HL truncation-to-72h criteria not verified | SAMPLING | MEDIUM | No |
