# Drive Log Column Analysis: Installation Criteria Research

**Date:** 2025-01-30
**Source File:** `Drive Log 1-10-2026.xls`
**Total Rows:** 61,904

## Summary

Analysis of the `Hammering_Status`, `Hammering_Flag`, and `Pile_Installed` columns to understand installation criteria and data patterns.

---

## Unique Values

### Hammering_Status (6 values + NaN)

| Value | Description |
|-------|-------------|
| `COMPLETED` | Standard completion |
| `SUCCESS` | Successful installation |
| `UNATTEMPTED` | Not yet attempted |
| `INCOMPLETE_NO_FINISH_TIME` | Started but no finish time recorded |
| `COMPLETED, Error to compute accurate hammering times` | Completed with timing errors |
| `COMPLETED, Might need Tap down` | Completed but may need adjustment |
| `NaN` | 42,868 rows (69.2%) |

### Hammering_Flag (9 values + NaN)

| Value | Description |
|-------|-------------|
| `GOOD` | No issues |
| `NONE` | No flag set |
| `UNSET` | Flag not configured |
| `INCLINED` | Pile is inclined |
| `REFUSED` | Pile refused (hit obstruction) |
| `OTHER` | Other issue |
| `TWISTED` | Pile twisted during driving |
| `DAMAGED` | Pile damaged |
| `OVERDRIVEN` | Pile driven too deep |
| `NaN` | 42,868 rows (69.2%) |

### Pile_Installed (3 values + NaN)

| Value | Count |
|-------|-------|
| `No` | Majority of NaN hammering rows |
| `Yes` | Successfully installed |
| `Refusal` | Installation refused |
| `NaN` | 4 rows |

---

## NaN Correlation

**Key Finding:** `Hammering_Status` and `Hammering_Flag` NaN values are perfectly correlated.
- When one is NaN, the other is always NaN
- 42,868 rows (69.2%) have both as NaN
- No rows exist where only one column has a value

---

## All Unique Combinations (48 total)

### High Frequency Combinations (>100 occurrences)

| Hammering_Status | Hammering_Flag | Pile_Installed | Count | % |
|------------------|----------------|----------------|-------|---|
| `<NaN>` | `<NaN>` | No | 36,621 | 59.2% |
| COMPLETED | GOOD | Yes | 12,712 | 20.5% |
| `<NaN>` | `<NaN>` | Yes | 6,197 | 10.0% |
| SUCCESS | NONE | Yes | 3,363 | 5.4% |
| UNATTEMPTED | UNSET | Yes | 1,013 | 1.6% |
| COMPLETED | OTHER | Yes | 433 | 0.7% |
| COMPLETED | INCLINED | Yes | 418 | 0.7% |
| UNATTEMPTED | NONE | Yes | 380 | 0.6% |
| COMPLETED | REFUSED | Refusal | 255 | 0.4% |

### Medium Frequency Combinations (10-100 occurrences)

| Hammering_Status | Hammering_Flag | Pile_Installed | Count |
|------------------|----------------|----------------|-------|
| COMPLETED | REFUSED | Yes | 74 |
| UNATTEMPTED | GOOD | Yes | 58 |
| INCOMPLETE_NO_FINISH_TIME | UNSET | Yes | 50 |
| `<NaN>` | `<NaN>` | Refusal | 50 |
| COMPLETED | TWISTED | Yes | 45 |
| COMPLETED | GOOD | Refusal | 43 |
| UNATTEMPTED | UNSET | Refusal | 35 |
| COMPLETED | OTHER | Refusal | 22 |
| INCOMPLETE_NO_FINISH_TIME | GOOD | Yes | 19 |
| COMPLETED (Error to compute...) | GOOD | Yes | 18 |
| INCOMPLETE_NO_FINISH_TIME | UNSET | Refusal | 13 |
| SUCCESS | REFUSED | Refusal | 11 |

### Low Frequency Combinations (≤10 occurrences)

