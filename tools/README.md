# tools/

Development-only tooling. **Never imported by the application and never shipped
to runtime.** If something here is needed by the running bot, it belongs in
`src/mika/`, not here.

## hooks/

Custom git hooks wired through `.pre-commit-config.yaml`, enforcing the rules in
[`../AGENTS.md`](../AGENTS.md) section 2. Each is stdlib-only and runs standalone.

| Hook | Stage | Blocks |
|---|---|---|
| `check_no_coauthors.py` | commit-msg | co-author / AI-attribution trailers |
| `check_ai_comments.py` | pre-commit | AI-slop, narration, placeholder comments |
| `check_comment_ratio.py` | pre-commit | oversized files and comment-dominated files |
| `check_secrets.py` | pre-commit | secret-shaped strings and sensitive filenames |
| `check_persona_leak.py` | pre-commit | the codename in user-facing command surfaces |

Run one by hand:

```bash
python tools/hooks/check_ai_comments.py path/to/file.py
```

Thresholds (file size, comment ratio, comment-block length) live as constants at
the top of each script. Adjust there if a rule is too strict for a real case;
prefer the per-line `# allow-comment` escape hatch over loosening a global limit.
