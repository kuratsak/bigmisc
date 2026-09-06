#!/usr/bin/env python3
# v0.4 telemetry + constants + disk read optimization + progress bar + tiered manifest cache
# baki: deterministic two-stage backup sync utility

import argparse
import csv
import fnmatch
import os
import shutil
import sys
import time
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import xxhash
from tqdm import tqdm

HASH_CACHE_TTL_DAYS_LARGE = 15
HASH_CACHE_TTL_DAYS_SMALL = 30
HASH_CACHE_MIN_SIZE_BYTES = 1024 * 1024
CHUNK_SIZE = 4 * 1024 * 1024

DEFAULT_CONFIG_PATH = "settings.toml"
MANIFESTS_DIR_NAME = "baki_manifests"
REVIEW_LEDGER_PREFIX = "baki_review_"
POSTSYNC_REPORT_PREFIX = "baki_postsync_"

ACTION_WRITE = "[WRITE]"
ACTION_UPDATE = "[UPDATE]"
ACTION_RESTORE = "[RESTORE]"
ACTION_DELETE = "[DELETE]"
ACTION_MKDIR = "[MKDIR]"
ACTION_RMDIR = "[RMDIR]"
ACTION_IDENTICAL = "[IDENTICAL]"
ACTION_IGNORE = "[IGNORE]"
ACTION_MISSING = "[MISSING]"
WARNING_BIT_ROT_PREFIX = "[WARNING_BIT_ROT]"


@dataclass(slots=True)
class Target:
    name: str
    path: Path


@dataclass(slots=True)
class FileEntry:
    rel_path: str
    size: int
    mtime: str
    hash: str
    hashed_at: str
    is_dir: bool = False
    is_rot: bool = False


@dataclass(slots=True)
class BadFile:
    location: str
    rel_path: str
    expected_hash: str
    actual_hash: str
    mtime: str
    size: int
    last_hashed_at: str


@dataclass(slots=True)
class ScanStats:
    scanned_count: int = 0
    cached_count: int = 0
    rehashed_count: int = 0
    hashed_bytes: int = 0
    hashing_duration_sec: float = 0.0

    @property
    def speed_mb_s(self) -> float:
        mb = self.hashed_bytes / (1024 * 1024)
        return mb / max(self.hashing_duration_sec, 0.001)


def format_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(ts_str: str) -> datetime:
    normalized = ts_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def sanitize_name(path_str: str) -> str:
    return "".join(
        c if c.isalnum() or c in ("-", "_") else "_" for c in path_str
    ).strip("_")


def path_to_slug(path: Path) -> str:
    resolved_str = str(path.resolve())
    return "".join(
        c if c.isalnum() or c in ("-", "_") else "_" for c in resolved_str
    ).strip("_")


def truncate_path(path_str: str, max_len: int = 55) -> str:
    norm = path_str.replace("\\", "/")
    if len(norm) <= max_len:
        return norm
    if "/" in norm:
        dir_part, file_name = norm.rsplit("/", 1)
        dir_prefix = f"{dir_part[:17]}.." if len(dir_part) > 19 else dir_part
        file_str = (
            f"{file_name[:15]}...{file_name[-10:]}"
            if len(file_name) > 25
            else file_name
        )
        return f"{dir_prefix}/{file_str}"
    return f"{norm[:22]}...{norm[-12:]}"


def load_config(config_path: Path) -> tuple[Path, list[Target], list[str], list[str]]:
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    paths_sec = data.get("paths", {})
    source_raw = paths_sec.get("source")
    if not source_raw:
        raise ValueError("Missing 'paths.source' in settings.toml")
    targets_raw = paths_sec.get("targets", [])
    targets: list[Target] = []
    for item in targets_raw:
        if isinstance(item, dict):
            name = item.get("name") or sanitize_name(item.get("path", ""))
            targets.append(Target(name=name, path=Path(item["path"])))
        else:
            targets.append(Target(name=sanitize_name(str(item)), path=Path(item)))
    filters_sec = data.get("filters", {})
    excludes = [str(x) for x in filters_sec.get("excludes", [])]
    includes = [str(x) for x in filters_sec.get("includes", [])]
    return Path(source_raw), targets, excludes, includes


