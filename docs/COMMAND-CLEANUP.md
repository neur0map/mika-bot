# Removing stale Discord commands

Mika no longer registers Discord application commands. Discord retains commands that
were registered by older versions until they are explicitly removed.

Run this **once**, only after checking the configured application ID and guild scope:

```bash
mika cleanup-commands --confirm delete-discord-commands
```

The command first lists the global and configured-guild command endpoints. Only if every
list request succeeds, it uses Discord's bulk-overwrite API with an empty list for each
scope. It records only the timestamp and deletion counts in the optional shared archive;
it never stores the token or command payloads.

This action is permanent for the selected application scopes. The configured guild list
must include every guild that previously received guild-scoped commands. A successful
result reports global, guild, and total deletion counts; confirm Discord's UI shows zero
application commands afterwards.
