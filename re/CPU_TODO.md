# CPU work after the first physical strict-boot test

- Corrected unsafe-zero software probe still stops at MIPS16 `F140` at
  `BFC0AF06` after 3,203,621 instructions. This is an EXTEND prefix; implement
  the complete paired instruction and word-boundary fetch semantics with
  directed tests before claiming further execution. Zero MMIO is experimental.
- Review MIPS16 JR/JRC RA decoding: current RTL first requires `ry==1` and
  then checks `m16[7]`, which cannot be set under that condition. The compact
  JRC form uses its ND bit within that same field, so this path appears
  unreachable. Python's RA-form selection has the same narrow condition.
  Confirm encodings against MD00076, then test no-delay return and ISA switch.
- The strict boot test needs neither of those extensions before the first
  unknown read. They are not included in the current corrected bitstream.
- Upload-completion tracking currently detects the last flash address;
  it does not prove every preceding beat was committed. Add a buffered upload
  transaction/count/ordering test before trusting the full-flash-loaded flag.
- CPU memory lane tests cover the CPU port; they do not validate the real
  HPS upload or DDR controller. Compare hardware telemetry against strict
  counters first, then run a deterministic read-after-write/upload test.
