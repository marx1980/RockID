from dataclasses import dataclass, field
from typing import Optional

@dataclass(frozen=True)
class SourceProvenance:
    source_name: str
    source_url: str
    license: Optional[str]
    retrieval_date: str
    usage_decision: str  # allowed_train | allowed_reference_only | rejected | pending

@dataclass(frozen=True)
class ChallengeCase:
    id: str
    object_uri: str
    ground_truth_id: str
    accepted_labels: list[str] = field(default_factory=list)
    difficulty: str = "collector"
