"""
Prompt injection detection and input validation.
Uses pattern matching and heuristic rules to detect malicious prompts.
No heavy ML dependencies - fast and effective.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class PromptGuard:
    """
    Detects prompt injection attacks, jailbreak attempts,
    and out-of-scope queries for the financial advisory context.
    """

    # Prompt injection patterns
    INJECTION_PATTERNS = [
        # Direct instruction override
        r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
        r"disregard\s+(all\s+)?(previous|prior|above)",
        r"forget\s+(all\s+)?(previous|prior|above|everything|your)\s*(instructions|rules|training)?",
        r"you\s+are\s+now\s+(?:a|an)\s+(?!financial)",
        r"act\s+as\s+(?:if\s+you\s+are\s+)?(?!a\s+financial)",
        r"pretend\s+(you\s+are|to\s+be)",
        r"new\s+instruction[s]?\s*:",
        r"system\s*prompt\s*:",
        r"override\s+(system|safety|security)",

        # Data extraction attempts
        r"(reveal|show|display|tell\s+me)\s+(your|the)\s+(system\s+)?prompt",
        r"(what|show)\s+(is|are)\s+your\s+(instructions|rules|system\s+prompt)",
        r"repeat\s+(the\s+)?(system\s+)?(prompt|instructions)",
        r"output\s+(your|the)\s+(system|initial)\s+(prompt|instructions|message)",

        # Code execution attacks
        r"(execute|run|eval)\s*(this\s+)?(code|script|command)",
        r"```\s*(python|bash|sh|javascript|js)\s*\n.*?(os\.|subprocess|exec|eval|import\s+os)",
        r"__import__",
        r"os\.system",
        r"subprocess\.",

        # Delimiter injection
        r"<\|.*?\|>",
        r"\[INST\]",
        r"\[\/INST\]",
        r"<<SYS>>",
        r"<\|im_start\|>",

        # Role manipulation
        r"(you\s+must|always)\s+(respond|answer|say|output)\s+with",
        r"from\s+now\s+on\s+(you|always|only)",
    ]

    # Topics outside financial advisory scope
    OUT_OF_SCOPE_PATTERNS = [
        r"(how\s+to\s+)?(make|build|create)\s+(a\s+)?(bomb|weapon|explosive)",
        r"(hack|crack|break\s+into)\s+(a\s+)?(system|account|bank|computer)",
        r"(illegal|illicit)\s+(activity|scheme|operation)",
        r"money\s+launder",
        r"(tax\s+)?(evasion|evade\s+taxes)",
        r"insider\s+trading\s+(tips|advice|how)",
        r"(ponzi|pyramid)\s+scheme",
    ]

    # Max input length (characters)
    MAX_INPUT_LENGTH = 5000

    def __init__(self):
        # Compile patterns for performance
        self._injection_compiled = [
            re.compile(p, re.IGNORECASE | re.DOTALL)
            for p in self.INJECTION_PATTERNS
        ]
        self._oos_compiled = [
            re.compile(p, re.IGNORECASE)
            for p in self.OUT_OF_SCOPE_PATTERNS
        ]

    def check(self, text: str) -> dict:
        """
        Comprehensive input security check.

        Returns:
            {
                "safe": bool,
                "threats": [{"type": str, "severity": str, "detail": str}],
                "sanitized_input": str or None
            }
        """
        threats = []

        # 1. Length check
        if len(text) > self.MAX_INPUT_LENGTH:
            threats.append({
                "type": "excessive_length",
                "severity": "medium",
                "detail": f"Input length {len(text)} exceeds max {self.MAX_INPUT_LENGTH}",
            })

        # 2. Empty/whitespace check
        if not text or not text.strip():
            return {
                "safe": False,
                "threats": [{"type": "empty_input", "severity": "low", "detail": "Empty input"}],
                "sanitized_input": None,
            }

        # 3. Prompt injection detection
        text_lower = text.lower()
        for i, pattern in enumerate(self._injection_compiled):
            match = pattern.search(text)
            if match:
                threats.append({
                    "type": "prompt_injection",
                    "severity": "critical",
                    "detail": f"Injection pattern detected: '{match.group()[:50]}...'",
                })
                break  # One injection finding is enough to block

        # 4. Out-of-scope detection
        for pattern in self._oos_compiled:
            match = pattern.search(text)
            if match:
                threats.append({
                    "type": "out_of_scope",
                    "severity": "high",
                    "detail": f"Out-of-scope topic detected: '{match.group()[:50]}'",
                })
                break

        # 5. Excessive special characters (encoding attacks)
        special_ratio = sum(1 for c in text if not c.isalnum() and c not in " .,?!$%()-:;'\"\n") / max(len(text), 1)
        if special_ratio > 0.3:
            threats.append({
                "type": "suspicious_encoding",
                "severity": "medium",
                "detail": f"High special character ratio: {special_ratio:.2%}",
            })

        # 6. Repeated characters (DoS attempt)
        if re.search(r"(.)\1{50,}", text):
            threats.append({
                "type": "repeated_characters",
                "severity": "medium",
                "detail": "Excessive character repetition detected",
            })

        # Determine if safe
        critical_threats = [t for t in threats if t["severity"] == "critical"]
        high_threats = [t for t in threats if t["severity"] == "high"]

        is_safe = len(critical_threats) == 0 and len(high_threats) == 0

        # Sanitize input (trim length, strip control characters)
        sanitized = text[:self.MAX_INPUT_LENGTH].strip()
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", sanitized)

        return {
            "safe": is_safe,
            "threats": threats,
            "sanitized_input": sanitized if is_safe else None,
        }

    def is_safe(self, text: str) -> bool:
        """Quick boolean check."""
        return self.check(text)["safe"]


# Singleton
prompt_guard = PromptGuard()