# Private Submission Config Example

Create an ignored sibling directory named `private_submission_config/` when preparing a tutor/course submission package.

Allowed files:

- `expression_settings.json`
- `capability_settings.json`
- `long_term_memory.json`
- `dialogue_history.json`
- `companion_demo_save.json`

These files are copied into the course submission package as `user_data/`, so the frozen app can load private tutor-review settings directly after unzip.

Do not commit `private_submission_config/`.
