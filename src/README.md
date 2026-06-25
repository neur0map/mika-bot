# src/

Python source root (src layout). The application package lives in
[`mika/`](mika/README.md); nothing else belongs at this level. The src layout
keeps the installed package importable only via the project install, never by
accident from the repo root.
