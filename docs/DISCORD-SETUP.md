# Discord Setup — Getting Your Bot's Credentials

This guide walks you through the Discord side of setting up Mika: creating the bot, getting the secret token, turning on the one permission Mika needs to read messages, and inviting the bot to your server. There are no screenshots, but every click is spelled out.

You only have to do this **once**, and the whole thing takes about 5 minutes. When you're done, you'll have three values that the Mika setup wizard ([GETTING-STARTED.md](GETTING-STARTED.md), Step 3) will ask you for.

> **A note on terminology.** Discord uses a few words you may not have seen before. We'll define each one the first time it appears:
> - **Application** — the entry on Discord's developer site that represents your bot.
> - **Bot user** — the account inside an application that actually shows up in servers.
> - **Token** — a long secret string that lets your code log in *as* the bot. Treat it like a password.
> - **Intent** — a permission you tick on the developer site that lets your bot receive certain kinds of events (like message text).
> - **Scope** — what your bot is allowed to do when you invite it (e.g. join servers, register slash commands).
> - **Permission** — what your bot is allowed to do *inside* a server once it's there (send messages, embed links, etc.).

---

## Step 1 — Create the application

1. In a web browser, go to **https://discord.com/developers/applications**.
2. Log in with your normal Discord account if it asks.
3. In the top-right, click the blue **New Application** button.
4. Give it a name (this is just for you — you can rename it later). Tick the "I agree" checkbox and click **Create**.

You'll land on the application's main page. Leave this tab open; we'll use it for every other step.

---

## Step 2 — Get the bot token (and keep it secret)

1. In the left sidebar of your application page, click **Bot**.
2. Look for the **Token** section near the top. Click the **Reset Token** button.
   - Discord doesn't show you the token until you reset it, even on a brand new bot. This is normal.
3. If it asks you to confirm (or to enter a 2FA code), do that. A long string will appear.
4. Click **Copy**. This long string is your **`DISCORD_TOKEN`** — write it down somewhere safe for the next minute (a temporary note, a password manager, etc.).

> **Important — keep this token secret.**
> - Anyone with this token can control your bot completely. Never paste it into a public chat, a screenshot, a GitHub repo, or a support forum.
> - If you ever think it leaked (or you accidentally share it), come back to this page and click **Reset Token** again. The old one stops working immediately, and you can paste the new one into Mika with `mika setup`.

---

## Step 3 — Turn on the Message Content Intent

By default, Discord bots can see *that* a message was sent, but **not what it says**. For an AI chat bot, that's obviously a problem — Mika needs to read messages so it can reply to them. You fix this with one toggle.

