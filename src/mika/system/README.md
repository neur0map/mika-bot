# system/

Service control: turning a checkout into managed systemd services on the VPS.
Depends on `core` only.

- `manager.py` - renders unit files from `deploy/` templates and runs systemctl.
- `units/` - unit-file templates rendered at install time.
