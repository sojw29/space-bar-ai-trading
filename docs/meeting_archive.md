# Saved meeting records

Open a validated completed meeting and choose **전체 회의 TXT 저장** for reading
or **전체 회의 JSON 저장** for structured comparison. Both save all seven
statements regardless of active filters. Saving is a browser download initiated
by the user, with no model calls, uploads or changes to server files.

The JSON wrapper uses `SPACEBAR_MEETING_ARCHIVE_1`. It contains the browser's
`archived_at_utc`, fixed research/no-order flags, and an allowlisted `record`:

- Execution mode and inference label; optional execution ID and market source
  (`null` when absent from the source).
- Model, source/start/completion UTC times and final verdict.
- Full verdict counts and seven statements with M01–M07 IDs, agent, phase,
  verdict, summary and concerns.

Extra response fields are excluded. The archive preserves the validated display
record; it is not a signed attestation that inference occurred. Its save time is
not the source data time. It has a distinct archive version and cannot be used
directly as a live meeting API response. This release adds export only, not
archive import, automatic synchronization or meeting execution.

Downloads require a currently usable record. Loading, errors, offline state,
expiry or clock rollback disable saving. Once downloaded, the file is a dated
historical record; its existence does not verify a running process or authorize
orders. Browser download support, including on real iPhone Safari, must be
checked on the target device.
