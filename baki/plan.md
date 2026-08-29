Act as an expert Python engineer. Write a production-ready, single-file command-line utility called `baki` (`baki.py`).

The purpose of `baki` is to provide a deterministic, human-readable, two-stage one-way backup sync using the `xxhash` library (XXH3-128).

DEPENDENCY CONSTRAINT:
The only external library allowed is `xxhash`. All working files are CSV/plain-text. Read configuration with Python's built-in `tomllib` and write flat manifest/telemetry files using the built-in `csv` module.

CORE ARCHITECTURE:

1. CONFIGURATION & CLI INTERFACE
- Look for `settings.toml` in the current working directory.
- Parse `paths.source`, `paths.targets` (list of destination paths/names), `filters.excludes`, and `filters.includes`.
- CLI via `argparse` operating on **one target at a time**:
  * `baki groom [--target <name|path|index>]`: If target is omitted and multiple targets exist in `settings.toml`, prompt user interactively (1/2/3...) to pick one.
  * `baki sync --review <file>`: Execute the review ledger for the specified target.

2. GLOB FILTERS & DIRECTORY HANDLING
- Match relative paths against parsed `excludes` and `includes` glob patterns.
- Explicitly track empty folders. Represent them in manifests with size `0` and an empty string `""` as their hash.

3. MANIFEST GENERATION & SCHEMA (Native sorted flat-text output)
- Save run manifests under `baki_manifests/[target_name]_[YYYY-MM-DD_HH-MM]/`.
- Generate two CSV manifest files per run:
  * `source_manifest.csv` (scanned state of source directory)
  * `target_manifest.csv` (scanned state of selected target directory)
- CSV Columns: `relative_path,size,mtime,xxh3_128,hashed_at`
  * `mtime` and `hashed_at` formatted in ISO-8601 (`YYYY-MM-DDTHH:MM:SSZ` or local ISO-8601).
- Strict lexicographical ordering by `relative_path` to ensure clean `git diff` capability across historical manifests.

4. HASH CACHING & I/O OPTIMIZATION
- Top-level constants configurable at top of `baki.py`:
  * `HASH_CACHE_TTL_DAYS = 30` (TTL window for re-using existing hashes on unchanged files)
  * `HASH_CACHE_MIN_SIZE_BYTES = 1024 * 1024` (1MB threshold; smaller files always re-hashed)
- CLI argument `--hash-ttl-days <N>`:
  * Override cache TTL in days.
  * Setting `0` forces full recalculation from scratch, ignoring historical hashes.
- Cache reuse criteria:
  * File size >= `HASH_CACHE_MIN_SIZE_BYTES`.
  * Previous manifest contains exact match for `relative_path`, `size`, and `mtime`.
  * Time elapsed since previous `hashed_at` <= TTL window.
  * When reused: carry forward `xxh3_128` and the original `hashed_at`.
  * When recalculated or cache expired: re-hash via XXH3-128 and record current timestamp in `hashed_at`.

5. BIT ROT & ANOMALY DETECTION
- Triggered whenever a file is actively hashed (cache expired, forced refresh `--hash-ttl-days 0`, or files < 1MB).
- Flag as `BIT_ROT` if a file's `size` and `mtime` are identical to historical manifest but `xxh3_128` changed.
- If bit rot or hash mismatch anomaly occurs on either side:
  * Comment out the ledger entry with `# [WARNING_BIT_ROT]`.
  * Append telemetry details to `baki_manifests/[target_name]_[YYYY-MM-DD_HH-MM]/badfiles.csv` (columns: `location,relative_path,expected_hash,actual_hash,mtime,size,last_hashed_at`).

6. STAGE 1: THE 'groom' COMMAND
- CLI: `baki groom [--target <name|path|index>] [--hash-ttl-days <int>]`
- Scan source and target, write their respective manifests into the run folder.
- Generate an editable, target-scoped action ledger `baki_review_[target_name].txt` containing a metadata header (source path, target path, manifest timestamp) followed by line-by-line actions:
  * `[COPY] path/to/file`     (New file present on source, missing on target)
  * `[SYNC] path/to/file`     (Modified file on source; size/mtime/hash changed)
  * `[DELETE] path/to/file`   (File missing on source, exists on target)
  * `[MKDIR] path/to/dir`     (Directory present on source, missing on target)
  * `[RMDIR] path/to/dir`     (Directory missing on source, exists on target)
  * `[SKIP] path/to/file`     (Identical files or user-bypassed entries)
  * `# [WARNING_BIT_ROT] [ACTION] path/to/file` (Unsafe changes flagged for manual inspection)

7. STAGE 2: THE 'sync' COMMAND
- CLI: `baki sync --review <file>`
- Read and parse the specified review ledger file (e.g. `baki sync --review baki_review_[target_name].txt`).
- Validate source and target paths from the review header.
- Execute verified operations:
  * Directory creations (`MKDIR`) and directory removals (`RMDIR`).
  * Chunked file copy/sync (`COPY`, `SYNC`) preserving mtime attributes.
  * File removals (`DELETE`).
  * Ignore lines commented with `#` or marked `[SKIP]`.
- Print progress indicator with file counts, transferred bytes, and throughput.
- Robust error handling ensuring failed individual operations do not abort the entire batch unhandled.
