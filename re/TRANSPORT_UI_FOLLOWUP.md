# Transport UI investigation — 9 November 2026

## Latest result, 09:40 UTC

The 650M native RTL run completed without a software abort and produced a
populated ALL CHANNELS grid with TEST ONE / TEST TWO and both LOCAL TEST titles.
`re/transport/native_long.png` is a **simulation render**, not hardware footage.
It consumed/acknowledged 3532 sections, CRC errors0, GPU completions67,
Huffman calls8, title B5 calls5, row calls3. NVRAM reads reach20550 and stop
after400M; the main o-code event loop then keeps running. The earlier310M
tests ended too early to establish permanent failure.

Timing-passing compile g is deployed as `Pace2500N_TS.rbf`, SHA256
`4085c2a69c1986b274da9f0830ec29b1d4aa81064ea7d95398f0f9d6803148d7`,
3947576bytes, minimum reported slack+0.096ns/core+1.204ns. All source/ROM hashes
are recorded in `re/deployment/v048_build_verified.json`. v047 remains available.

The original MGL order flash/RAM/state/TS caused HALT05 on g: the ordinary
download hold resets CPU decode/branch state while it may be executing.
The source launchers now use flash/RAM/TS/state. This retest passes the startup
failure. Runtime TS replacement is still unsafe; restart through an MGL.

Full-day physical g later entered the original software-abort routine.
The saved TASK30 stack resolves the path through800A62E0 ->8007EEB8 ->8001ECF8
->8003A928. The retry/send routine aborts with4C11 after two failures. These
are SDK message sends, **not memory allocations**; the early allocation name
in a decompiler output was a provisional interpretation and is superseded.
Ghidra's original enqueue and metadata-lookup functions establish the message
list layouts. The physical snapshot has free0/queued270, all toTASK30.

The sparse replay uses1 fixed TOT per8-second file and a SI/title wave every2s.
It remained live until the morning capture (HALT00, one stable video underrun).
Hardware RAM contains decoded LOCAL TEST ONE, and an actual SSH screenshot
shows a tuned TEST ONE banner and programme titles with a channel technical-fault
message. There is no MPEG2/MP2 decoder. F1/Back Up attempts have not yet returned
the display to the grid. Evidence: `re/deployment/v048_sparse_now.png`,
`v048_sparse_guide.png`, `v048_sparse_late.log` and its RAM capture.

Queue size alone is not a proof of a stuck task: working native650M also has
free8/queued262. Sparse hardware has free1/queued269, still running TASK30,
and no saved abort-loop PC. These recurring event8 messages carry8000/8001
and increasing sequence values. Their exact producer is being traced directly
at8007FB08 in `native_event_producer`; do not assume that they are SI or clock
notifications. No guest-memory writes were used to clear the queues.

## Earlier captures and primary findings

The final block-RAM-filter native run (`native_updates_early`) retires 310M
instructions and consumes/acknowledges 601 sections, with zero CRC errors.
The original GUI renders ALL CHANNELS, the synthetic stream's 12.00pm Sun 1
clock, and a no-satellite-signal dialog. This is an RTL simulation capture,
not a MiSTer screenshot and not populated programme listings.

## Primary firmware findings

- Ghidra `frontend_state_machine_decompile.txt` decodes the original MIPS16
  acquisition task at 80028530. Its state pointer is 800FCDC4, and the related
  flag is 80105C00. Both the early-key 310M and late-key 300M RAM captures
  contain state 7 and flag 1; the checkpoint has 0/0. The hardware status
  response therefore causes a native frontend transition. This does not
  establish RF accuracy or prove that every acquisition condition is met.
- Both disclosed presentation interventions retain their checkpoint values:
  80054F84=0 and 80430A28=1. No additional RAM gate has been applied.
- The AV active byte 80161D3C remains zero and selection 80161D40 remains
  FFFFFFFF. The reason is still under investigation.
- Ghidra `av_command_f4_decompile.txt` shows 80054268 constructing F4 at byte
  33 of a local 36-byte command, then sending an internal queue. F4 is not
  evidence for adding a guessed DVB table to the transport.
- `nvram_shadow_native_decompile.txt` independently decodes 8002926C: a bounded
  16KiB NVRAM read uses the device if the shadow-valid byte at shadow+4000 is
  zero, otherwise a semaphore-protected RAM copy. Its shadow base resolves to
  801170E0 in the captured firmware.
- The early-key capture's validated TASK30 control block is 801D5B48. Its
  saved stack pointer is 801D4FAC, within its stack bounds 801D3B04..801D5B00.
  The saved stack contains return addresses in the NVRAM and service-list
  routines (80029545, 8002938F, 800B4741, 800B48F9, 800B627F), and bytecode
  addresses 9FC85F83/9FC85F4E/9FC85F4C. These are saved-stack observations,
  not an assertion that all those addresses are currently executing.
- `ocode_fetch_native.txt` confirms the interpreter fetch at 80069298 reads
  a byte at gpr[2] and advances the local code pointer at sp+2C.

## Working hypothesis and next check

The read-only reference project's investigation records a counted favourites
rebuild at bytecode 9FC85F41..9FC85F92. Its apparent freeze ended after hundreds
of millions of instructions; the author withdrew earlier claims of a permanent
GUI refusal. Our saved stack is consistent with this work, but its completion
has not yet been measured here. The 300–310M runs resume at 200M and therefore
exercise only 100–110M further instructions.

Allow a substantially longer physical run before diagnosing a persistent UI
failure. Capture RAM, keyboard/redraw counters and actual screenshots before
and after; do not bypass the work with guest-memory writes. The current native
notification run records key delivery, frontend notifications, AV commands and
UI event data, with Back Up / Guide / Select after the initial acquisition.

## Build validation

Compile f fitted 75% ALMs, 387 RAM blocks and 50 DSP blocks. Firmware-clock
setup passes +1.066ns; the HDMI scaler has a -0.005ns setup path. Its reports
and undeployed RBF are preserved in `re/transport/build_f`. Compile g retries
placement with seed 2 and identical functional RTL. Do not mistake the earlier
RBF for the pending build or report the small HDMI violation as a timing pass.