def select_target(targets: list[Target], target_arg: str | None) -> Target:
    if not targets:
        raise ValueError("No targets defined in configuration.")
    if target_arg:
        if target_arg.isdigit():
            idx = int(target_arg) - 1
            if 0 <= idx < len(targets):
                return targets[idx]
        for t in targets:
            if (
                t.name.lower() == target_arg.lower()
                or str(t.path).lower() == target_arg.lower()
            ):
                return t
        raise ValueError(f"Target '{target_arg}' not found in configuration.")
    if len(targets) == 1:
        return targets[0]
    print("Available backup targets:")
    for i, t in enumerate(targets, start=1):
        print(f"  [{i}] {t.name} -> {t.path}")
    while True:
        choice = input(f"Select target [1-{len(targets)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(targets):
            return targets[int(choice) - 1]
        print("Invalid selection. Try again.")


def matches_glob(rel_path: str, patterns: list[str]) -> bool:
    posix_path = rel_path.replace("\\", "/")
    file_name = Path(posix_path).name
    for pat in patterns:
        norm_pat = pat.replace("\\", "/")
        if fnmatch.fnmatch(posix_path, norm_pat) or fnmatch.fnmatch(
            file_name, norm_pat
        ):
            return True
        if fnmatch.fnmatch(posix_path, f"*/{norm_pat}") or fnmatch.fnmatch(
            posix_path, f"**/{norm_pat}"
        ):
            return True
        if norm_pat.endswith("/*") and fnmatch.fnmatch(posix_path, norm_pat[:-2]):
            return True
    return False


def is_active_path(rel_path: str, excludes: list[str], includes: list[str]) -> bool:
    if not excludes:
        return True
    if not matches_glob(rel_path, excludes):
        return True
    return bool(includes and matches_glob(rel_path, includes))


def scan_directory(root: Path) -> list[tuple[str, Path, os.stat_result, bool]]:
    results: list[tuple[str, Path, os.stat_result, bool]] = []
    if not root.exists():
        return results
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        curr_dir = Path(dirpath)
        if not dirnames and not filenames and curr_dir != root:
            rel = curr_dir.relative_to(root).as_posix()
            results.append((rel, curr_dir, curr_dir.stat(), True))
            continue
        for fn in filenames:
            file_path = curr_dir / fn
            if file_path.is_symlink():
                continue
            rel = file_path.relative_to(root).as_posix()
            try:
                results.append((rel, file_path, file_path.stat(), False))
            except OSError:
                continue
    return results


def hash_file_chunked(file_path: Path) -> tuple[str, int, float]:
    hasher = xxhash.xxh3_128()
    total_bytes = 0
    t0 = time.time()
    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)
            total_bytes += len(chunk)
    return hasher.hexdigest(), total_bytes, time.time() - t0


def parse_manifest_csv(
    csv_path: Path, sub_prefix: str, cache: dict[str, FileEntry]
) -> None:
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        lines = [line for line in f if not line.startswith("#")]
        reader = csv.DictReader(lines)
        for row in reader:
            raw_rel = row.get("relative_path", "")
            rel = f"{sub_prefix}/{raw_rel}".lstrip("/") if sub_prefix else raw_rel
            hashed_at = row.get("hashed_at", "")
            if rel not in cache or (hashed_at and hashed_at > cache[rel].hashed_at):
                cache[rel] = FileEntry(
                    rel_path=rel,
                    size=int(row["size"]),
                    mtime=row["mtime"],
                    hash=row["xxh3_128"],
                    hashed_at=hashed_at,
                    is_dir=(int(row["size"]) == 0 and not row["xxh3_128"]),
                )


