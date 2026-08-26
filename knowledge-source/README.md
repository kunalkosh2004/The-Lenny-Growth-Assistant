# Knowledge Source

Place the local transcript repository here:

```text
knowledge-source/lennys-podcast-transcripts/
```

The ingestion pipeline will read:

```text
knowledge-source/lennys-podcast-transcripts/episodes/**/transcript.md
```

The transcript repository itself is ignored by Git to avoid committing a large
raw data source into the application repository.
