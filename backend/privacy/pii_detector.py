"""
PII Detection and Anonymization using Microsoft Presidio.
Detects SSNs, credit card numbers, bank accounts, phone numbers,
emails, and other sensitive financial information.
"""

import logging
from typing import Optional
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

logger = logging.getLogger(__name__)


class PIIDetector:
    """
    Detects and anonymizes Personally Identifiable Information (PII)
    in text using Microsoft Presidio.
    """

    # PII types relevant to financial advisory
    FINANCIAL_PII_ENTITIES = [
        "CREDIT_CARD",
        "CRYPTO",
        "IBAN_CODE",
        "IP_ADDRESS",
        "US_BANK_NUMBER",
        "US_SSN",
        "US_ITIN",
        "US_PASSPORT",
        "US_DRIVER_LICENSE",
        "PHONE_NUMBER",
        "EMAIL_ADDRESS",
        "PERSON",
        "LOCATION",
        "DATE_TIME",
    ]

    def __init__(self):
        """Initialize Presidio engines."""
        try:
            self.analyzer = AnalyzerEngine()
            self.anonymizer = AnonymizerEngine()
            self._initialized = True
            logger.info("PIIDetector initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PIIDetector: {e}")
            self._initialized = False

    def detect(self, text: str, language: str = "en") -> list[dict]:
        """
        Detect PII entities in text.

        Returns list of detected PII with type, location, and confidence.
        """
        if not self._initialized or not text:
            return []

        try:
            results: list[RecognizerResult] = self.analyzer.analyze(
                text=text,
                entities=self.FINANCIAL_PII_ENTITIES,
                language=language,
            )

            detections = []
            for result in results:
                detections.append({
                    "entity_type": result.entity_type,
                    "start": result.start,
                    "end": result.end,
                    "score": round(result.score, 3),
                    "text_snippet": text[max(0, result.start - 5):result.end + 5],
                })

            return detections

        except Exception as e:
            logger.error(f"PII detection error: {e}")
            return []

    def anonymize(
        self,
        text: str,
        language: str = "en",
        operator: str = "replace",
    ) -> tuple[str, list[dict]]:
        """
        Detect and anonymize PII in text.

        Args:
            text: Input text to anonymize
            language: Language code
            operator: 'replace', 'redact', 'hash', or 'mask'

        Returns:
            Tuple of (anonymized_text, list_of_detections)
        """
        if not self._initialized or not text:
            return text, []

        try:
            # Detect PII
            analyzer_results = self.analyzer.analyze(
                text=text,
                entities=self.FINANCIAL_PII_ENTITIES,
                language=language,
            )

            if not analyzer_results:
                return text, []

            # Configure anonymization operators
            operators = {}
            if operator == "replace":
                for entity_type in self.FINANCIAL_PII_ENTITIES:
                    operators[entity_type] = OperatorConfig(
                        "replace",
                        {"new_value": f"<{entity_type}>"}
                    )
            elif operator == "redact":
                for entity_type in self.FINANCIAL_PII_ENTITIES:
                    operators[entity_type] = OperatorConfig("redact")
            elif operator == "hash":
                for entity_type in self.FINANCIAL_PII_ENTITIES:
                    operators[entity_type] = OperatorConfig(
                        "hash", {"hash_type": "sha256"}
                    )
            elif operator == "mask":
                for entity_type in self.FINANCIAL_PII_ENTITIES:
                    operators[entity_type] = OperatorConfig(
                        "mask",
                        {"masking_char": "*", "chars_to_mask": 100, "from_end": False}
                    )

            # Anonymize
            anonymized = self.anonymizer.anonymize(
                text=text,
                analyzer_results=analyzer_results,
                operators=operators,
            )

            # Build detections list
            detections = [
                {
                    "entity_type": r.entity_type,
                    "score": round(r.score, 3),
                    "action": operator,
                }
                for r in analyzer_results
            ]

            return anonymized.text, detections

        except Exception as e:
            logger.error(f"PII anonymization error: {e}")
            return text, []

    def has_pii(self, text: str, min_score: float = 0.7) -> bool:
        """Quick check if text contains PII above confidence threshold."""
        detections = self.detect(text)
        return any(d["score"] >= min_score for d in detections)

    def get_pii_summary(self, text: str) -> dict:
        """Get a summary of PII found in text."""
        detections = self.detect(text)
        summary = {
            "has_pii": len(detections) > 0,
            "total_entities": len(detections),
            "entity_types": list(set(d["entity_type"] for d in detections)),
            "high_confidence": [d for d in detections if d["score"] >= 0.85],
        }
        return summary


# Singleton
pii_detector = PIIDetector()