def load_manifest_cache_for_path(
    manifests_root: Path, target_root: Path
) -> dict[str, FileEntry]:
    cache: dict[str, FileEntry] = {}
    if not manifests_root.exists():
        return cache
    resolved_target = target_root.resolve()

    for folder in manifests_root.iterdir():
        if not folder.is_dir():
            continue
        csv_files = sorted(
            [f for f in folder.glob("*.csv") if not f.name.endswith("_bad.csv")]
        )
        if not csv_files:
            continue
        latest_csv = csv_files[-1]
        try:
            with open(latest_csv, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            if not first_line.startswith("# Path:"):
                continue
            manifest_base = Path(first_line.split(":", 1)[1].strip()).resolve()
            if manifest_base == resolved_target:
                parse_manifest_csv(latest_csv, "", cache)
            elif manifest_base.is_relative_to(resolved_target):
                sub_prefix = manifest_base.relative_to(resolved_target).as_posix()
                parse_manifest_csv(latest_csv, sub_prefix, cache)
        except OSError:
            continue
    return cache


def check_cache_hit(
    entry: FileEntry | None, size: int, mtime_iso: str, ttl_days: int, now_dt: datetime
) -> bool:
    if (
        ttl_days <= 0
        or entry is None
        or entry.size != size
        or entry.mtime != mtime_iso
        or not entry.hashed_at
    ):
        return False
    return (now_dt - parse_iso(entry.hashed_at)).total_seconds() <= ttl_days * 86400


def build_manifest(
    root: Path, cached: dict[str, FileEntry], user_ttl: int | None, loc: str
) -> tuple[list[FileEntry], list[BadFile], ScanStats]:
    entries: list[FileEntry] = []
    bad_files: list[BadFile] = []
    stats = ScanStats()
    now_dt = datetime.now(timezone.utc)
    now_iso = format_iso(now_dt.timestamp())
    scanned = scan_directory(root)
    stats.scanned_count = len(scanned)

    pbar = tqdm(scanned, desc=f"Scanning {loc:<6}", unit="item", dynamic_ncols=True)
    for rel_path, full_path, stat, is_dir in pbar:
        pbar.set_postfix_str(
            f"{stats.speed_mb_s:.1f} MB/s | {truncate_path(rel_path, 50)}"
        )
        if is_dir:
            entries.append(
                FileEntry(
                    rel_path=rel_path,
                    size=0,
                    mtime=format_iso(stat.st_mtime),
                    hash="",
                    hashed_at=now_iso,
                    is_dir=True,
                )
            )
            continue
        size, mtime_iso = stat.st_size, format_iso(stat.st_mtime)
        prev = cached.get(rel_path)
        ttl = (
            user_ttl
            if user_ttl is not None
            else (
                HASH_CACHE_TTL_DAYS_LARGE
                if size >= HASH_CACHE_MIN_SIZE_BYTES
                else HASH_CACHE_TTL_DAYS_SMALL
            )
        )
        if check_cache_hit(prev, size, mtime_iso, ttl, now_dt) and prev is not None:
            stats.cached_count += 1
            entries.append(
                FileEntry(
                    rel_path=rel_path,
                    size=size,
                    mtime=mtime_iso,
                    hash=prev.hash,
                    hashed_at=prev.hashed_at,
                )
            )
            continue

        try:
            actual_hash, hashed_len, duration = hash_file_chunked(full_path)
            stats.rehashed_count += 1
            stats.hashed_bytes += hashed_len
            stats.hashing_duration_sec += duration
        except OSError:
            continue

        is_rot = bool(
            prev
            and prev.size == size
            and prev.mtime == mtime_iso
            and prev.hash
            and prev.hash != actual_hash
        )
        if is_rot and prev is not None:
            bad_files.append(
                BadFile(
                    loc,
                    rel_path,
                    prev.hash,
                    actual_hash,
                    mtime_iso,
                    size,
                    prev.hashed_at,
                )
            )
        entries.append(
            FileEntry(
                rel_path=rel_path,
                size=size,
                mtime=mtime_iso,
                hash=actual_hash,
                hashed_at=now_iso,
                is_rot=is_rot,
            )
        )

    entries.sort(key=lambda e: e.rel_path)
    return entries, bad_files, stats


def write_manifest_csv(
    filepath: Path, base_path: Path, entries: list[FileEntry], stats: ScanStats
) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    hashed_mb = stats.hashed_bytes / (1024 * 1024)
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        f.write(f"# Path: {base_path.resolve()}\n")
        f.write(
            f"# Scanned: {stats.scanned_count}, Cached: {stats.cached_count}, Re-hashed: {stats.rehashed_count}, "
            f"Hashed Bytes: {hashed_mb:.1f} MB, Hashing Time: {stats.hashing_duration_sec:.1f} s, Hashing Speed: {stats.speed_mb_s:.1f} MB/s\n"
        )
        writer = csv.writer(f)
        writer.writerow(["relative_path", "size", "mtime", "xxh3_128", "hashed_at"])
        for e in entries:
            writer.writerow([e.rel_path, e.size, e.mtime, e.hash, e.hashed_at])


def write_badfiles_csv(filepath: Path, bad_files: list[BadFile]) -> None:
    if not bad_files:
        return
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "location",
                "relative_path",
                "expected_hash",
                "actual_hash",
                "mtime",
                "size",
                "last_hashed_at",
            ]
        )
        for b in bad_files:
            writer.writerow(
                [
                    b.location,
                    b.rel_path,
                    b.expected_hash,
                    b.actual_hash,
                    b.mtime,
                    b.size,
                    b.last_hashed_at,
                ]
            )


