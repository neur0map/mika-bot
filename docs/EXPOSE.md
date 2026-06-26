# Opening the dashboard to the internet

The dashboard (`mika web`) runs on `http://127.0.0.1:8080` - only your own machine
can reach it. To open it elsewhere (your phone, a teammate), use one of these. Both
are free and far safer than forwarding a port on your router.

## Option A - Tailscale (easiest, private)

Tailscale puts your devices on a private network. Nobody else can reach the dashboard.

1. Install Tailscale on the server and on your phone/laptop: https://tailscale.com/download
2. Sign in with the same account on both (`tailscale up`).
3. Find the server's Tailscale address: `tailscale ip -4` (looks like `100.x.y.z`).
4. Start the dashboard bound to all interfaces: set `MIKA_WEB_HOST=0.0.0.0` in `.env`, then `mika web`.
5. On your other device, open `http://100.x.y.z:8080`.

Only devices on your Tailscale network can connect. This is the recommended option.

## Option B - Cloudflare Tunnel (public URL, no open ports)

Gives you a public `https://` link without exposing your IP or opening firewall ports.

1. Install cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
2. Run the bot's dashboard: `mika web` (leave it on the default `127.0.0.1:8080`).
3. In another terminal: `cloudflared tunnel --url http://127.0.0.1:8080`
4. cloudflared prints a `https://<random>.trycloudflare.com` URL - open it anywhere.

For a permanent named URL, create a named tunnel and route a domain (see Cloudflare's
docs). The quick command above is perfect for occasional access.

> **Security:** the dashboard is read-only, but it still shows your configuration. Don't
> share the link publicly. Tailscale (Option A) keeps it private to your own devices.

## Plain port forwarding (not recommended)

You *can* forward port 8080 on your router to the server, but that exposes the page to
the whole internet and reveals your home IP. Prefer Tailscale or a Cloudflare Tunnel.
