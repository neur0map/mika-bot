# Getting Started with Mika

**Your all-purpose Discord bot + AI, for dummies.**

Mika is a friendly Discord bot you run yourself on your own computer (or a small server). It chats with your friends using AI, has handy slash commands (`/8ball`, `/dice`, `/cat`, and more), and is designed so you do **not** need to know how to code. If you can follow a numbered list and copy-paste, you can get Mika running.

This guide takes you from "I just downloaded the zip" to "the bot is chatting in my server" in about 10 minutes.

---

## What you need before starting

Before you touch anything, please have these ready:

- **A Discord account.** The free kind. If you use Discord already, you're set.
- **A Discord server you own** (or where you have the *Manage Server* permission). Mika has to be invited to a server by someone who's allowed to invite bots. If you don't have one, click the **+** in your Discord sidebar and choose *Create My Own* — it takes 10 seconds.
- **About 10 minutes** of uninterrupted time.
- **The Mika zip file**, unzipped to a folder somewhere you can find it again (Desktop, Documents, wherever). On Windows we recommend using WSL (Windows Subsystem for Linux); these instructions assume **Linux or macOS**.

You do **not** need to install Python, pip, or anything else by hand. The installer handles all of that for you.

---

## Step 1 — Open a terminal in the Mika folder

A **terminal** is just a text window where you type commands instead of clicking. Don't worry — you only need to paste a couple of things.

### On macOS

1. Open **Finder** and go to the folder where you unzipped Mika (e.g. `~/Downloads/mika-bot`).
2. **Right-click** the folder (or hold **Control** and click).
3. Choose **New Terminal at Folder**.
   - If you don't see that option: open **System Settings → Keyboard → Keyboard Shortcuts → Services**, and turn on *New Terminal at Folder*. Then try again.
4. A black-and-white text window will appear. That's your terminal. You're now "inside" the Mika folder.

### On Linux

Most Linux file managers (Files/Nautilus, Dolphin, Thunar, etc.) let you right-click an empty space inside the folder and choose **Open Terminal Here** or **Open in Terminal**.

If yours doesn't, open your terminal app from the menu and type:

```
cd ~/Downloads/mika-bot
```

(replace the path with wherever you actually unzipped Mika). Press **Enter**. The prompt should now show the folder name.

### Quick sanity check

Type this and press **Enter**:

```
ls
```

You should see files like `install.sh`, `README.md`, and a folder named `mika`. If you do, you're in the right place. If you see something unrelated, you opened the terminal in the wrong folder — try Step 1 again.

---

## Step 2 — Run the installer

Now copy-paste this into the terminal and press **Enter**:

```
./install.sh
```

Here's what's about to happen, so nothing surprises you:

1. The installer downloads and installs a small Python toolchain called **uv**. (You don't need to know what that is — it's just what runs Mika under the hood.)
2. It installs all of Mika's dependencies. You'll see lots of lines scroll by — this is normal and means it's working.
3. When the noisy part finishes, it automatically launches the **setup wizard** (Step 3 below).

This usually takes 1–3 minutes depending on your internet. If it asks for your password at any point, that's the system asking permission to install something — type your computer's login password and press **Enter** (you won't see characters appear; that's normal for terminals).

**If it errors out:** scroll up, read the last few red lines, and check that you have an internet connection. Running `./install.sh` again is safe.

---

## Step 3 — The setup wizard

When the installer finishes, the **setup wizard** starts on its own. It's just a friendly questionnaire in the terminal. You answer a few questions and it saves your answers for you. You will **never** have to edit a config file by hand.

It will ask you for three things:

1. **Your Discord bot token.** This is a long secret string that lets Mika log in to Discord as your bot — think of it like a password for the bot account. If you don't have one yet, follow **[DISCORD-SETUP.md](DISCORD-SETUP.md)** first, then come back. The whole thing takes about 5 minutes.
2. **A name for your bot** (the *persona name*). This is what the AI calls itself when it talks. "Mika" is fine; so is anything else — "Biscuit", "Captain Bot", whatever you like.
3. **An LLM API key.** "LLM" just means the AI brain that powers the chat. We recommend **OpenRouter** because it's cheap, has free models, and gives you access to lots of options through one key:
   - Go to **https://openrouter.ai** and sign up (Google login works).
   - Click **Keys** in the sidebar, then **Create Key**.
   - Copy the key it shows you (it starts with `sk-or-...`) and paste it into the wizard.

When you finish answering, the wizard writes everything to a hidden file called `.env` in your Mika folder. That's where your settings live from now on. Keep that file private — it contains your secrets.

