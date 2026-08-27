# Adding a harness

A harness adapter has two small responsibilities:

1. On a user prompt, send its text to the local recall path and inject only returned Markdown pointers.
2. On session end, map available lifecycle data to provenance schema v1 and enqueue it asynchronously.

Do not add harness conditionals to index, retrieval, capture, or synthesis. Preserve existing harness configuration using read → parse → backup → merge → atomic write. A missing daemon or capture error must never block the harness.

Schema fields are `schema_version`, `session_id`, `harness`, `host`, `project`, `cwd`, `started_at`, `ended_at`, `branch`, `prompts`, `commands`, `files_changed`, and `final_response`. Unknown values remain null or empty.
