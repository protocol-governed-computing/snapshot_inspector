#!/usr/bin/env bash
#
# Protocol Inspection Surface — composition launcher.
#
# PURPOSE: a stable, externally observable surface for INSPECTING a known warm-boot snapshot.
# It is bound to that snapshot by design. Alongside Collatz it is one of two out-of-box reference
# implementations, and the complementary one: Collatz demonstrates that a governed workflow
# EXECUTES, this demonstrates what a governed snapshot CONTAINS.
#
#   Assembled snapshot (software_governance + conformance_workloads + business_domains + inspection)
#         |
#         +-- Inspection Surface   (this surface)
#
# This script is where tool-domain-resident knowledge lives: it points the DOMAIN-NEUTRAL transport
# HTTP adapter at this repo's web client and HTTP binding table. Boundary declarations (TI/TE) are
# read from the sealed snapshot, never from here.
#
set -euo pipefail
CLIENT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"     # …/snapshot_inspector/client
INSPECTOR="$(cd "$CLIENT/.." && pwd)"                      # snapshot_inspector/
UMBRELLA="$(cd "$INSPECTOR/.." && pwd)"                    # protocol-governed-computing/

export PGC_RUNTIME_ROOT="$UMBRELLA/protocol_runtime"
export PGC_INSPECTOR_ROOT="$INSPECTOR"
# Impl roots are irrelevant to inspection (nothing executes) but are supplied so a composition
# serving BOTH kinds from one adapter needs no second launcher.
export PGC_IMPL_ROOTS="$UMBRELLA/software_governance:$UMBRELLA/conformance_workloads:$UMBRELLA/business_domains"
export PGC_HTTP_BINDINGS="$CLIENT/bindings/http.json"
export PGC_SNAPSHOT_ROOT="${PGC_SNAPSHOT_ROOT:-$UMBRELLA/snapshot}"
export PGC_DATA_ROOT="${PGC_DATA_ROOT:-$UMBRELLA/data/inspection_client}"
# Static mounts (all READ-ONLY, config-driven):
#   /          the web client (shell + inspection screen)
#   /snapshot  live inspection of the assembled snapshot — serves behaviour-logic PNGs, which are
#              binary assets fetched directly rather than inlined in a governed response.
export PGC_STATIC_MOUNTS="/=$CLIENT/web;/snapshot=$PGC_SNAPSHOT_ROOT"
export PGC_HTTP_PORT="${PGC_HTTP_PORT:-8001}"

echo "PGC inspection surface (snapshot-bound)"
echo "  client   : $CLIENT"
echo "  snapshot : $PGC_SNAPSHOT_ROOT"
echo "  port     : $PGC_HTTP_PORT"
echo

exec "$UMBRELLA/protocol_transport/run_http.sh"
