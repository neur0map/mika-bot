# bot/commands/

One file per slash command. To stay under Discord's 100-command cap, group related
actions as subcommands of a single `/category`. `ping.py` is the template.

**Never hardcode the codename or a bot name here.** Command names, descriptions, and
replies are user-facing: use neutral wording, and `config.persona.name` for the
bot's name. The persona-leak hook blocks a literal codename in this folder.
