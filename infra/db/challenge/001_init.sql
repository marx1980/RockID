-- Challenge Vault. Only the evaluator holds credentials for this database.
CREATE TABLE challenge_cases (
    case_id          text PRIMARY KEY,           -- opaque, label-free identifier
    suite            text NOT NULL CHECK (suite IN
                      ('museum', 'collector', 'field', 'pebble_weathered',
                       'confusion_pair', 'unknown_ood', 'low_quality')),
    object_uri       text NOT NULL,
    specimen_id      text NOT NULL,              -- must not exist in the reference domain
    source_name      text NOT NULL,
    source_url       text,
    sha256           char(64) NOT NULL UNIQUE,
    phash            char(16) NOT NULL,
    ground_truth_id  text NOT NULL,              -- taxon_id, or 'UNKNOWN' for OOD
    accepted_labels  text[] NOT NULL DEFAULT '{}',
    verified_by      text NOT NULL,
    frozen_suite_version text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now()
);

-- Append-only: a prediction is written once, before the label is revealed.
CREATE TABLE predictions (
    run_id            text NOT NULL,
    case_id           text NOT NULL REFERENCES challenge_cases(case_id),
    model_version     text NOT NULL,
    frozen_at         timestamptz NOT NULL DEFAULT now(),
    prediction        jsonb NOT NULL,
    prediction_sha256 char(64) NOT NULL,
    PRIMARY KEY (run_id, case_id)
);

CREATE FUNCTION forbid_prediction_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'predictions are append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER predictions_append_only
    BEFORE UPDATE OR DELETE ON predictions
    FOR EACH ROW EXECUTE FUNCTION forbid_prediction_change();
