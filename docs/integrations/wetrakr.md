# WeTrakr outbound sync

Floppy can send what you watch, what you plan or drop, and your ratings to
[WeTrakr](https://api.wetrakr.com/). It is one provider on the shared outbound
engine described in [watched-state-sync](../architecture/watched-state-sync.md);
this page covers only what is specific to WeTrakr.

The runnable half is `src/integrations/tests/test_wetrakr.py`. If this page and
that file disagree, the file is right.

```bash
SECRET=test-only scripts/test.sh integrations.tests.test_wetrakr
```

## Verification status

**Not yet verified against a live WeTrakr account.** Every request and reply
shape in `wetrakr_api.py` and `state/adapters/wetrakr.py` comes from an
unofficial transcription of WeTrakr's documentation (2026-10-01), and the tests
run against a mocked WeTrakr. Do not call this integration complete until a
WeTrakr application key and a consenting test account have confirmed:

- the device-login field name (`code` or `device_code`; Floppy tries both);
- the exact reply buckets (`added`, `notFound`, `errored`) and `play_id`;
- the rate-limit and quota headers;
- that an unrecognised reply is retried rather than lost (it is).

## Connecting

1. Get an application key from WeTrakr and set `WETRAKR_CLIENT_ID`, or paste it
   under Settings > Metadata. Floppy ships no shared key.
2. Integrations > WeTrakr > Connect. Floppy shows a code; approve it on
   wetrakr.com. Floppy stores the tokens encrypted and refreshes them under a
   lock, because WeTrakr rotates refresh tokens.
3. Connecting sends nothing. Plays, statuses and ratings each have a switch,
   all off.

## What is sent

| Switch | Sent | Never sent |
|---|---|---|
| Plays | A movie or episode you finish, with the date you watched it | Imported history, undated plays, a whole show as watched |
| Statuses | Planning and dropped for movies; planning, paused and dropped for shows | Watching and completed (a play already says so) |
| Ratings | Movie and show ratings, including clearing one | Episode ratings |

Deliveries are Live (within seconds), Hourly or Daily. Hourly and Daily use UTC
boundaries.

## Send existing library

Plays are WeTrakr's activity feed, so imported history never reaches it by
itself. **Send existing library** queues your dated plays, plans, drops and
ratings once, only when you press it. Re-running it never sends the same dated
play twice. Plays without a date are counted on the card and left out, because
WeTrakr would show them as watched today.

## Known limits

- Un-tracking in Floppy does not remove anything from WeTrakr yet.
- Play receipts (`play_id`) are stored on each delivery for the removal work.
- Floppy never calls WeTrakr's remove-all endpoints.
