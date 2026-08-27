# Airport Friction Seed v0.1 — runbook

## What the user must do

1. Wait until the already-submitted KAC applications show as usable in the Public Data Portal. The Seed uses six; the Gimpo cell-level service is reserved for the future app.
2. Join KMA API Hub as a general member. The account and authentication key are issued automatically; on the aviation-weather page, only confirm that the `API 활용신청` actions for domestic METAR/SPECI and airport warning are active/completed.
3. Add two GitHub Repository Secrets:
   - `DATA_GO_KR_SERVICE_KEY`
   - `KMA_API_HUB_KEY`
4. Run the **Collect Airport Friction seed** workflow once with `mode=live`.

That is the entire live-data setup. The code, namespace, cadence, retries, dedupe, manifests, health checks, and commits are already configured.

The local project `.env` currently contains only the name `SEOUL_OPEN_DATA_KEY`; no KAC or KMA credential was found. GitHub does not expose secret values and this environment has no authenticated secret-listing client, so repository-side existence could not be independently confirmed. Do not reuse the Seoul key: KAC uses a Public Data Portal key and KMA uses an API Hub key.

## Offline verification before keys

The fixture path never calls the network and never writes fake data unless explicitly selected:

```bash
export PYTHONPATH="$PWD/src"
python3 -m public_data_alpha_engine.cli collect-airport \
  --output /tmp/airport-friction-fixture \
  --fixture \
  --force-weather \
  --trigger-source fixture_smoke
```

The workflow has the same explicit `mode=fixture` option. Scheduled runs and no-input external dispatches default to `live`, so fixtures cannot silently enter the production time series.

## External 15-minute dispatcher

Call GitHub's workflow-dispatch API for `.github/workflows/collect-airport-friction.yml` on `main`, passing:

```json
{
  "ref": "main",
  "inputs": {
    "mode": "live",
    "trigger_source": "external",
    "force_weather": "false"
  }
}
```

This is the same no-server external-trigger pattern as the Seoul transition: the scheduler stores only a GitHub token and dispatches the repository workflow; API credentials remain GitHub Repository Secrets.

GitHub's internal 15-minute `schedule` is retained temporarily because the external scheduler has not yet been verified. It is a safety net, not the long-term clock. During overlap, raw payload dedupe prevents duplicate raw storage and `trigger_source` identifies both runs. After seven consecutive days of external triggers with no unexplained schedule gaps, delete the `schedule` block to avoid redundant manifests.

The Airport and Seoul workflows share one data-branch writer lock. If another writer still advances `data` between checkout and push, the workflow rebases its namespace-only commit on the latest branch and retries up to four times. A provider failure manifest is therefore preserved even when both Seeds finish together.

The normal single-clock load is 1,824 calls/day. During this short overlap, the conservative maximum is 3,360/day because KAC can run twice while KMA remains protected by its shared 30-minute state. This still fits every published quota; the exact proof is embedded in `airport-quota` output and every run manifest.

## Health and failure behavior

- Network retries: two, with bounded exponential delay.
- One API failure: other sources are saved; manifest status is `PARTIAL`; strict workflow exits red after committing the diagnostic manifest.
- All live sources fail or keys are absent: a redacted `FAILED` manifest/state is committed; no secret is printed.
- Scheduler gap: warning after 2.5 × 15 minutes, with estimated missed intervals.
- Source gap: checked against 2.5 × that source's own cadence.
- Storage review: state changes to `MIGRATION_REVIEW` at 500 MB of cumulative newly stored gzip payloads.

## Cost and storage expectation

- KAC APIs: ₩0.
- KMA API Hub: ₩0.
- Database/server/domain/app: none.
- GitHub Actions: ₩0 while this repository remains public and uses a standard runner.
- Expected monthly cash cost: ₩0.

The checked-in contract fixture is not a realistic volume estimate. Live flight and schedule responses dominate. The initial planning range is roughly 0.3–1.2 GB over 90 days, with actual size reported by the first seven live days. Gimpo cell-level parking is excluded from archival storage. The code raises a migration review at 500 MB because GitHub recommends keeping repositories ideally below 1 GB. If reached, stop adding new raw bundles to Git before moving subsequent raw blobs to a zero-cost/free-tier object store; keep manifests, hashes, provenance, and normalized records on the data branch.

## Commands

```bash
export PYTHONPATH="$PWD/src"
python3 -m unittest discover -s tests -v
python3 -m public_data_alpha_engine.cli airport-quota
scripts/run_airport_friction.sh /absolute/path/to/data-branch-checkout
```