def generate_ledger(
    source_entries: list[FileEntry],
    target_entries: list[FileEntry],
    excludes: list[str],
    includes: list[str],
    source_path: Path,
    target_path: Path,
    source_manifest_path: Path,
    target_manifest_path: Path,
    ledger_path: Path,
) -> None:
    s_map = {e.rel_path: e for e in source_entries}
    t_map = {e.rel_path: e for e in target_entries}
    all_keys = sorted(set(s_map.keys()) | set(t_map.keys()))
    lines: list[str] = [
        "# BAKI REVIEW LEDGER",
        f"# Source: {source_path.resolve()}",
        f"# Target: {target_path.resolve()}",
        f"# Generated: {format_iso(time.time())}",
        f"# Source Manifest: {source_manifest_path.resolve()}",
        f"# Target Manifest: {target_manifest_path.resolve()}",
        f"# Actions: {ACTION_WRITE}, {ACTION_UPDATE}, {ACTION_RESTORE}, {ACTION_MISSING}, {ACTION_DELETE}, {ACTION_MKDIR}, {ACTION_RMDIR}, {ACTION_IGNORE}, {ACTION_IDENTICAL}",
        f"# Change {ACTION_MISSING} to {ACTION_DELETE} or {ACTION_RESTORE} to execute.",
        "",
    ]
    for key in all_keys:
        s, t = s_map.get(key), t_map.get(key)
        is_rot = bool((s and s.is_rot) or (t and t.is_rot))
        prefix = WARNING_BIT_ROT_PREFIX if is_rot else ""

        if not is_active_path(key, excludes, includes):
            lines.append(f"{prefix}{ACTION_IGNORE} {key}")
        elif s is not None and t is None:
            lines.append(
                f"{prefix}{ACTION_MKDIR} {key}"
                if s.is_dir
                else f"{prefix}{ACTION_WRITE} {key}"
            )
        elif s is None and t is not None:
            lines.append(
                f"{prefix}{ACTION_RMDIR} {key}"
                if t.is_dir
                else f"{prefix}{ACTION_MISSING} {key}"
            )
        elif s is not None and t is not None:
            if s.is_dir and t.is_dir:
                lines.append(f"{prefix}{ACTION_IDENTICAL} {key}")
            elif (
                not s.is_dir and not t.is_dir and s.hash == t.hash and s.size == t.size
            ):
                lines.append(f"{prefix}{ACTION_IDENTICAL} {key}")
            else:
                lines.append(f"{prefix}{ACTION_UPDATE} {key}")

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def parse_review_header(lines: list[str]) -> tuple[Path, Path]:
    src_path: Path | None = None
    dst_path: Path | None = None
    for line in lines:
        if line.startswith("# Source:"):
            src_path = Path(line.split(":", 1)[1].strip())
        elif line.startswith("# Target:"):
            dst_path = Path(line.split(":", 1)[1].strip())
    if not src_path or not dst_path:
        raise ValueError("Invalid review ledger: missing Source or Target header.")
    return src_path, dst_path


