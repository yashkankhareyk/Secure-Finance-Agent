"""
Output sanitization layer.
Ensures agent responses don't leak PII, contain proper disclaimers,
and are appropriate for a financial advisory context.
"""

import re
import logging
from typing import Optional
from .pii_detector import pii_detector

logger = logging.getLogger(__name__)


class OutputSanitizer:
    """Sanitizes agent output before returning to user."""

    FINANCIAL_DISCLAIMER = (
        "\n\n---\n"
        "⚠️ **Disclaimer**: This information is for educational purposes only "
        "and does not constitute financial advice. Always consult with a qualified "
        "financial advisor before making investment decisions. Past performance "
        "does not guarantee future results."
    )

    # Patterns that should never appear in output
    FORBIDDEN_OUTPUT_PATTERNS = [
        r"(?:system\s*prompt|internal\s*instructions?)[\s:]*",
        r"(?:my\s+(?:instructions?|training|rules)\s+(?:say|tell|are))",
        r"(?:I\s+(?:was|am)\s+(?:instructed|told|programmed)\s+to)",
        r"api[_\s]?key\s*[:=]\s*\S+",
        r"(?:password|secret|token)\s*[:=]\s*\S+",
    ]

    def __init__(self):
        self._forbidden_compiled = [
            re.compile(p, re.IGNORECASE)
            for p in self.FORBIDDEN_OUTPUT_PATTERNS
        ]

    def sanitize(
        self,
        text: str,
        add_disclaimer: bool = True,
        check_pii: bool = True,
        session_id: Optional[str] = None,
    ) -> dict:
        """
        Sanitize agent output.

        Returns:
            {
                "text": sanitized text,
                "pii_found": list of PII detections,
                "modifications": list of modifications made,
                "disclaimer_added": bool
            }
        """
        modifications = []
        pii_found = []
        result_text = text

        # 1. Check for forbidden patterns
        for pattern in self._forbidden_compiled:
            if pattern.search(result_text):
                result_text = pattern.sub("[REDACTED]", result_text)
                modifications.append("removed_forbidden_pattern")

        # 2. Check for PII in output
        if check_pii:
            anonymized_text, detections = pii_detector.anonymize(
                result_text, operator="replace"
            )
            if detections:
                result_text = anonymized_text
                pii_found = detections
                modifications.append("anonymized_pii")
                logger.warning(
                    f"PII found in output (session: {session_id}): "
                    f"{[d['entity_type'] for d in detections]}"
                )

        # 3. Add disclaimer for financial content
        if add_disclaimer and self._is_financial_content(result_text):
            result_text += self.FINANCIAL_DISCLAIMER
            modifications.append("added_disclaimer")

        return {
            "text": result_text,
            "pii_found": pii_found,
            "modifications": modifications,
            "disclaimer_added": "added_disclaimer" in modifications,
        }

    def _is_financial_content(self, text: str) -> bool:
        """Check if response contains financial advice-like content."""
        financial_keywords = [
            "invest", "stock", "bond", "portfolio", "return",
            "risk", "dividend", "market", "fund", "asset",
            "allocation", "retirement", "savings", "interest rate",
            "inflation", "diversif", "capital", "equity",
            "recommend", "suggest", "consider", "strategy",
            "buy", "sell", "hold", "price target",
        ]
        text_lower = text.lower()
        matches = sum(1 for kw in financial_keywords if kw in text_lower)
        return matches >= 2  # At least 2 financial keywords

    def quick_clean(self, text: str) -> str:
        """Quick clean without full sanitization - for internal use."""
        # Remove any accidentally leaked system prompts
        for pattern in self._forbidden_compiled:
            text = pattern.sub("", text)
        return text.strip()


# Singleton
output_sanitizer = OutputSanitizer()