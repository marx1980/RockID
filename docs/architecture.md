# Architecture
Consumer/mobile -> Identify API -> image quality -> visual encoder(s) -> reference vector search -> specimen-balanced taxon aggregation -> structured property reranker -> calibration/abstention -> result/follow-up.

RockLab evaluator (challenge + reference networks) -> Challenge Vault -> sends image bytes only over HTTP -> exact Identify API -> freezes prediction -> Evaluator reveals hidden labels -> metrics -> Improvement proposals -> new independent reference material -> candidate model -> release gate.
