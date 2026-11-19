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
browser archive import, automatic synchronization or meeting execution.

## Offline inspection and comparison

```sh
python agents/ai_meeting_archive.py saved-meeting.json
python agents/ai_meeting_archive.py earlier.json later.json
python agents/ai_meeting_archive.py earlier.json later.json --format html
```

All commands read local files only. The default prints JSON to stdout;
`--format html` prints a standalone Korean report with metadata and change tables.
It contains no JavaScript or remote assets, escapes archive text and works for
one-record inspection or two-record comparison. Save the stdout HTML to a new
report file (never redirect into an input archive), then open it in a browser.
This CLI does not itself write a report file or add dashboard controls.
Inspection reports
record metadata and verdict counts. Comparison reports left/right provenance,
market-source compatibility, final verdict changes and separate verdict, summary
and concern changes for each M01–M07 statement. Left and right follow argument
order; changes do not imply an improvement in accuracy or profitability. Unknown
market sources remain `UNKNOWN`, rather than being assumed equivalent.

Comparison also reports model changes and independent source/completion time
relations. `RIGHT_LATER`, `RIGHT_EARLIER` or `SAME_TIME` describes the recorded UTC
times; `right_minus_left_seconds` is signed and negative when the right timestamp
is earlier. Input files are never automatically reordered. A later completion
can use earlier source data, so the HTML report shows both time relations. These
timestamps do not establish authenticity, synchronized clocks or data quality.

`comparison_context` collects recorded condition differences in stable order:
unknown/different market source, different model, different execution mode,
different source timestamp and earlier completion on the right. The HTML report
shows their Korean descriptions before the metadata tables. An empty list means
none of these conditions differs; it does not verify identical inputs, provider
execution, comparability or quality. This summary is not a confidence score.

`change_summary` lists changed statement IDs in M01–M07 order and counts distinct
changed statements plus verdict/summary/concern changes. A statement changed in
multiple ways counts once in `changed_statement_count` but in each applicable
type count. Metadata-only changes do not invent statement changes. The HTML
report shows a changed-statements summary before the existing complete seven-row
table, and explicitly reports when no statements changed. This is a navigation
aid, not an accuracy or quality score; original prose is still omitted.

`verdict_transitions` contains all nine left/right verdict pairs, their counts
and ordered statement IDs, including unchanged verdicts. Counts sum to seven.
`verdict_count_delta` is right minus left for each verdict; its total is zero.
The HTML transition table uses left verdicts as rows and right verdicts as
columns, with a separate list of changed-verdict IDs. It does not rank transitions
as improvements or treat fewer review/data-gap labels as verified better results.

Historical archives do not expire for comparison. Structure, UTC time ordering,
seven role/phase identities, counts, field allowlists and no-order flags must
still match the archive schema. Duplicate JSON keys, oversized files (over
256 KiB) and malformed records are rejected with a fixed CLI error. These checks
verify format consistency, not authenticity or correctness of model statements.
The commands do not print statement prose or modify input files.

Downloads require a currently usable record. Loading, errors, offline state,
expiry or clock rollback disable saving. Once downloaded, the file is a dated
historical record; its existence does not verify a running process or authorize
orders. Browser download support, including on real iPhone Safari, must be
checked on the target device.
