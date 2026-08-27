# Security

## Reporting

Please use GitHub private vulnerability reporting. Do not open a public issue containing credentials, transcripts, or private memory.

## Local data

The vault and captured sessions may contain sensitive material. Recall is local-only and no network listener is created. Queue content and SQLite indexes are excluded from Git, but `.gitignore` is not a security boundary. Inspect staged files before publishing a vault.

The built-in scrubber recognizes common token/password shapes and bounds captured fields. It cannot recognize every secret. Rotate any credential that entered a harness transcript.
