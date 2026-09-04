"""Feature registry definition and loader."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import yaml
import polars as pl


@dataclass
class FeatureDefinition:
    name: str
    entity: str
    source_event: str
    aggregation: str
    window: str
    available_at_rule: str
    ttl: str
    version: str
    owner: str
    fraud_mechanism: str


class FeatureRegistry:
    """Manages feature definitions and validates datasets against registered schemas."""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        self.version: str = "fv-2.1"
        self.features: Dict[str, FeatureDefinition] = {}
        if config_path:
            self.load(config_path)

    @classmethod
    def load_from_yaml(cls, config_path: Union[str, Path]) -> "FeatureRegistry":
        registry = cls()
        registry.load(config_path)
        return registry

    def load(self, config_path: Union[str, Path]) -> None:
        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(f"Feature registry config not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.version = data.get("version", "fv-2.1")
        self.features = {}
        for item in data.get("features", []):
            feat = FeatureDefinition(
                name=item["name"],
                entity=item.get("entity", "unknown"),
                source_event=item.get("source_event", "unknown"),
                aggregation=item.get("aggregation", "unknown"),
                window=item.get("window", "none"),
                available_at_rule=item.get("available_at_rule", "event.timestamp"),
                ttl=item.get("ttl", "86400s"),
                version=item.get("version", self.version),
                owner=item.get("owner", "risk_ml"),
                fraud_mechanism=item.get("fraud_mechanism", "general"),
            )
            self.features[feat.name] = feat

    def get_feature(self, name: str) -> Optional[FeatureDefinition]:
        return self.features.get(name)

    def get_feature_names(self) -> List[str]:
        return list(self.features.keys())

    def get_all_features(self) -> List[FeatureDefinition]:
        return list(self.features.values())

    def get_by_fraud_mechanism(self, mechanism: str) -> List[FeatureDefinition]:
        return [f for f in self.features.values() if f.fraud_mechanism == mechanism]

    def get_by_entity(self, entity: str) -> List[FeatureDefinition]:
        return [f for f in self.features.values() if f.entity == entity]

    def validate_dataframe(self, df: pl.DataFrame) -> Tuple[bool, List[str]]:
        """Validates that all registry features exist in the given Polars DataFrame."""
        missing = [f for f in self.get_feature_names() if f not in df.columns]
        return len(missing) == 0, missing