| Hammering_Status | Hammering_Flag | Pile_Installed | Count |
|------------------|----------------|----------------|-------|
| UNATTEMPTED | INCLINED | Yes | 9 |
| COMPLETED | INCLINED | Refusal | 8 |
| SUCCESS | REFUSED | Yes | 6 |
| SUCCESS | NONE | Refusal | 6 |
| COMPLETED | TWISTED | Refusal | 5 |
| COMPLETED (Might need Tap down) | GOOD | Yes | 4 |
| SUCCESS | INCLINED | Yes | 3 |
| UNATTEMPTED | TWISTED | Yes | 3 |
| COMPLETED | GOOD | No | 3 |
| UNATTEMPTED | NONE | Refusal | 3 |
| UNATTEMPTED | UNSET | No | 2 |
| COMPLETED | GOOD | `<NaN>` | 2 |
| INCOMPLETE_NO_FINISH_TIME | REFUSED | Refusal | 2 |
| COMPLETED | UNSET | Yes | 2 |
| COMPLETED | REFUSED | No | 2 |
| COMPLETED | OVERDRIVEN | Yes | 2 |
| COMPLETED (Error to compute...) | OTHER | Yes | 2 |
| INCOMPLETE_NO_FINISH_TIME | UNSET | No | 1 |
| COMPLETED | DAMAGED | Refusal | 1 |
| SUCCESS | REFUSED | No | 1 |
| INCOMPLETE_NO_FINISH_TIME | OTHER | Yes | 1 |
| SUCCESS | TWISTED | Yes | 1 |
| COMPLETED (Error to compute...) | INCLINED | Yes | 1 |
| UNATTEMPTED | INCLINED | No | 1 |
| COMPLETED | TWISTED | `<NaN>` | 1 |
| COMPLETED | INCLINED | `<NaN>` | 1 |
| COMPLETED | DAMAGED | Yes | 1 |

---

## Decision

**`Pile_Installed` is the ultimate determinate for dashboard display.**

The app will compute and assign `Pile_Installed` values (`Yes`, `No`, `Refusal`) based on `Hammering_Status` and `Hammering_Flag` logic baked into the application. This ensures:
- Consistent display across the dashboard
- Single source of truth for installation status
- Logic is maintainable in one place (the app) rather than relying on external data

---

## Installation Logic to Implement

### Import Sources

| Source | Has `Pile_Installed`? | Action |
|--------|----------------------|--------|
| Drive Log (.xls) | Yes | Trust existing value — Yes means Yes, always |
| Nasku (.csv) | **No** | Must compute from `Hammering_Status` + `Hammering_Flag` |

### Logic

```python
def compute_pile_installed(
    hammering_status: str | None,
    hammering_flag: str | None
) -> str:
    """
    Compute Pile_Installed from hammering columns.
    Used during Nasku CSV import (which has no Pile_Installed column).

    Returns: "Yes", "No", or "Refusal"
    """
    # Refusal cases
    if hammering_flag == "REFUSED":
        return "Refusal"

    # Installed cases
    if hammering_status in ("COMPLETED", "SUCCESS"):
        return "Yes"

    # Not installed
    return "No"


def get_pile_installed(
    pile_installed: str | None,
    hammering_status: str | None,
    hammering_flag: str | None
) -> str:
    """
    Get Pile_Installed value.
    - Trusts existing value if present (Drive Log import)
    - Computes if missing (Nasku import)

    Returns: "Yes", "No", or "Refusal"
    """
    # Trust existing values — Yes means Yes, always
    if pile_installed in ("Yes", "No", "Refusal"):
        return pile_installed

    # Compute when missing (Nasku import path)
    return compute_pile_installed(hammering_status, hammering_flag)
```

---

## Key Observations

### Data Anomalies in Source File

1. **6,197 rows** have `Pile_Installed = "Yes"` but no hammering data (NaN in both columns)
   - These may be legacy records or imports from a different system

2. **74 rows** have `COMPLETED + REFUSED + Yes` — marked as installed despite refusal flag

3. **3 rows** have `COMPLETED + GOOD + No` — good completion but not marked installed

4. **4 rows** have NaN in `Pile_Installed`

These anomalies will be resolved by the app's computed logic, which will override any inconsistent source data.

---

## Next Steps

- [ ] Define exact mapping rules for each `Hammering_Status` + `Hammering_Flag` combination
- [ ] Implement `compute_pile_installed()` function in the app
- [ ] Update dashboard to use computed `Pile_Installed` as the display source
- [ ] Decide handling for edge case flags: INCLINED, TWISTED, OTHER, DAMAGED, OVERDRIVEN

---