def copy_file_chunked(src: Path, dst: Path) -> int:
    dst.parent.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
        while chunk := fsrc.read(CHUNK_SIZE):
            fdst.write(chunk)
            total_bytes += len(chunk)
    st = src.stat()
    os.utime(dst, (st.st_atime, st.st_mtime))
    return total_bytes


def write_postsync_report(
    report_path: Path,
    counts: dict[str, dict[str, int]],
    exceptions: list[str],
    duration: float,
    bytes_tx: int,
) -> None:
    mb_tx = bytes_tx / (1024 * 1024)
    speed = mb_tx / max(duration, 0.001)
    lines: list[str] = [
        "# BAKI POST-SYNC EXECUTION REPORT",
        f"# Generated: {format_iso(time.time())}",
        f"# Duration: {duration:.1f} s, Transferred: {mb_tx:.1f} MB ({speed:.1f} MB/s)",
        "",
        "# Operation Summary (Attempted / Success / Failed):",
    ]
    for op, data in counts.items():
        lines.append(
            f"  {op:<10}: Attempted={data['attempted']:<4} Success={data['success']:<4} Failed={data['failed']}"
        )
    lines.append("")
    if exceptions:
        lines.append("# Exceptions:")
        for exc in exceptions:
            lines.append(f"  [EXCEPTION] {exc}")
    else:
        lines.append("# Exceptions: None")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def execute_sync_operation(
    action: str,
    rel_path: str,
    src_root: Path,
    dst_root: Path,
    counts: dict[str, dict[str, int]],
    exceptions: list[str],
) -> int:
    if action in counts:
        counts[action]["attempted"] += 1
    bytes_transferred = 0
    try:
        if action == ACTION_MKDIR:
            (dst_root / rel_path).mkdir(parents=True, exist_ok=True)
        elif action in (ACTION_WRITE, ACTION_UPDATE):
            bytes_transferred += copy_file_chunked(
                src_root / rel_path, dst_root / rel_path
            )
        elif action == ACTION_RESTORE:
            bytes_transferred += copy_file_chunked(
                dst_root / rel_path, src_root / rel_path
            )
        elif action == ACTION_DELETE:
            target_file = dst_root / rel_path
            if target_file.is_file():
                target_file.unlink()
        elif action == ACTION_RMDIR:
            target_dir = dst_root / rel_path
            if target_dir.is_dir() and not any(target_dir.iterdir()):
                target_dir.rmdir()
        if action in counts:
            counts[action]["success"] += 1
    except OSError as e:
        if action in counts:
            counts[action]["failed"] += 1
        exceptions.append(f"{action} {rel_path} - {e}")
        print(f"Error executing {action} {rel_path}: {e}", file=sys.stderr)
    return bytes_transferred


