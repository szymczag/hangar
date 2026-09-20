# Recognizing training invitations

How Hangar decides that a block of time in somebody's calendar is a training
they are running, what it reads to decide that, and why it reads it that way
rather than the obvious way.

This document is the reasoning, not only the result. The obvious design was
tried, shipped, and did not work, and the reason it did not work is a property
of how organizations actually keep shared calendars. Somebody will propose the
obvious design again; this is the answer.

> No organization-specific identifiers belong in repository files. Calendar
> addresses, coordinator names and rule contents live in instance data,
> encrypted, and never in documentation, fixtures or tests.

## The question being answered

A workspace wants to know, for each trainer and each period: which trainings did
this person run, when, and what were they called. Three product surfaces need
it — the weekly team ledger, the monthly training report, and importing existing
calendar plans as Workshop work items — and one booking path needs the times so
it does not double-book somebody who is already teaching.

The trainings are planned in a shared calendar the organization already runs.
Hangar does not own that calendar and must not require it to be restructured.

## What a rule is

A **training rule** names one calendar. Every event on it is a training.

That is the whole rule. It is deliberately not "every event on this calendar
organized by this person", which is what it used to be, and the next section is
why.

## The design that did not work, and the two reasons

The first implementation read the rule's calendar and accepted an event when
two things held: `organizer.email` equalled an address stored on the rule, and
the trainer's own verified address appeared in the event's `attendees`.

Both halves fail against a real shared calendar.

### The guest list is hidden, and the API honours that

A shared organizational calendar is normally configured so guests cannot see one
another — in the interface, _"The full guest list has been hidden at the
organizer's request."_ This is not a display setting. Google applies it to the
API as well: `events.list` returns the event without an `attendees` array at
all, to a caller who is not an attendee, and returns only a reduced list to one
who is.

Measured on a real calendar over a two-month window: 188 events, of which **one**
carried a guest list. An identity test built on attendees therefore recognized
one event in a hundred and eighty-eight, and the workspace saw an empty report
with no error anywhere to explain it.

There is no configuration that fixes this while keeping the calendar useful. The
hiding is wanted: a company training calendar lists clients and delegates, and
its owner hides the guest list on purpose.

### The organizer is the calendar, not the person

Google sets `organizer` on an event to the calendar that owns it. For an event
created on a shared calendar, that is the calendar's own address; the person who
created it appears as `creator`, which the previous field mask did not even
request. A rule configured with a coordinator's address can therefore never
match, and a rule configured with the calendar's address is testing that events
on a calendar are on that calendar.

The consequence reaches further than recognition. Anything Hangar itself inserts
into that calendar is organized by the calendar too, so a design where Hangar
writes a training and later recognizes it could never close its own loop while
identity depended on the organizer.

## The design that works

Two reads, each answering the half of the question it can actually answer, and
an intersection.

| Read          | Source                         | Mask asks for                                                 | Answers                                                |
| ------------- | ------------------------------ | ------------------------------------------------------------- | ------------------------------------------------------ |
| Rule calendar | the calendar named by the rule | `iCalUID`, times, `summary`, `status`                         | what trainings exist, when, and what they are called   |
| Own calendar  | each trainer's own `primary`   | `iCalUID`, times, `attendees(email,responseStatus)`, `status` | which of them are this person's, and how they answered |

An event that appears in both is a training belonging to that trainer. Neither
source is sufficient alone, and that is the point: the shared calendar knows
what a training is, and only the trainer's own copy knows whose it is.

### Why the intersection is sound

A copy of an invitation appears in somebody's own calendar only because they
were invited to it. There is no way for an event to be in both the organization's
training calendar and a person's own calendar without that person having been
made a guest. Membership is therefore established without ever reading a guest
list.

The join key is the occurrence key: `HMAC-SHA256(SECRET_KEY, "<iCalUID>:<originalStart>")`.
It is derived from the event's own identity rather than from where it was read,
so the same occurrence read from either calendar produces the same key. Including
the original start distinguishes one instance of a recurrence from another,
rather than collapsing a weekly series into a single training.

This is the same key `GoogleTrainingEventLink` and `TrainingEventOccurrence` have
always used, so linking an invitation to a session, and everything built on that,
is unchanged.

### Statuses

The trainer's own attendee entry carries their answer.

| Answer                     | Result         | Why                                                                                                                                                                                        |
| -------------------------- | -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `accepted`                 | confirmed      | —                                                                                                                                                                                          |
| `needsAction`, `tentative` | pending        | A training nobody has answered yet is still a training somebody is expected at, and it still blocks the time.                                                                              |
| `declined`                 | not recognized | An explicit refusal.                                                                                                                                                                       |
| unreadable                 | pending        | Where even a trainer's own copy omits the guest list, silence is not a refusal. The event is on the training calendar and in their calendar; counting it as pending is the honest reading. |

### Privacy boundary

The masks are the mechanism, not a filter applied afterwards. A field that is
not requested is not sent, which is a stronger statement than discarding it.