1. You should still be on the **Bot** tab from Step 2. If not, click **Bot** in the left sidebar.
2. Scroll down to the section titled **Privileged Gateway Intents**.
3. Find the toggle labelled **MESSAGE CONTENT INTENT** and turn it **on** (it'll go blue/green).
4. Scroll to the bottom and click **Save Changes** if a save bar appears.

That's it. You don't need to touch the other two intents (*Presence* and *Server Members*) for basic Mika functionality.

---

## Step 4 — Get the Application ID

This is much easier than the token — it's not secret and Discord shows it to you right on the page.

1. In the left sidebar, click **General Information**.
2. Look for **Application ID** (it's a long number).
3. Click **Copy**. This is your **`DISCORD_CLIENT_ID`**. Save it next to your token.

---

## Step 5 — Build the invite link

This is the link you'll click to actually put your bot into a server. Discord has a builder that creates the link for you based on what you tick.

1. In the left sidebar, click **OAuth2**.
2. Click **URL Generator** (it might be a sub-item under OAuth2, or visible directly — depends on which version of the portal you see).
3. Under **Scopes**, tick **both** of these boxes:
   - **`bot`** — lets your application join servers as a bot user.
   - **`applications.commands`** — lets your bot register slash commands like `/help` and `/dice`.
   - Do **not** tick anything else. (Skipping `applications.commands` is the #1 reason slash commands don't appear later.)
4. A new section called **Bot Permissions** will appear below the scopes. Tick exactly these:
   - **View Channels** — so the bot can see channels at all.
   - **Send Messages** — so it can reply.
   - **Read Message History** — so it has context when you mention it in the middle of a conversation.
   - **Embed Links** — so its replies can include nice formatted previews.
   - **Attach Files** — so commands like `/cat` and `/dog` can post pictures.
   - **Add Reactions** — so it can react with emoji when appropriate.
   - You can leave everything else unchecked.
5. Scroll to the very bottom of the page. You'll see a long **Generated URL** with a **Copy** button next to it. Click **Copy**.

---

## Step 6 — Invite the bot to your server

1. Open a new browser tab and **paste the URL** you just copied. Press **Enter**.
2. Discord will show an "Add to Server" page. Pick your server from the dropdown.
   - The dropdown only shows servers where you have *Manage Server* permission. If yours isn't there, you either don't own a server yet (create one in Discord first) or you're logged into the wrong Discord account.
3. Review the permissions list (it should match what you ticked in Step 5) and click **Authorize**.
4. Complete the captcha if it asks.

Switch over to Discord — your bot should now appear in the server's member list. It'll have a grey dot (offline) until you actually start Mika with `mika run`. That's normal.

---

## Step 7 — Turn on Developer Mode and copy your Server / Channel IDs

The Mika wizard will optionally ask you for your **Server ID** and one or more **Channel IDs**. These are long numbers that let Mika know which server to register slash commands in (so they appear instantly instead of after an hour) and which channels are "free-chat" channels where it replies without being mentioned.

To copy these IDs, you first need to turn on **Developer Mode** in your Discord app — it just unlocks a "Copy ID" right-click option.

1. Open the **Discord app** (desktop or web).
2. Click the **gear icon** next to your username in the bottom-left (that's User Settings).
3. In the left sidebar, scroll down to **Advanced** (under "App Settings").
4. Turn on the **Developer Mode** toggle.
5. Close the settings (top-right **X** or **Esc**).

Now you can copy IDs:

- **Server ID** — In Discord, find your server icon in the far-left sidebar. **Right-click** it and choose **Copy Server ID**. This is your **`DISCORD_GUILD_IDS`**.
- **Channel ID** (optional) — In any channel where you want Mika to chat freely (without being @mentioned), **right-click the channel name** and choose **Copy Channel ID**. This is what goes into **`DISCORD_RESPONSE_CHANNEL_IDS`**. You can list more than one — the wizard will explain how.

If "Copy ID" doesn't appear in the right-click menu, Developer Mode isn't on yet. Go back to step 4 above.

**Still no "Copy Server ID"? Use the no-Developer-Mode fallback.** Open Discord in
a web browser (or read your desktop window's address bar), click into your server,
and look at the URL:

```
discord.com/channels/1234567890/9876543210
                     ^Server ID   ^Channel ID
```

The **first** number after `/channels/` is your **Server ID**; the **second** is a
**Channel ID**. Two reminders: right-click the **server itself** (its icon or its
name at the top), not a channel or empty space — and the Developer Mode toggle is
under **Advanced**, not Appearance.

---

## Summary — what each value is for

When the Mika setup wizard asks for these, here's where each one goes in the `.env` file (the wizard writes this for you — you don't have to touch the file):

| What you copied                        | Goes into this setting                | Required? |
|----------------------------------------|---------------------------------------|-----------|
| Bot token (Step 2)                     | `DISCORD_TOKEN`                       | Yes       |
| Application ID (Step 4)                | `DISCORD_CLIENT_ID`                   | Yes       |
| Server ID (Step 7)                     | `DISCORD_GUILD_IDS`                   | Recommended (faster slash-command updates) |
| Channel ID(s) for free-chat (Step 7)   | `DISCORD_RESPONSE_CHANNEL_IDS`        | Optional  |
| The name you want the bot called       | `MIKA_PERSONA_NAME`                   | Yes       |
| Your OpenRouter (or other LLM) key     | `MIKA_LLM_API_KEY`                    | Yes       |

You're done with the Discord side. Head back to **[GETTING-STARTED.md](GETTING-STARTED.md)** and continue from **Step 3 — The setup wizard**. Paste these values when it asks for them, and the rest is automatic.
