
# VirtualStageServer — Codex project instructions

## Environment
- Target OS: CentOS
- Python: 3.6.13
- PyTango: 9.2.2
- No additional packages may be installed on production.
- Do not use Python syntax introduced after Python 3.6.
- Preserve existing Tango device/property compatibility.

## Mechanical model
Real stage axes:
- SN, ST: orthogonal translations
- SRZ: rotation in the SN-ST plane

Virtual axes:
- SAN, SAT: orthogonal axes attached to the rotating stage
- SAS: translation along the defocus direction
- SAZ: virtual rotation associated with SRZ

Model parameters:
- SRZ0: reference rotation
- Alpha: defocus direction angle
- Axis offsets and software limits
- PIX, PIY, PIZ: PI controller attributes

Important:
- SAS is below SRZ mechanically.
- SAS translates along the defocus direction for all SRZ.
- SAN and SAT rotate with SRZ.
- SAS generally contributes to both SN and ST.
- Use the source code and verified specifications
  to establish the exact coordinate conventions.
- Never invent unknown parameter values.

## Kinematic verification
- Derive forward and inverse equations independently.
- Check coordinate units and angle conventions.
- Check transformation round trips.
- Identify singular and overconstrained mappings.
- Compare requested and achievable real coordinates.
- Report numerical residuals and tolerances.
- Detect discrepancies between model and implementation.

## Motion and motor states
- Inspect motor-state propagation and aggregation.
- Treat real-axis faults and moving states carefully.
- Preserve agreed ON state for the ready virtual motor.
- Verify recovery after faults or disconnections.
- Distinguish commanded from measured coordinates.
- Identify sequential rather than atomic real moves.

## Safety
- Do not connect to live Tango motor devices.
- Do not issue motion or motor-control commands.
- Tests must use fake or simulated motor interfaces.
- Never bypass software limits.
- Do not silently correct a failed safety check.
- Dry-run must not change persistent coordinates.

## Version control
- Current implementation: v2.4/v2.5.
- v2.6 is planned but not authorized for implementation.
- Analyze and document v2.6 requirements if needed.
- Do not implement v2.6 without explicit authorization.
- Never modify production code during an audit task.

## Testing and reporting
- Prefer Python standard-library unittest.
- Keep tests compatible with Python 3.6.
- Explicitly distinguish executed tests from proposed tests.
- Report unavailable dependencies or hardware honestly.
- List changed files, regressions, and unresolved issues.
- Require explicit approval before live deployment.
