"""Evidence builder: constructs concrete, human-readable audit statements from feature values."""

from typing import Any, Dict
from src.common.logging import get_logger

logger = get_logger("explainability.evidence")


class EvidenceBuilder:
    """Renders templated evidence narratives using exact decision-time feature values."""

    @staticmethod
    def render_template(template: str, features: Dict[str, Any]) -> str:
        """Safely renders template string with feature values, handling missing keys."""
        # Create a formatting dict with safe defaults
        fmt_dict = {}
        for k, v in features.items():
            if isinstance(v, float):
                if v.is_integer():
                    fmt_dict[k] = int(v)
                else:
                    fmt_dict[k] = v
            elif isinstance(v, int):
                fmt_dict[k] = v
            else:
                try:
                    num = float(v)
                    fmt_dict[k] = int(num) if num.is_integer() else num
                except (ValueError, TypeError):
                    fmt_dict[k] = v

        try:
            return template.format(**fmt_dict)
        except KeyError as missing_key:
            # Provide default 0.0 for missing key and retry
            k_str = str(missing_key).strip("'")
            fmt_dict[k_str] = 0.0
            try:
                return template.format(**fmt_dict)
            except Exception:
                return template
        except Exception as e:
            logger.warning(f"Error formatting template '{template}': {e}")
            return template

    @staticmethod
    def build_evidence(
        code: str,
        template: str,
        features: Dict[str, Any],
        relevant_feature_names: list[str],
    ) -> tuple[str, Dict[str, Any]]:
        """Constructs evidence string and dictionary of supporting feature values."""
        supporting = {
            f: features.get(f, 0.0)
            for f in relevant_feature_names
            if f in features
        }
        text = EvidenceBuilder.render_template(template, features)
        return text, supporting
