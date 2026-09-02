## Security and privacy

**A copied work item never carries another member's private work, and only an
administrator can start one.** Duplicating a project can now include its work
items, with their sub-item tree. It is off by default, like every option that
carries somebody else's work, and it inherits the existing rule that only an
administrator of the source may duplicate it at all. Drafts are never copied: a
draft is one author's unsaved composition, hidden from everyone else.

**Assignees who are not members of the copy are dropped, and the number is
reported.** Copying an assignment would name somebody on work in a project they
have not been added to. The same rule already governs private views and departed
members; the count appears in the copy's summary so the omission is visible
rather than silent.

**Relations are copied only where both ends are inside the copy.** A relation
carries two plain references to work items with nothing scoping them to a
project. Copying a one-sided relation would attach the copy's items to the
source's -- and would start showing the source's members relations into a
project they have never heard of. Only relations wholly inside the copy travel;
the rest are dropped and counted.

**Images inside a copied work item are copied too, and authorised against the
person who asked for the copy.** A work item embeds each inline image as an
asset identifier, so copying the text alone would leave every image pointing at
the source project -- unreadable for anyone in the copy who is not also in the
source, and broken outright once the source is deleted. Each image is now
duplicated into the copy, and each one is resolved through the same check that
governs reading it directly: an image the initiator could not read is not copied.
An image that cannot be copied is removed from the description rather than left
pointing at the source, because a reference nobody outside the source can load
reads as a broken copy rather than an incomplete one.

**A copy that is interrupted resumes rather than duplicating.** Work item numbers
are carried across from the source, which makes them a durable key between the
two projects, and every stage of the copy skips what it has already written. A
worker that dies mid-copy is redispatched and adds only the remainder. Before
this release the later stages re-ran from the beginning, which either raised on a
uniqueness constraint or silently created a second copy of labels and links.

**One work item copy per workspace at a time.** The existing limits bound a
single copy; this bounds how many can be queued at once, so one person cannot
occupy a worker with several large copies. A copy of more than 20,000 work items
is refused outright.

## Migrations and compatibility

One additive migration, `ext.0020`, creates the table that tracks a copy in
progress. No existing table is altered and no data is rewritten, so an older
application version runs against this schema unchanged and simply does not read
it.

Work items are copied by a background job on the default queue, which every
deployment already runs; no new worker or queue is required. A scheduled sweep
every five minutes redispatches copies whose worker died and copies the broker
never delivered.

Copying work items requires object storage to be writable, because each image is
duplicated into it. There is no per-workspace storage limit in Hangar, so a copy
of a project with many images increases storage use by roughly the size of those
images; the number of images one copy will duplicate is capped.

Deploy the web and API images together. Rolling back needs no schema reversal.

## Known limitations and rollback

The work item copy carries a project's structure, not its discussion. Comments,
reactions, subscribers, activity history, attachments and worklogs are not
copied, and each is named in the copy's summary so the omission is recorded
rather than assumed.

Copying a project's work items has been verified end to end against real object
storage, including that a member of the copy who is not a member of the source
can read the copied images while still not being able to read the source's. What
has not been checked is how any of it looks: the progress strip shown while a
copy runs, and the interface surfaces introduced in `rc.41` -- the maintenance
bar, the build identity dialog and the workspace home-defaults page -- have not
been viewed in a browser.

A copy whose work items are still arriving shows a progress strip on the project;
there is no estimate of how long it will take.

To roll back, redeploy the previous image and leave the new table in place. Work
items already copied are ordinary work items and continue to work.
