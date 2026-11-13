-- Reference domain: taxonomy, provenance, specimens, assets, embeddings.
-- No table here may hold challenge cases, challenge labels or challenge image hashes.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE taxa (
    taxon_id         text PRIMARY KEY,
    canonical_name   text NOT NULL UNIQUE,
    category         text NOT NULL CHECK (category IN ('MINERAL', 'ROCK')),
    rank             text NOT NULL,
    confusion_group  text NOT NULL,
    taxonomy_version text NOT NULL
);

CREATE TABLE specimens (
    specimen_id text PRIMARY KEY,
    taxon_id    text NOT NULL REFERENCES taxa(taxon_id),
    source_name text NOT NULL,
    locality    text,
    notes       text
);

CREATE TABLE assets (
    asset_id       text PRIMARY KEY,
    specimen_id    text NOT NULL REFERENCES specimens(specimen_id),
    source_name    text NOT NULL,
    source_url     text NOT NULL,
    media_url      text NOT NULL,   -- where the image is re-fetched from; images are not stored (see DECISIONS.md)
    author         text,
    license        text NOT NULL,
    retrieval_date date NOT NULL,
    usage_decision text NOT NULL CHECK (usage_decision IN ('allowed_train', 'allowed_reference_only')),
    sha256         char(64) NOT NULL UNIQUE,
    phash          char(16) NOT NULL,
    quarantined    boolean NOT NULL DEFAULT false,
    quarantine_reason text,
    created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX assets_phash_idx ON assets (phash);

CREATE TABLE encoders (
    encoder_version text PRIMARY KEY,   -- family:model_id@revision
    family          text NOT NULL,
    model_id        text NOT NULL,
    revision        text NOT NULL,
    dim             integer NOT NULL,
    license         text NOT NULL,
    registered_at   timestamptz NOT NULL DEFAULT now()
);

-- 768 = dinov2-base and siglip2-base. A different dimension needs its own table/column.
CREATE TABLE embeddings (
    asset_id        text NOT NULL REFERENCES assets(asset_id) ON DELETE CASCADE,
    encoder_version text NOT NULL REFERENCES encoders(encoder_version),
    embedding       vector(768) NOT NULL,
    PRIMARY KEY (asset_id, encoder_version)
);
CREATE INDEX embeddings_hnsw_cos ON embeddings USING hnsw (embedding vector_cosine_ops);
