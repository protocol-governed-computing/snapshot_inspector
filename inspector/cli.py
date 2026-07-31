"""`si` — the command-line client of `inspector.api`.

**Generated from the SNAPSHOT, not hand-written.** Every command, its arguments and its help text
come from the inspection contracts the snapshot declares; there is no per-operation code here.
That is deliberate twice over: a CLI with hand-written commands accretes capability the API does
not have and becomes a second inspection engine, and a CLI built from a private list would offer
commands the snapshot in front of it never declared. Authoring a TI artifact is the only way to
add a command, and it is then automatically present.

    si <group> <verb> [args]        one command per Operation Identity: si.artifact.show → si artifact show
    si operations                   the catalog itself
    si --snapshot PATH …            which snapshot to read

Snapshot resolution, in order: `--snapshot`, `$PGC_SNAPSHOT_ROOT`, `./snapshot`. The only
requirement is that the directory carry a `manifest.json` — an ASSEMBLED snapshot is the input
contract, and nothing else is gated on.

Exit codes: 0 on SUCCESS, 1 on NOT_FOUND, 2 on usage or snapshot error. `si snapshot validate
--strict` additionally exits 1 when the snapshot is invalid, so it works as a CI gate.

Stdlib only (argparse) — this repo installs nothing.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from inspector.api import query
from inspector.catalog import Operation, load_catalog
from inspector.kinds import CATEGORIES
from inspector.snapshot import Snapshot, SnapshotError

_DEFAULT_SNAPSHOT = "snapshot"


def _snapshot_root(argv: list[str]) -> Path:
    """Resolve the snapshot BEFORE the parser exists.

    The commands are generated from the snapshot's declared operations, so the snapshot has to be
    located first — `--snapshot` is read by a deliberately minimal pre-pass rather than by the
    parser it is needed to build. This is the one place the ordering is inverted, and it is
    inverted because the protocol, not the code, decides what commands exist.
    """
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--snapshot", default=None)
    known, _ = pre.parse_known_args(argv)
    return Path(known.snapshot or os.environ.get("PGC_SNAPSHOT_ROOT") or _DEFAULT_SNAPSHOT)


def _group_and_verb(identity: str) -> tuple[str, str]:
    """`si.artifact.show` → ('artifact', 'show'); `si.behavior_logic.show` → ('behavior_logic', 'show')."""
    parts = identity.split(".")
    return parts[1], ".".join(parts[2:])


def _dest(param: str) -> str:
    return f"param_{param}"


def _build_parser(operations: dict[str, Operation]
                  ) -> tuple[argparse.ArgumentParser, dict[tuple[str, str], Operation]]:
    parser = argparse.ArgumentParser(
        prog="si",
        description="Read-only inspection of an assembled PGC snapshot.",
    )
    parser.add_argument("--snapshot", default=None, metavar="PATH",
                        help="snapshot root (default: $PGC_SNAPSHOT_ROOT, else ./snapshot)")
    parser.add_argument("--json", action="store_true", help="emit the raw payload as JSON")
    groups = parser.add_subparsers(dest="group", metavar="<group>")

    # The same two options after the verb, where a reader naturally reaches for them
    # (`si artifact list --json`). SUPPRESS so an unused subcommand copy never overwrites the
    # value already parsed at the top level.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--snapshot", metavar="PATH", default=argparse.SUPPRESS)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    by_group: dict[str, list[Operation]] = {}
    for op in operations.values():
        by_group.setdefault(_group_and_verb(op.identity)[0], []).append(op)

    def bind(parser: argparse.ArgumentParser, op: Operation) -> None:
        """Give a parser this operation's declared parameters and bind it to the identity."""
        for param in op.params:
            if param in op.flags:
                parser.add_argument(f"--{param}", dest=_dest(param), action="store_true")
            elif param in op.required:
                parser.add_argument(_dest(param), nargs="?", default=None, metavar=param.upper())
            else:
                parser.add_argument(f"--{param}", dest=_dest(param), default=None)
        parser.set_defaults(_operation=op.identity)

    routes: dict[tuple[str, str], Operation] = {}
    order = {c: i for i, c in enumerate(CATEGORIES)}
    for group_name in sorted(by_group, key=lambda g: (order.get(by_group[g][0].category, 99), g)):
        ops = sorted(by_group[group_name], key=lambda o: o.identity)

        # A two-segment identity (`si.catalog`) is a command in its own right; a three-segment one
        # (`si.artifact.show`) is a verb under a group. The shape of the identity decides, so an
        # operation named either way gets the command a reader would expect.
        flat = [op for op in ops if not _group_and_verb(op.identity)[1]]
        if flat:
            if len(ops) > 1:
                raise ValueError(
                    f"identity group {group_name!r} mixes a bare command with verbs: "
                    f"{[o.identity for o in ops]}"
                )
            op = flat[0]
            command = groups.add_parser(group_name, help=op.summary, parents=[common],
                                        description=(f"{op.summary}\n\n"
                                                     f"Operation Identity: {op.identity}  ({op.kind})"),
                                        formatter_class=argparse.RawDescriptionHelpFormatter)
            bind(command, op)
            routes[(group_name, "")] = op
            continue

        group_parser = groups.add_parser(group_name, help=f"{ops[0].category.lower()} operations")
        verbs = group_parser.add_subparsers(dest="verb", metavar="<verb>")
        for op in ops:
            _, verb = _group_and_verb(op.identity)
            verb_parser = verbs.add_parser(verb, help=op.summary, parents=[common], description=(
                f"{op.summary}\n\nOperation Identity: {op.identity}  ({op.kind})"
            ), formatter_class=argparse.RawDescriptionHelpFormatter)
            bind(verb_parser, op)
            routes[(group_name, verb)] = op

    operations_parser = groups.add_parser(
        "operations", help="list every inspection operation this snapshot inspector answers")
    operations_parser.set_defaults(_operation="__catalog__")

    return parser, routes


