# Plan: CSV export of invoices

<!-- An example of what /write-plan produces, for a fictional TypeScript web API. Shortened: a real plan
     has full line ranges, every stage's fields and the board values of UI stages. -->

- **Base:** origin/main @ 3f2a9c1
- **Milestone:** single

## Goal
Accountants can download the invoices of a date range as a CSV file from the invoices page and through `GET /api/invoices/export`. Amounts match the invoice PDFs to the cent, and the file opens in Excel without an import dialog.

## Non-goals
- Other formats (XLSX, PDF bundles).
- Scheduled or emailed exports.

## Architecture
The API route streams rows from the existing invoice query through a new CSV writer; the page adds a button that calls the route. No new tables.
- **Layer:** CSV writing in `packages/core` (pure, no I/O); the route in `apps/api`; the button in `apps/web`. The web app never formats CSV itself (D1).
- **New and changed types:** `CsvWriter` (core): turns rows into RFC 4180 lines. `exportInvoices` (api): query + stream. See *Contracts*.
- **Entry points:** `GET /api/invoices/export?from=&to=`; a button on the invoices page. Older clients are not affected.
- **Data and state:** none stored.
- **Errors:** invalid range → 400 with the existing error shape; more than 50,000 rows → 413 (D3). One unreadable invoice is skipped and counted in the `X-Skipped` header, never aborting the file.
- **Concurrency and lifetime:** streamed; the request's abort signal cancels the query.
- **Security and privacy:** same permission as the invoices page (`invoices:read`); customer names never reach logs.
- **Reuse:** `listInvoices` at `apps/api/src/invoices/query.ts:40-88` (extend with a cursor); `formatMoney` at `packages/core/src/money.ts:12` (reuse).
- **Shipping:** no new dependencies.

## Decisions

### D1 CSV is written in core, not in the web app
One writer for API and future jobs; the web app only downloads. (source: codebase: all formatting lives in core)

### D2 Excel-friendly: UTF-8 with BOM, comma, CRLF
Excel opens a BOM-marked UTF-8 file directly; without the BOM, umlauts break. (source: measured, see *Measured facts*)

### D3 At most 50,000 rows per export
The owner's largest customer has 31,000 invoices a year; above the limit the user narrows the range. (source: owner 2026-11-20)

## Open decisions

### O1 Cursor or offset paging for the stream
Decided by S2; criteria: query time for 50,000 rows on the seed database under 2 s; if the offset is fast enough, keep the existing offset; otherwise add a cursor on `(issued_at, id)`.

## Measured facts
- Excel 365 (Windows): a UTF-8 file with BOM and CRLF opens with correct umlauts and no import dialog; without the BOM it shows mojibake. Measured with a 3-row probe file, deleted afterwards.

## Contracts

```ts
// packages/core/src/csv.ts
export function csvLine(fields: readonly (string | number | null)[]): string; // RFC 4180 quoting, ends with "\r\n"; null → empty field
export const CSV_BOM = "﻿";
```

## Conventions to follow
- Route handlers validate with zod schemas: see `apps/api/src/invoices/routes.ts:15`

## Verification (whole feature)
- `bash scripts/gate.sh` (the final reviewer runs it)

## Parallel groups
none (S2 builds on S1's writer, S3 on S2's route)

## Stages

### S1: CSV writer
- **Depends on:** none
- **Model:** sonnet
- **Review:** full
- **Goal:** `csvLine` and `CSV_BOM` in core, per the contract.
- **Decisions used:** D1, D2 | **Open decision owned:** none
- **Files owned:** `packages/core/src/csv.ts` (new), `packages/core/src/index.ts` (change), `packages/core/test/csv.test.ts` (new)
- **Read first:** `packages/core/src/money.ts:1-30` (module and export style)
- **Facts:** none
- **Steps:** 1. Write the table test. 2. Implement. 3. Export from the index.
- **Edge cases:** quotes inside a field, a line break inside a field, leading `=` (written as is; formula injection is handled in S2 by prefixing `'`), null.
- **Tests (pin these, before the code):**
  - `csvLine` table: `["a","b"]` → `a,b\r\n`; `['say "hi"']` → `"say ""hi"""\r\n`; `["x\ny"]` → `"x\ny"\r\n`; `[null, 3]` → `,3\r\n` (source: table, RFC 4180)
- **Same piece of work:** none
- **UI check:** none
- **Owner check:** none
- **Acceptance criteria:**
  - [ ] the contract's signatures, exported from `packages/core`
- **Verify:** `pnpm --filter core test -- -t "csvLine" 2>&1 | tail -5`

### S2: Export route
- **Depends on:** S1
- **Model:** opus
- **Review:** full
- **Goal:** `GET /api/invoices/export` streams the CSV with D2's encoding, D3's limit and the skipped-row header.
- **Decisions used:** D2, D3 | **Open decision owned:** O1
- **Files owned:** `apps/api/src/invoices/export.ts` (new), `apps/api/src/invoices/routes.ts` (change), `apps/api/src/invoices/query.ts` (change, if O1 → cursor), `apps/api/test/export.test.ts` (new)
- **Read first:** `apps/api/src/invoices/query.ts:40-88`, `apps/api/src/invoices/routes.ts:1-60`
- **Steps:** …
- **Tests (pin these, before the code):**
  - `export rejects more than 50,000 rows`: seed 50,001 invoices → 413 (source: D3)
  - `amounts match the PDF`: the seed's 3 reference invoices → `12.30`, `0.07`, `1000.00` (source: user-facing promise, the PDFs in `fixtures/invoices/`)
- **Same piece of work:** API docs `docs/api/invoices.md` *Export* (add)
- **Owner check:** none
- **Verify:** `pnpm --filter api test -- -t "export" 2>&1 | tail -5`

### S3: Export button
- **Depends on:** S2
- **Model:** sonnet
- **Review:** full
- **UI check:** `pnpm --filter web storybook:capture InvoicesPage` and compare with: button "Export CSV" right of the date filter, 8 px gap, secondary style; disabled while the range is invalid.
- **Owner check:** open the invoices page, export last month, open the file in Excel: umlauts correct, no import dialog (confirms D2).
- …

## Risks / open questions
- none

## Execution log
<filled in by the orchestrator>
