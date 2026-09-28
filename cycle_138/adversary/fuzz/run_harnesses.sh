#!/usr/bin/env bash
# run_harnesses.sh — execute every Atheris harness in this directory with
# the Invariant 26 §2 timeout (5s per surface).
#
# Usage:
#   ./run_harnesses.sh          # 5s per harness (default)
#   ./run_harnesses.sh 30       # 30s per harness (deeper fuzzing)
#
# Environment:
#   PYTHONPATH must include ``src/`` (or the package must be installed).
#   The script will export it automatically if the package is importable
#   from a sibling ``src/`` directory.
#
# Layout this script expects:
#   <repo_root>/
#       src/iso7064_pure/         # the package
#       cycle_138/adversary/fuzz/ # this script's directory
#           harness_*.py          # Atheris harnesses
#           run_harnesses.sh
#           corpus/               # seed corpus (input)
#           crashes/, hangs/, oom/, logs/, artifacts/
#
# The script writes per-harness stdout/stderr to logs/<surface>.log,
# moves any crash-* / oom-* / timeout-* artifacts into per-harness
# subdirectories under crashes/ hangs/ oom/.

set -uo pipefail

PER_HARNESS_SECONDS="${1:-5}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Layout: HERE = <repo>/cycle_138/adversary/fuzz
# Three levels up = <repo>.
REPO_ROOT="$(cd "$HERE/../../.." && pwd)"

# Ensure the package is importable.
if [[ -z "${PYTHONPATH:-}" ]] || ! python3 -c "import iso7064_pure" 2>/dev/null; then
    if [[ -f "$REPO_ROOT/src/iso7064_pure/__init__.py" ]]; then
        export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
    fi
fi

echo "==================================================================="
echo "cycle_138 adversarial fuzz sweep (HARNESSES phase)"
echo "  per-harness timeout: ${PER_HARNESS_SECONDS}s"
echo "  PYTHONPATH:          ${PYTHONPATH:-<unset>}"
echo "  python:              $(command -v python3) ($(python3 --version 2>&1))"
echo "  atheris:             $(python3 -c 'import atheris; print("installed")' 2>&1)"
echo "  repo_root:           $REPO_ROOT"
echo "==================================================================="

# Make sure the artifact directories exist.
mkdir -p "$HERE/crashes" "$HERE/hangs" "$HERE/oom" "$HERE/logs" "$HERE/artifacts"

# Per-surface harness list.  Order: cheapest first so the sweep
# surfaces the most likely bug first.
HARNESSES=(harness_compute.py harness_per_system.py harness_alphabet.py harness_verify.py harness_cli.py)

# Per-surface label (used for artifact subdirectories).
declare -A SURFACE_FOR
SURFACE_FOR[harness_compute.py]="compute"
SURFACE_FOR[harness_per_system.py]="per_system"
SURFACE_FOR[harness_alphabet.py]="alphabet"
SURFACE_FOR[harness_verify.py]="verify"
SURFACE_FOR[harness_cli.py]="cli"

# Per-surface artifact dir (atheris drops crash-*/oom-*/timeout-* here).
declare -A ARTIFACT_DIR_FOR

for h in "${HARNESSES[@]}"; do
    if [[ ! -f "$HERE/$h" ]]; then
        echo "[skip] $h (not found)"
        continue
    fi
    surface="${SURFACE_FOR[$h]:-$h}"
    artifact_dir="$HERE/artifacts/${surface}"
    ARTIFACT_DIR_FOR[$h]="$artifact_dir"
    mkdir -p "$artifact_dir" "$HERE/crashes/${surface}" "$HERE/hangs/${surface}" "$HERE/oom/${surface}"
done

# Run each harness.
for h in "${HARNESSES[@]}"; do
    if [[ ! -f "$HERE/$h" ]]; then
        continue
    fi
    surface="${SURFACE_FOR[$h]:-$h}"
    artifact_dir="${ARTIFACT_DIR_FOR[$h]}"
    log="$HERE/logs/${surface}.log"

    echo "-------------------------------------------------------------------"
    echo "[run]  $h (surface=$surface, timeout=${PER_HARNESS_SECONDS}s)"
    echo "-------------------------------------------------------------------"
    cd "$HERE"
    # We deliberately do NOT use ``set -e`` here — atheris returning
    # non-zero on a crash is exactly the signal we want to surface.
    set +e
    timeout "${PER_HARNESS_SECONDS}" python3 "$h" \
        -atheris_runs=100000 \
        -max_total_time="${PER_HARNESS_SECONDS}" \
        -artifact_prefix="${artifact_dir}/" \
        >"$log" 2>&1
    rc=$?
    set -uo pipefail
    echo "  rc=$rc   log=$log"
    echo "  (last 5 lines of $log)"
    tail -5 "$log" 2>/dev/null | sed 's/^/    /'

    # Quarantine artifacts.
    crashes=0 hangs=0 ooms=0
    if compgen -G "$artifact_dir/crash-*" >/dev/null 2>&1; then
        crashes=$(ls -1 "$artifact_dir"/crash-* 2>/dev/null | wc -l)
        mv "$artifact_dir"/crash-* "$HERE/crashes/${surface}/" 2>/dev/null || true
    fi
    if compgen -G "$artifact_dir/timeout-*" >/dev/null 2>&1; then
        hangs=$(ls -1 "$artifact_dir"/timeout-* 2>/dev/null | wc -l)
        mv "$artifact_dir"/timeout-* "$HERE/hangs/${surface}/" 2>/dev/null || true
    fi
    if compgen -G "$artifact_dir/oom-*" >/dev/null 2>&1; then
        ooms=$(ls -1 "$artifact_dir"/oom-* 2>/dev/null | wc -l)
        mv "$artifact_dir"/oom-* "$HERE/oom/${surface}/" 2>/dev/null || true
    fi

    # Defensive: atheris may drop into cwd (REPO_ROOT or HERE) if
    # ``-artifact_prefix`` is missing trailing slash.
    rm -f "$HERE"/crash-* "$HERE"/oom-* "$HERE"/timeout-*

    echo "  summary: crashes=$crashes hangs=$hangs oom=$ooms"
done

echo "==================================================================="
echo "sweep complete"
echo "  artifacts: $HERE/crashes  $HERE/hangs  $HERE/oom"
echo "  logs:      $HERE/logs"
echo "==================================================================="