# ── rendering ────────────────────────────────────────────────────
#
# One generic renderer, for the same reason there is one generic command builder: a per-operation
# formatter is per-operation code, and per-operation code drifts from the payload it formats.

def _render(value: Any, indent: int = 0) -> list[str]:
    pad = "  " * indent
    lines: list[str] = []
    if isinstance(value, dict):
        scalars = {k: v for k, v in value.items() if not isinstance(v, (dict, list))}
        nested = {k: v for k, v in value.items() if isinstance(v, (dict, list))}
        width = max((len(k) for k in scalars), default=0)
        for key, scalar in scalars.items():
            lines.append(f"{pad}{key.ljust(width)}  {scalar}")
        for key, child in nested.items():
            if not child:
                lines.append(f"{pad}{key}: —")
                continue
            lines.append(f"{pad}{key}:")
            lines.extend(_render(child, indent + 1))
    elif isinstance(value, list):
        if all(isinstance(item, dict) for item in value) and value:
            lines.extend(_render_table(value, pad))
        else:
            lines.extend(f"{pad}- {item}" for item in value)
    else:
        lines.append(f"{pad}{value}")
    return lines


def _render_table(rows: list[dict[str, Any]], pad: str) -> list[str]:
    """List-of-dicts as a table when the rows are flat and share a shape; itemised otherwise."""
    columns = list(dict.fromkeys(k for row in rows for k in row))
    flat = all(not isinstance(row.get(c), (dict, list)) for row in rows for c in columns)
    if not flat or len(columns) > 8:
        lines = []
        for position, row in enumerate(rows):
            lines.append(f"{pad}—" if position else f"{pad}—")
            lines.extend(_render(row, len(pad) // 2 + 1))
        return lines
    widths = {
        c: max(len(c), max((len(str(row.get(c, ""))) for row in rows), default=0))
        for c in columns
    }
    header = "  ".join(c.ljust(widths[c]) for c in columns)
    lines = [f"{pad}{header}", f"{pad}{'  '.join('-' * widths[c] for c in columns)}"]
    lines.extend(
        f"{pad}{'  '.join(str(row.get(c, '')).ljust(widths[c]) for c in columns)}"
        for row in rows
    )
    return lines


def _render_catalog(operations: dict[str, Operation]) -> list[str]:
    lines = ["Protocol Inspection — read-only inspection of the PGC snapshot", ""]
    by_category: dict[str, list[Operation]] = {}
    for op in operations.values():
        by_category.setdefault(op.category, []).append(op)
    for category in CATEGORIES:
        ops = by_category.get(category)
        if not ops:
            continue
        lines.append(f"  {category}")
        for op in ops:
            group, verb = _group_and_verb(op.identity)
            params = " ".join(
                f"<{p}>" if p in op.required else f"[--{p}]" for p in op.params
            )
            lines.append(f"    si {group} {verb} {params}".rstrip())
            lines.append(f"        {op.summary}  [{op.kind}]")
        lines.append("")
    return lines


# ── entry point ──────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]

    # The snapshot declares the commands, so it is located first and read before the parser is
    # built. A snapshot that declares no inspection contracts yields a usage error, not a partial
    # CLI answering from a list the snapshot never agreed to.
    root = _snapshot_root(argv)
    try:
        operations = load_catalog(Snapshot(root))
    except SnapshotError as exc:
        print(f"si: {exc}", file=sys.stderr)
        return 2

    parser, _ = _build_parser(operations)
    args = parser.parse_args(argv)

    operation = getattr(args, "_operation", None)
    if operation is None:
        parser.print_help()
        return 2

    if operation == "__catalog__":
        print("\n".join(_render_catalog(operations)))
        return 0

    op = operations[operation]
    params = {p: getattr(args, _dest(p)) for p in op.params}
    params = {k: v for k, v in params.items() if v not in (None, False)}

    try:
        status, payload = query(operation, params, root)
    except SnapshotError as exc:
        print(f"si: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"{operation}  [{status}]")
        print("\n".join(_render(payload, 1)))

    if status != "SUCCESS":
        return 1
    # `validate --strict` is a CI gate: an invalid snapshot must fail the command, not merely
    # report inside a successful one.
    if payload.get("valid") is False:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
