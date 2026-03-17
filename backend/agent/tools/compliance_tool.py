"""
Compliance Engine Tool - Checks financial advice against regulatory rules.
Uses YAML-based rule definitions for flexibility.
"""

import logging
from pathlib import Path
from typing import Optional
import yaml
from langchain_core.tools import tool
from config import settings

logger = logging.getLogger(__name__)

# Default compliance rules (used if YAML file doesn't exist)
DEFAULT_RULES = {
    "disclaimers": {
        "investment_advice": {
            "trigger_words": [
                "recommend", "suggest", "should buy", "should sell",
                "best stock", "guaranteed", "sure thing", "can't lose",
                "hot tip", "insider",
            ],
            "required_disclaimer": (
                "This is for informational purposes only and does not constitute "
                "investment advice. Past performance does not guarantee future results. "
                "Please consult with a qualified financial advisor."
            ),
            "severity": "high",
        },
        "tax_advice": {
            "trigger_words": [
                "tax deduction", "tax benefit", "write off", "tax shelter",
                "tax strategy", "avoid taxes", "reduce taxes",
            ],
            "required_disclaimer": (
                "Tax situations vary by individual. This is general information "
                "and not tax advice. Please consult a qualified tax professional."
            ),
            "severity": "high",
        },
    },
    "prohibited_claims": [
        "guaranteed returns",
        "risk-free investment",
        "can't lose money",
        "100% safe",
        "no risk",
        "sure profit",
        "insider information",
        "secret strategy",
    ],
    "suitability_requirements": {
        "must_consider": [
            "risk tolerance",
            "investment timeline",
            "financial goals",
            "current financial situation",
            "diversification",
        ],
        "must_not_assume": [
            "specific income level",
            "tax bracket",
            "risk tolerance without asking",
            "investment experience",
        ],
    },
    "regulatory_references": {
        "SEC": "Securities and Exchange Commission",
        "FINRA": "Financial Industry Regulatory Authority",
        "Reg_BI": "Regulation Best Interest",
        "fiduciary_duty": "Act in client's best interest",
    },
}


def _load_rules() -> dict:
    """Load compliance rules from YAML file or use defaults."""
    rules_file = settings.COMPLIANCE_RULES_DIR / "rules.yaml"

    if rules_file.exists():
        try:
            with open(rules_file, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Failed to load rules.yaml: {e}, using defaults")

    # Save default rules for reference
    try:
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        with open(rules_file, "w") as f:
            yaml.dump(DEFAULT_RULES, f, default_flow_style=False)
    except Exception:
        pass

    return DEFAULT_RULES


@tool
def check_compliance(advice_text: str) -> str:
    """
    Check if financial advice or content complies with regulatory requirements.

    Use this tool to:
    - Verify advice doesn't make prohibited claims
    - Check if proper disclaimers are needed
    - Ensure suitability requirements are considered
    - Flag potential regulatory issues

    Args:
        advice_text: The financial advice or content to check for compliance
    """
    rules = _load_rules()
    findings = []
    advice_lower = advice_text.lower()

    # 1. Check for prohibited claims
    prohibited = rules.get("prohibited_claims", [])
    found_prohibited = []
    for claim in prohibited:
        if claim.lower() in advice_lower:
            found_prohibited.append(claim)

    if found_prohibited:
        findings.append(
            f"🚫 **PROHIBITED CLAIMS DETECTED:**\n"
            f"The following prohibited claims were found:\n"
            + "\n".join(f"  - ❌ '{claim}'" for claim in found_prohibited)
            + "\n\nThese claims violate SEC/FINRA regulations and must be removed."
        )

    # 2. Check for required disclaimers
    disclaimers = rules.get("disclaimers", {})
    needed_disclaimers = []

    for category, rule in disclaimers.items():
        trigger_words = rule.get("trigger_words", [])
        for trigger in trigger_words:
            if trigger.lower() in advice_lower:
                needed_disclaimers.append({
                    "category": category,
                    "trigger": trigger,
                    "disclaimer": rule.get("required_disclaimer", ""),
                    "severity": rule.get("severity", "medium"),
                })
                break  # One trigger per category is enough

    if needed_disclaimers:
        disc_text = "⚠️ **DISCLAIMERS REQUIRED:**\n\n"
        for d in needed_disclaimers:
            disc_text += (
                f"  **{d['category'].replace('_', ' ').title()}** "
                f"(severity: {d['severity']})\n"
                f"  Triggered by: '{d['trigger']}'\n"
                f"  Required: {d['disclaimer']}\n\n"
            )
        findings.append(disc_text)

    # 3. Suitability check
    suitability = rules.get("suitability_requirements", {})
    must_consider = suitability.get("must_consider", [])
    considered = [item for item in must_consider if item.lower() in advice_lower]
    missing = [item for item in must_consider if item.lower() not in advice_lower]

    if missing and any(
        word in advice_lower
        for word in ["recommend", "suggest", "should", "consider investing"]
    ):
        findings.append(
            f"📋 **SUITABILITY REVIEW:**\n"
            f"When making recommendations, consider:\n"
            + "\n".join(f"  ✅ {item}" for item in considered)
            + "\n"
            + "\n".join(f"  ⚠️ Missing: {item}" for item in missing)
        )

    # 4. Overall compliance score
    if not findings:
        return (
            "✅ **COMPLIANCE CHECK PASSED**\n\n"
            "No regulatory issues detected. The content:\n"
            "- Contains no prohibited claims\n"
            "- No additional disclaimers required\n"
            "- Meets basic suitability standards"
        )
    else:
        severity_count = {
            "critical": len(found_prohibited),
            "warnings": len(needed_disclaimers),
        }
        header = (
            f"⚠️ **COMPLIANCE CHECK - {len(findings)} ISSUE(S) FOUND**\n"
            f"Critical: {severity_count['critical']} | "
            f"Warnings: {severity_count['warnings']}\n\n"
        )
        return header + "\n---\n\n".join(findings)