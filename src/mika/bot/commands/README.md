# bot/commands

Legacy slash-command catalog retained for compatibility and its offline harness. The
conversation-only runtime does not call `register_all` or sync this tree.

Active conversation abilities live one-per-directory under
`conversation/tools/abilities`; new runtime capabilities must not be added here.

**Never hardcode the codename or a bot name here.** Command names, descriptions, and
replies are user-facing: use neutral wording, and `config.persona.name` for the
bot's name. The persona-leak hook blocks a literal codename in this folder.
