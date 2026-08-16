# conversation/media

Provider-neutral preparation of incoming visual media. Animated images are fetched with strict
limits and converted into a few chronological still frames so vision models can read motion and
punchlines instead of seeing an arbitrary first frame.

Discord normalization belongs in `mika.discord.ingress`; provider byte transport belongs in the
provider adapters.
