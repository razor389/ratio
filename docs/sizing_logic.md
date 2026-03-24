# Beta Sizing Logic Reference (LLM Agent)

This document defines the portfolio sizing methodology to be applied by an LLM when generating first-pass assessments. It specifies the factor framework, scoring system, beta derivation, and position sizing logic.

---

## 1. Objective

Estimate a **custom beta-like risk measure** for a company based on four qualitative factors, then determine a **suggested position size** by scaling a base position inversely to that beta.

* Lower risk → lower beta → larger position
* Higher risk → higher beta → smaller position

---

## 2. Factor Framework

Each company is evaluated across four factors:

1. **Debt**
2. **Change in Market Share**
3. **Change in Definition of Market**
4. **Relative Valuation**

---

## 3. Scoring Rules

* Each factor is scored from **0 to 10**
* Higher score = higher risk / higher beta contribution
* Lower score = lower risk / lower beta contribution

### Total score

[
\text{total_score} = d + ms + md + rv
]

* Minimum = 0
* Maximum = 40

---

## 4. Benchmark Reference

The system is calibrated to a benchmark:

* **S&P 500 reference score = 20 / 40 = 0.5**
* **Benchmark beta = 1.0**

This defines the midpoint of the scoring system.

---

## 5. Beta Calculation

### Step 1: Normalize score

[
\text{normalized_score} = \frac{\text{total_score}}{40}
]

### Step 2: Compute custom beta

[
\text{custom_beta} = \frac{\text{normalized_score}}{0.5}
]

Simplified:

[
\text{custom_beta} = \frac{\text{total_score}}{20}
]

---

## 6. Position Sizing

### 6.1 Base position (configurable)

[
\text{base_position} = \text{global configuration}
]

Default:

[
\text{base_position} = 0.05 \quad (5%)
]

Assumption:

* Portfolio is **100% allocated to equities**
* No additional allocation scaling is applied

---

### 6.2 Final sizing formula

[
\text{suggested_position} = \frac{\text{base_position}}{\text{custom_beta}}
]

---

## 7. Interpretation

| Total Score | Custom Beta | Position Impact  |
| ----------- | ----------- | ---------------- |
| Low         | Low         | Larger position  |
| Medium      | ~1          | Base position    |
| High        | High        | Smaller position |

---

## 8. Factor Scoring Guidance

### Debt

* **Low (0–3):** strong balance sheet, low leverage
* **High (7–10):** high leverage, refinancing risk, constrained flexibility

### Change in Market Share

* **Low:** stable or improving share
* **High:** declining share, competitive pressure

### Change in Definition of Market

* **Low:** stable industry structure
* **High:** disruption, shifting value chain, structural change

### Relative Valuation

* **Low:** inexpensive, margin of safety
* **High:** expensive, high expectations

---

## 9. LLM Output Requirements

For each company, the LLM must return:

### Factor scores and reasoning

* Score (0–10) for each factor
* Concise rationale tied to provided evidence

### Calculations

* total_score
* normalized_score
* custom_beta
* suggested_position

### Assumptions

* Any missing or inferred information
* Areas of uncertainty

---

## 10. Standard Output Schema

```json
{
  "ticker": "XYZ",
  "factor_scores": {
    "debt": { "score": 3, "rationale": "..." },
    "market_share_change": { "score": 4, "rationale": "..." },
    "market_definition_change": { "score": 6, "rationale": "..." },
    "relative_valuation": { "score": 7, "rationale": "..." }
  },
  "calculations": {
    "total_score": 20,
    "normalized_score": 0.5,
    "custom_beta": 1.0,
    "base_position_size": 0.05,
    "suggested_position_size": 0.05
  },
  "confidence": "medium"
}
```

---

## 11. Constraints

The LLM must:

* Use exactly four factors
* Keep scores within 0–10
* Use benchmark score = 0.5
* Use default base position = 5% unless explicitly overridden
* Apply inverse beta sizing exactly as defined
* Treat output as a **first-pass draft**, not a final decision

---

## 12. Edge Case Handling (System-Level)

These are implementation rules (not LLM responsibilities but relevant context):

* Apply a **beta floor** to prevent extreme sizing
* Optionally apply a **maximum position cap**
* Maintain full precision internally; round only for display

---

## 13. Summary

The method converts a qualitative four-factor assessment into a quantitative sizing decision:

1. Score each factor (0–10)
2. Sum to a total out of 40
3. Normalize relative to benchmark (20/40)
4. Convert to custom beta
5. Scale position size inversely using a configurable base (default 5%)

This creates a consistent, explainable bridge between qualitative analysis and portfolio sizing.