**If you ever want to redo the wizard** (for example, to change the bot's name or use a different AI model), you can run it again:

```
mika setup
```

---

## Step 4 — Test the AI without Discord

Before we hook the bot up to your server, let's make sure the AI brain works. In the same terminal, type:

```
mika chat "hello"
```

You should see Mika reply in the terminal a moment later. Try a couple more:

```
mika chat "what's a good name for a hamster?"
mika chat "tell me a one-line joke"
```

If you get replies, the AI side is working perfectly. If you get an error about an API key, your OpenRouter key probably wasn't pasted correctly — run `mika setup` again and re-paste it.

This little chat tool is also great for testing prompts later, without spamming your Discord server.

---

## Step 5 — Check everything is set up correctly

Mika comes with a built-in health check. Run:

```
mika doctor
```

This goes through every feature one at a time and reports **pass** or **fail** for each one — Discord connection, AI key, persona, optional features, the works. If everything is green, you're ready to go live.

If something says **fail**, the message next to it tells you what's missing (usually a value that wasn't filled in, or a token that's wrong). Fix it with `mika setup` and run `mika doctor` again until it's all happy.

---

## Step 6 — Start the bot

Time to go live. Run:

```
mika run
```

(or, if you prefer, `make run` — they do the same thing.)

You'll see a few startup messages and then a line like **"Logged in as YourBotName"**. That means your bot is now online in Discord. Open Discord and check your server — the bot should appear in the member list with a green dot.

**Keep this terminal window open.** As long as it's running, the bot is online. If you close the window or shut down your computer, the bot goes offline. To stop it on purpose, click on the terminal and press **Ctrl+C**.

> **Want it online 24/7?** Once you're comfortable, you can run Mika on a cheap VPS (a small always-on server you rent, usually $4–6 a month from providers like Hetzner, DigitalOcean, or Vultr). The setup is identical to what you just did — unzip on the VPS, `./install.sh`, `mika setup`, `mika run`. That's a project for another day; for now, your laptop is fine.

---

## How to talk to the bot

There are two ways to chat with Mika in Discord:

1. **Mention it.** In any channel the bot can see, type `@YourBotName` followed by your message:
   > `@Mika what's the weather like on Mars?`

   Mika will reply in the same channel. This works everywhere the bot has permission to read and write.

2. **Use a free-chat channel.** During setup (or later, in `.env`) you can list one or more channels where Mika replies to **every** message without needing a mention — useful for a dedicated `#ai-chat` room. To set that up, copy the channel's ID (see [DISCORD-SETUP.md](DISCORD-SETUP.md), the Developer Mode section) into the `DISCORD_RESPONSE_CHANNEL_IDS` setting.

### Slash commands

Mika also ships with handy commands. In Discord, type `/` in any channel and Discord will show you a list. The ones Mika provides are:

| Command       | What it does                                                |
|---------------|-------------------------------------------------------------|
| `/help`       | Shows the in-Discord help menu                              |
| `/ask`        | Ask the AI a one-off question                               |
| `/8ball`      | Magic 8-ball answer to a yes/no question                    |
| `/coinflip`   | Flips a coin                                                |
| `/dice`       | Rolls dice (e.g. `2d6`)                                     |
| `/choose`     | Picks one option from a list you give it                    |
| `/userinfo`   | Shows info about a Discord user                             |
| `/serverinfo` | Shows info about the current server                         |
| `/avatar`     | Shows a user's profile picture, big                         |
| `/cat`        | A random cat picture                                        |
| `/dog`        | A random dog picture                                        |

Slash commands can take a minute or two to appear in Discord the very first time the bot starts up — that's Discord's caching, not a bug. Refresh the app (**Ctrl+R**) if you're impatient.

---

## Troubleshooting

Stuck? Try these in order. Most problems fall into one of three categories.

### "The bot shows as offline in Discord"

- Is the terminal window where you ran `mika run` still open? If you closed it, the bot stopped. Open a terminal in the Mika folder and run `mika run` again.
- Does your computer have internet? Mika needs to reach Discord and your AI provider.
- Run `mika doctor` in a second terminal. If anything reports **fail**, that's almost certainly your culprit.

### "The bot is online but doesn't reply when I @mention it"

This is almost always one specific thing: the **Message Content Intent** is turned off. (An "intent" is a permission Discord makes you tick to let bots read message text.)

1. Go to **https://discord.com/developers/applications** and click your bot's application.
2. Click **Bot** in the left sidebar.
3. Scroll to **Privileged Gateway Intents** and turn on **MESSAGE CONTENT INTENT**. Save.
4. Stop the bot (**Ctrl+C** in the terminal) and run `mika run` again.

Other things to check:
- Does the bot have permission to **View Channel**, **Send Messages**, and **Read Message History** in that specific channel? In Discord, right-click the channel → **Edit Channel** → **Permissions** → make sure your bot's role can do those three.
- Are you @mentioning the **bot user** (with the green dot in the member list), and not a regular user with a similar name?

### "Slash commands don't show up"

- Wait a couple of minutes after first starting the bot, then press **Ctrl+R** in Discord to refresh.
- Make sure when you invited the bot you ticked **both** the `bot` and `applications.commands` scopes (see [DISCORD-SETUP.md](DISCORD-SETUP.md)). If you only ticked `bot`, kick the bot from the server and re-invite using a fresh invite link.

### "Something else is wrong"

Run:

```
mika doctor
```

It's literally there for this. Whatever it reports as **fail** is your next thing to fix. Run `mika setup` to re-enter any value, then `mika doctor` again. Repeat until it's all green, then `mika run`.

You've got this.
