# Virtual Stage v2.4 — dry-run commissioning build

Based on v2.3. Python 3.6 / PyTango 9.2.2 target.

## Changes
- Per-device expert RW `dryRun`, **True on every server/device restart**.
- Read-only `lastMoveReport` and `lastMoveValid` attributes.
- `position` continues reading physical motor positions; simulated targets are only in the report.
- A simulated move reads actual positions and software limits, calculates SN/ST/SZ targets, checks user and real limits, and never sends a motor position write.
- Dry-run `STOP` does not send hardware commands.
- Tango exceptions raised through `tango.Except.throw_exception` instead of `DevFailed(string)`.
- No changes to XML input limits or the v2.3 kinematics.

## Starting
From project root: `python -m server.virtual_stage_server 1`.
Keep the existing ConfigFile path and AxisRole Tango properties. Ensure the XML motor names and geometry are correct.

## Important safety notes
- `dryRun` is **per virtual device**; switching SAN to False does not switch SAT, etc.
- It is in-memory, not persisted; restart resets it to True.
- A dry-run report is a calculation, not a proof of safe motion: it cannot validate collision clearance, hardware interlocks, or dynamic limits.
- Live moves use the inherited v2.3 multi-axis sequential write sequence, **not an atomic coordinated move**. Partial moves can occur if a later write fails.
- The inherited v2.3 SAN/SAT/SAS mapping is overconstrained: three virtual coordinates map to two physical translations. The forward/inverse equations are not exact inverses. **Do not enable live mode until the kinematics are reviewed and verified against your mechanical model.**
- Dry-run validates software limits by reading `minPositionSoftwareLimit` and `maxPositionSoftwareLimit` on SN/ST/SZ. Missing attributes cause rejection.
- The current version does not check the motors' current state, collision constraints, or hardware limit switches before live moves.

## Example
In ATK set SAN `dryRun=True`, write a requested `position`, then inspect `lastMoveReport` and `lastMoveValid`. The displayed `position` remains the actual measurement.

## Test status
Source compiled successfully; no PyTango installation or real Tango hardware available here for runtime testing.
