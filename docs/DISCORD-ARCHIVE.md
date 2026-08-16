# Mika Discord Archive Design

Date: 2026-08-16

## Purpose

Create a local, durable, training-ready archive of every message visible to the MikaV2 bot in the RyokuArch Discord server, including channels, announcement channels, forum posts, public threads, private threads, replies, reactions, stickers, embeds, Discord attachments, and directly linked external resources. After the initial history import, synchronize incrementally every week without rescanning the full history.

The archive is operational data stored under `/srv/mika-discord-archive`; it is not part of the Mika repository.

## Storage layout

- `data/archive.sqlite3`: normalized metadata, source records, cursors, resource provenance, and run reports.
- `data/raw/<guild>/<channel>/<year>/<month>.jsonl.gz`: immutable raw Discord message snapshots.
- `data/media/sha256/<prefix>/<digest>`: content-addressed Discord and external files.
- `data/exports/messages.jsonl.gz`: deterministic normalized training export.
- `data/exports/resources.jsonl.gz`: resource manifest linked to messages.
- `logs/`: scheduler output and verification reports.

Directories and files are root-owned and inaccessible to other Unix users. Downloaded content is never executed.

## Synchronization

The initial run enumerates all visible text and announcement channels, active threads, archived public threads, archived private threads, and forum threads. It paginates each history to the oldest available message.

Each channel or thread has a durable high-water cursor containing its highest completely committed Discord message ID. Incremental runs request only messages after that cursor. They also reconcile the latest 100 archived messages to capture edits without fetching an entire calendar week. New channels and threads are rediscovered on every run. A cursor advances only in the same database transaction that commits the corresponding messages and resource references.

Message IDs, channel IDs, attachment IDs, source URLs, and SHA-256 digests provide idempotency. Interrupted runs can repeat a page without duplicating records.

## Raw and normalized records

Every API message response is preserved as canonical compact JSON in SQLite and appended to a compressed, partitioned raw snapshot stream. The normalized message table stores identity, guild, channel, thread parent, author, timestamps, content, type, reply target, flags, embeds, components, stickers, mentions, reactions, attachment metadata, and raw JSON.

Message content is never altered in the raw layer. Training exports are derived products and can be regenerated. Bot/system messages remain identifiable so later training preparation can filter them explicitly.

## Resource acquisition

Discord attachments, embed media, stickers, and custom emoji URLs are downloaded. External URLs in message content and embed targets are fetched once per canonical URL. The archiver follows normal HTTP redirects but does not recursively crawl links found inside HTML.

Known media landing pages, including Tenor and Giphy, are inspected for Open Graph media targets; those directly referenced media files are downloaded and linked as derived resources. HTML pages are snapshotted. Responses are streamed to temporary files, capped at 512 MiB per resource, hashed while downloading, fsynced, and atomically moved into content-addressed storage. Duplicate bytes are stored once while retaining all message-to-resource relationships.

Network safety rejects localhost, link-local, multicast, unspecified, and private IP destinations after DNS resolution and after every redirect. Only HTTP and HTTPS are accepted. Authentication headers and Discord credentials are never forwarded to external hosts.

## Failures and integrity

Rate limits honor Discord retry durations. Transient HTTP and network failures use bounded retries. Every resource has a state: pending, stored, skipped, or failed, with status, error, byte count, MIME type, digest, and attempt timestamps. Failed resources remain retryable.

Verification performs:

1. Database integrity and foreign-key checks.
2. Reconciliation of stored message totals against a fresh Discord census.
3. Presence, size, and SHA-256 validation of every stored blob.
4. Detection of dangling message-resource links and duplicate logical records.
5. Decompression and JSON parsing of every raw and export stream.
6. A run manifest listing exact successes, failures, skips, and permission gaps.

No run is reported complete if a Discord history endpoint was inaccessible, a raw stream is corrupt, database integrity fails, or a stored blob has the wrong digest. External URLs that are unavailable, unsafe, over the limit, or blocked by their origin are explicitly reported rather than treated as archive corruption.

## Scheduling

Root cron runs the incremental synchronizer every Sunday at 03:15 Europe/Berlin. `flock` prevents overlapping runs. The job discovers topology, ingests only records after each cursor, reconciles the latest 100 records, retries incomplete resources, rebuilds deterministic exports, runs verification, and logs a concise report.

Because polling cannot observe a deletion that happens entirely between weekly runs, archived source records are retained and may not be marked deleted unless a later API response or future real-time event bridge reports it. This limitation does not remove or corrupt already archived training data.

## Acceptance criteria

- All history endpoints visible to Mika return successfully.
- Stored message count matches a fresh Discord census at verification time, allowing only messages created during the measured race window and documenting that delta.
- All Discord attachments are either hash-verified locally or explicitly failed with a retriable reason.
- All discovered external URLs have a terminal stored, skipped, or failed state.
- SQLite, raw streams, exports, and every stored blob pass integrity verification.
- A second incremental run produces no duplicate messages or blobs.
- The weekly cron entry is installed and successfully exercised manually.
