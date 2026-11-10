"""Verify fresh Quartus transport output and record a deployment manifest.

Read-only apart from the requested JSON output. Rejects failed flows, stale
images/reports, negative reported slack and mismatched isolated RTL sources.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root, build, log):
    content = log.read_text(errors='replace')
    if 'Info (293000): Quartus Prime Full Compilation was successful.' not in content:
        raise ValueError('Selected compilation log has no full-flow success')
    started = re.search(r'Processing started: (.+)', content)
    if not started:
        raise ValueError('Compilation log has no start time')
    start = datetime.strptime(started[1].strip(), '%a %b %d %H:%M:%S %Y').timestamp()
    output = build / 'output_files'
    rbf = output / 'Pace2500N.rbf'
    timing = output / 'Pace2500N.sta.summary'
    fit = output / 'Pace2500N.fit.summary'
    for path in (rbf, timing, fit):
        if not path.is_file() or path.stat().st_mtime < start:
            raise ValueError(f'Missing or stale compilation output: {path}')
    if 'Fitter Status : Successful' not in fit.read_text():
        raise ValueError('Fitter did not succeed')
    summary = timing.read_text()
    slacks = [(kind, float(slack)) for kind, slack in re.findall(
        r'Type\s*:\s*([^\r\n]+)\s+Slack\s*:\s*([-+\d.]+)', summary)]
    if not slacks or not any(kind.startswith('Setup ') for kind, _ in slacks):
        raise ValueError('No setup timing results found')
    if any(slack < 0 for _, slack in slacks):
        raise ValueError(f'Negative reported timing slack: {min(slacks, key=lambda item: item[1])}')
    qip = (build / 'files.qip').read_text()
    sources = re.findall(r'SYSTEMVERILOG_FILE\s+(\S+)', qip)
    if 'rtl/Pace2500N_Transport.sv' not in sources:
        raise ValueError('Selected build does not use the transport top')
    sources += ['rtl/pace_checkpoint_demux_match.vh', 'rtl/pace_checkpoint_csr.vh']
    sources += [path.relative_to(build).as_posix() for path in sorted((build / 'rom').glob('*.hex'))]
    hashes = {}
    for name in sources:
        current, isolated = root / name, build / name
        if sha(current) != sha(isolated):
            raise ValueError(f'Root and isolated source differ: {name}')
        if isolated.stat().st_mtime > start:
            raise ValueError(f'Isolated source changed during compilation: {name}')
        hashes[name] = sha(isolated)
    return dict(verified_utc=datetime.now(timezone.utc).isoformat(),
                build=str(build), compilation_log=str(log),
                compilation_log_sha256=sha(log),
                rbf=str(rbf), rbf_sha256=sha(rbf), rbf_bytes=rbf.stat().st_size,
                minimum_reported_slack_ns=min(value for _, value in slacks),
                timing=[dict(type=kind, slack_ns=value) for kind, value in slacks],
                source_sha256=hashes,
                qsf_sha256=sha(build / 'Pace2500N.qsf'),
                sdc_sha256=sha(build / 'Pace2500N.sdc'),
                fit_summary=fit.read_text(),
                timing_scope='Reported TimeQuest domains; upstream unconstrained-path warnings remain',
                hardware_verified=False, fpga_cpu_execution=True,
                protected_loader_cold_boot_solved=False,
                checkpoint_ram_interventions=['80054F84 FFFFFFFF->00000000',
                                              '80430A28 00000000->00000001'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=Path('builds/v048_transport'))
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = verify(root, args.build.resolve(), args.log.resolve())
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(f"Verified RBF {result['rbf_sha256']}, {result['rbf_bytes']} bytes, "
          f"minimum reported slack {result['minimum_reported_slack_ns']:+.3f}ns")


if __name__ == '__main__':
    main()
