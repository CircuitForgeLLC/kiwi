-- Migration 035: add sensory_tags column for sensory profile filtering
--
-- sensory_tags holds a JSON object with texture, smell, and noise signals:
--   {"textures": ["mushy", "creamy"], "smell": "pungent", "noise": "moderate"}
--
-- Empty object '{}' means untagged — these recipes pass ALL sensory filters
-- (graceful degradation when tag_sensory_profiles.py has not yet been run).
--
-- Populated offline by: python scripts/tag_sensory_profiles.py [path/to/kiwi.db]
-- No FTS rebuild needed — sensory_tags is filtered in Python after candidate fetch.

ALTER TABLE recipes ADD COLUMN sensory_tags TEXT NOT NULL DEFAULT '{}';