def execute_sync_ledger(ledger_path: Path) -> None:
    if not ledger_path.is_file():
        raise FileNotFoundError(f"Review ledger not found: {ledger_path}")
    with open(ledger_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    src_root, dst_root = parse_review_header(lines)
    if not src_root.exists():
        raise FileNotFoundError(f"Source directory does not exist: {src_root}")
    dst_root.mkdir(parents=True, exist_ok=True)

    ops = [
        ACTION_WRITE,
        ACTION_UPDATE,
        ACTION_RESTORE,
        ACTION_DELETE,
        ACTION_MKDIR,
        ACTION_RMDIR,
        ACTION_IDENTICAL,
        ACTION_IGNORE,
    ]
    counts = {op: {"attempted": 0, "success": 0, "failed": 0} for op in ops}
    exceptions: list[str] = []
    bytes_transferred, start_time = 0, time.time()

    active_lines = [l for l in lines if not l.startswith("#")]
    pbar = tqdm(active_lines, desc="Executing sync", unit="op", dynamic_ncols=True)
    for line in pbar:
        parts = line.split(" ", 1)
        if len(parts) != 2:
            continue
        action, rel_path = parts[0], parts[1]
        pbar.set_postfix_str(f"{action} {truncate_path(rel_path, 45)}")
        if action in (ACTION_IDENTICAL, ACTION_IGNORE):
            counts[action]["attempted"] += 1
            counts[action]["success"] += 1
            continue
        bytes_transferred += execute_sync_operation(
            action, rel_path, src_root, dst_root, counts, exceptions
        )

    duration = max(time.time() - start_time, 0.001)
    target_name = ledger_path.stem.replace(REVIEW_LEDGER_PREFIX, "")
    report_file = ledger_path.parent / f"{POSTSYNC_REPORT_PREFIX}{target_name}.txt"
    write_postsync_report(report_file, counts, exceptions, duration, bytes_transferred)
    print(f"\nSync finished in {duration:.1f}s. Report written to {report_file}")


def run_groom(args: argparse.Namespace) -> None:
    source_path, targets, excludes, includes = load_config(Path(args.config))
    target = select_target(targets, args.target)

    manifests_root = Path(MANIFESTS_DIR_NAME)
    cached_src = load_manifest_cache_for_path(manifests_root, source_path)
    cached_dst = load_manifest_cache_for_path(manifests_root, target.path)

    print(f"Scanning source: {source_path}")
    src_entries, src_bad, src_stats = build_manifest(
        source_path, cached_src, args.hash_ttl_days, "source"
    )
    print(
        f"  Source: {src_stats.scanned_count} items, {src_stats.cached_count} cached, {src_stats.rehashed_count} re-hashed "
        f"({src_stats.speed_mb_s:.1f} MB/s)"
    )

    print(f"Scanning target: {target.path}")
    dst_entries, dst_bad, dst_stats = build_manifest(
        target.path, cached_dst, args.hash_ttl_days, "target"
    )
    print(
        f"  Target: {dst_stats.scanned_count} items, {dst_stats.cached_count} cached, {dst_stats.rehashed_count} re-hashed "
        f"({dst_stats.speed_mb_s:.1f} MB/s)"
    )

    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    src_dir = manifests_root / path_to_slug(source_path)
    dst_dir = manifests_root / path_to_slug(target.path)
    src_manifest = src_dir / f"{timestamp_str}.csv"
    dst_manifest = dst_dir / f"{timestamp_str}.csv"

    write_manifest_csv(src_manifest, source_path, src_entries, src_stats)
    write_manifest_csv(dst_manifest, target.path, dst_entries, dst_stats)

    if src_bad:
        write_badfiles_csv(src_dir / f"{timestamp_str}_bad.csv", src_bad)
        print(f"WARNING: Detected {len(src_bad)} source bit rot anomalies.")
    if dst_bad:
        write_badfiles_csv(dst_dir / f"{timestamp_str}_bad.csv", dst_bad)
        print(f"WARNING: Detected {len(dst_bad)} target bit rot anomalies.")

    ledger_file = Path(f"{REVIEW_LEDGER_PREFIX}{target.name}.txt")
    generate_ledger(
        src_entries,
        dst_entries,
        excludes,
        includes,
        source_path,
        target.path,
        src_manifest,
        dst_manifest,
        ledger_file,
    )
    print(f"Review ledger written to: {ledger_file}")


def run_sync(args: argparse.Namespace) -> None:
    execute_sync_ledger(Path(args.review))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="baki", description="Two-stage deterministic backup sync with XXH3-128."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    groom_parser = subparsers.add_parser(
        "groom", help="Scan source and target, generate manifests and review ledger."
    )
    groom_parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to configuration file (default: {DEFAULT_CONFIG_PATH})",
    )
    groom_parser.add_argument(
        "--target", default=None, help="Target name, path, or 1-based index"
    )
    groom_parser.add_argument(
        "--hash-ttl-days",
        type=int,
        default=None,
        help="Override hash cache TTL in days (0 = force rehash)",
    )

    sync_parser = subparsers.add_parser(
        "sync", help="Execute reviewed ledger operations."
    )
    sync_parser.add_argument(
        "--review", required=True, help="Path to review ledger file"
    )

    args = parser.parse_args()
    if args.command == "groom":
        run_groom(args)
    elif args.command == "sync":
        run_sync(args)


if __name__ == "__main__":
    main()
