# tools/hooks/

Custom git hook scripts wired through `../../.pre-commit-config.yaml`. See
[`../README.md`](../README.md) for the full table of what each blocks. Every
script is stdlib-only and runs standalone:

```bash
python tools/hooks/check_secrets.py <file>...
```
