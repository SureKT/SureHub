# Privacy Policy — SureHub

SureHub is a personal, self-hosted application used by a single person (its author).
It is not offered to the public and has no other users.

## Google user data

SureHub requests the `https://www.googleapis.com/auth/calendar.events` scope only to:

- read events from the owner's own calendar, to avoid scheduling over existing events;
- create (and, on explicit request, delete) events that the owner has approved.

The OAuth token is stored only in the owner's private, self-hosted database.
Calendar data is processed only to produce the owner's own schedule. It is never sold,
shared with third parties, or used for advertising.

Event text may be sent to a large language model API (Anthropic) to draft schedule
proposals for the owner. Nothing is written to the calendar without the owner's
explicit approval.

## Retention and revocation

Data stays on the owner's server. Access can be revoked at any time from
<https://myaccount.google.com/permissions>, and the stored token deleted from the database.

## Contact

Open an issue at <https://github.com/SureKT/SureHub/issues>.
