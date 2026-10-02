# Validated sensorless safety fixtures

These fixtures are independent regression references recovered from the real
K1 Max production-validation transcripts for:

`known-good-eddy-production-20261001-153849`

Recorded production `sensorless.cfg` SHA256:

```text
548fdaa7d19a0eaf5a943febe416bde97dd736987ecf7e2991a5bd61b0caa12c
```

The raw archived `sensorless.cfg` bytes are not stored in this repository and
were not available as a standalone file in the accessible conversation/library
history when this test contract was created. Therefore CI does **not** claim to
reproduce the whole-file SHA256.

Instead, the history contains exact terminal output for the complete
pre-final `_IF_HOME_Z`, `_HOME_Z`, and `homing_override` sections plus the
exact three-block patch that produced the corrected production state.

CI therefore enforces:

1. exact recovered final `_IF_HOME_Z` text;
2. exact recovered final `_HOME_Z` text;
3. exact recovered pre-XY connectivity-only safety block;
4. the superseded off-bed `MARGIN=1.000 MAX_TRAVEL=5.000` block is absent;
5. `_IF_MOVE_XY`, `_HOME_Y`, and `_HOME_X` are byte-preserved by activation;
6. all of `homing_override` outside the validated pre-XY replacement is
   byte-preserved by activation.

If the original cleaned production archive is later added as a test artifact,
a full-file SHA256 regression can be added on top of this contract.