- **Titles are requested from the rule's calendar only.** That is safe precisely
  because of which calendar it is: every event on it is a training, so every
  title on it is a training title. The same mask pointed at a personal calendar
  would be reading somebody's private life.
- **The trainer's own calendar is read with no `summary` and no `description`.**
  Titles of their private meetings are never sent to Hangar at all. The read
  establishes identity and nothing else.
- Titles are stored encrypted with the calendar key material, truncated, and are
  shown only to a workspace administrator or to the trainer whose invitation it
  is.
- Nothing from either read is logged. The sweep logs error codes and counters.

The OAuth scope is unchanged — `calendar.events.readonly`, which a trainer grants
explicitly and separately from basic availability. What changed is which calendar
is read with it, so the consent text says so and trainers see the revised wording.

### What is no longer required

Trainers do **not** need permission to see the details of the shared training
calendar. Free/busy access to it is enough for their own trainings to be
recognized, because the details Hangar needs about _their_ training come from
their own copy. A trainer reading the whole organization's training schedule is
no longer a precondition for being counted, which is a smaller ask than the
previous design made.

## Where this runs

### Live path

`training_events()` serves the weekly ledger and the booking checks, reading
Google on every request. It reads the rule calendar once per workspace per
window — cached for five minutes and keyed on the rules and the window, never on
a viewer, because every trainer would otherwise read an identical list — and each
trainer's own calendar per request, then intersects.

Whether a given viewer may _see_ a title is decided later, where the viewer is
known: a workspace administrator, or the trainer themselves.

### Sweep

`sweep_rule()` records recognized trainings into `TrainingEventOccurrence` so
that the monthly report and the calendar import can answer without calling
Google. It reads the rule's calendar once, in month slices, then each consenting
trainer's own calendar over the same slices, and writes the intersection.

Consent is enforced twice over: a trainer with no credential, no granted scope
or the feature switched off is not read at all, and a trainer who was not invited
has no copy to find.

Windowing, incremental passes, what a pass may conclude about disappearance, and
leasing are unchanged and documented in `capacity-planner.md`.

## Failure states and what they look like

The failure that cost the most time was invisible, so each of these now has
wording somebody can act on.

| State                                        | Where it shows                                               | What it means                                                                                    |
| -------------------------------------------- | ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| Trainer has not granted training recognition | My capacity, prominently; team ledger and report per trainer | Their trainings are not counted and nobody else can turn it on for them. This is the common one. |
| Trainer has not connected Google             | team ledger, report                                          | No credential at all.                                                                            |
| Credential needs reauthorization             | team ledger, report                                          | Refresh token rejected.                                                                          |
| Provider error                               | team ledger                                                  | The error code is now shown rather than swallowed into "Availability unknown".                   |
| No rule configured                           | report, import                                               | No calendar has been named as a training calendar.                                               |

A trainer excluded for any of these reasons is reported as excluded and counted
in the exclusions — never as a trainer who ran no training. The distinction is
the whole point: a zero that means "no trainings" and a zero that means "we could
not look" must not render identically.

## Diagnosing a workspace that recognizes nothing

Run from any container built on the API image. In order, because each step
narrows the next.

**1. Is a rule configured, and is its calendar readable?**

```python
from urllib.parse import quote, urlencode
from plane.ext.capacity.calculation import _google_client
from plane.ext.capacity.crypto import decrypt_value
from plane.ext.models import GoogleTrainingRule, TrainerProfile

rule = GoogleTrainingRule.objects.first()
print("rules:", GoogleTrainingRule.objects.count())
calendar = decrypt_value(rule.encrypted_calendar_id, rule.encryption_key_id)
profile = TrainerProfile.objects.filter(calendar_selection__isnull=False).first()
credential = profile.calendar_selection.credential
query = urlencode({"timeMin": "...", "timeMax": "...", "singleEvents": "true", "maxResults": 250})
items = _google_client()._authorized_json(
    credential, "GET",
    f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar, safe='')}/events?{query}",
).get("items", [])
print("events:", len(items), "titled:", sum(1 for i in items if i.get("summary")))
```

Zero events means the reading account cannot see the calendar. Events with no
titles mean the reading account granted only free/busy scope — which is fine for
the rule calendar's half of the work but means this particular account cannot be
the one that fetches titles.

**2. Who has consented?**

```python
from plane.ext.capacity.training_sync import consenting_trainers
print(len(consenting_trainers(rule.workspace_id)))
```

Zero is the common answer and explains an empty report entirely.

**3. Does the intersection produce anything?**

```python
from plane.ext.capacity.training_sync import sweep_rule
print(sweep_rule(_google_client(), rule, full=True))
```

`readers: 0` sends you back to step 2. `readers > 0, matched: 0` means the
trainers who consented hold no copies of anything on that calendar in the
window — they are not invited to these trainings, or the trainings are further
ahead than `GOOGLE_TRAINING_SWEEP_WINDOW_FUTURE_DAYS`.

## Retained and unused

`GoogleTrainingRule.encrypted_organizer` is written empty and read by nothing. It
is kept so that a downgrade to a release that still reads it finds a column
rather than an error, and is dropped in a later migration once no supported
release reads it.
