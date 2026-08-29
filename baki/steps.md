# Implementation Steps: baki.py

Single-file CLI backup sync utility with two-stage ledger execution, XXH3-128 hashing, and 30-day hash caching.

## Critical Constraints
- Single-file: `baki.py`.
- Dependencies: standard library + `xxhash` ONLY (`tomllib`, `csv`, `pathlib`, `argparse`, `datetime`, `shutil`).
- Unicode / Encoding: All CSV manifests, badfiles telemetry, and review ledger files MUST be opened and written using `encoding="utf-8"`. Path normalization handles cross-platform unicode filenames without escaping issues.
- No comments in code unless non-obvious "why". Max function length: 50 lines. Max line length: 165 chars. Cyclomatic complexity <= 10.
- All working files: CSV or plain-text ledger.

---

## Step 1: Configuration & CLI Interface
1. Define top-level constants:
   - `HASH_CACHE_TTL_DAYS = 30`
   - `HASH_CACHE_MIN_SIZE_BYTES = 1024 * 1024` (1MB)
   - `CHUNK_SIZE = 1024 * 1024` (1MB chunked reads/writes)
2. Implement TOML configuration parser (`tomllib`):
   - Locate `settings.toml` in CWD.
   - Extract `paths.source`, `paths.targets` (support string paths and `{name, path}` dicts), `filters.excludes`, and `filters.includes`.
3. Implement `argparse` CLI:
   - `groom`: `--target` (optional name/path/index), `--hash-ttl-days` (default 30, `0` = force rehash). Interactive prompt (1/2/3...) if `--target` omitted with multiple targets.
   - `sync`: `--review` (path to ledger file).

## Step 2: Directory Scanner & Filter Engine
1. Traverse full directory trees during `groom` without skipping:
   - Collect all regular files and empty directories (except symlinks/special files).
   - Use Unicode-safe `pathlib.Path` iteration.
   - Both `source_manifest.csv` and `target_manifest.csv` record the complete unfiltered physical state.
2. Implement glob evaluation rule:
   - File is active by default.
   - If path matches any `excludes` pattern -> marked for ignore.
   - If path also matches an `includes` pattern -> `includes` overtakes `excludes` (remains active).

## Step 3: Hash Engine & Cache Lookup
1. Manifest discovery:
   - Find latest past run directory `baki_manifests/[target_name]_[timestamp]/`.
   - Load previous `source_manifest.csv` and `target_manifest.csv` into lookup maps keyed by `relative_path` (UTF-8 decoded).
2. Hash calculation with TTL caching:
   - If file size >= 1MB, same `relative_path`, `size`, `mtime` as past manifest, and `(now - last_hashed_at) <= TTL`: reuse past `xxh3_128` and `hashed_at`.
   - Else: compute XXH3-128 in 1MB chunks, set `hashed_at = now`.
3. Bit rot detection:
   - If actively recomputed hash != past hash for identical `size` and `mtime`, flag record as `BIT_ROT`.

## Step 4: Manifest & Telemetry Generation
1. Write `source_manifest.csv` and `target_manifest.csv` under `baki_manifests/[target_name]_[YYYY-MM-DD_HH-MM]/` using `encoding="utf-8"`.
   - CSV header: `relative_path,size,mtime,xxh3_128,hashed_at`.
   - Strict lexicographical ordering by `relative_path`. Empty folders have `size=0`, empty string hash.
2. If bit rot anomalies detected:
   - Write `badfiles.csv` in manifest directory using `encoding="utf-8"` (`location,relative_path,expected_hash,actual_hash,mtime,size,last_hashed_at`).

## Step 5: Review Ledger Generator (Stage 1)
1. Diff source vs target manifests and evaluate filter rules:
   - `[IGNORED]`: Excluded files/dirs (matches `excludes` and not overridden by `includes`).
   - `[COPY]`: New source file missing on target.
   - `[SYNC]`: Existing file modified on source (size, mtime, or hash differs).
   - `[MISSING]`: File exists on target but is missing on source (review default; never deleted unless manually edited by user to `[DELETE]`).
   - `[MKDIR]`: Source empty/nested directory missing on target.
   - `[RMDIR]`: Empty directory on target that was removed on source.
   - `[SKIP]`: Files identical on both sides.
   - `# [WARNING_BIT_ROT] [ACTION]`: Any action involving a rotted file.
2. Write target-specific ledger `baki_review_[target_name].txt` using `encoding="utf-8"` with metadata header (source, target, timestamp).

## Step 6: Sync Executor (Stage 2)
1. Parse ledger file from `--review`:
   - Validate header (source and target directory paths exist).
   - Filter active actions (ignore `#` comments, `[SKIP]`, `[IGNORED]`, `[MISSING]`).
2. Order execution:
   - 1. Create directories (`MKDIR`).
   - 2. Copy/sync files (`COPY`, `SYNC`) preserving `mtime` using `os.utime`.
   - 3. Remove files (`DELETE` - only executed if user explicitly changed `[MISSING]` to `[DELETE]`).
   - 4. Remove empty directories (`RMDIR` - safely removes only empty dirs).
3. Display progress tracking (processed files, transferred bytes, failure counts).
4. Isolate errors per file so failures log cleanly without crashing the sync run.

## Step 7: Verification & Testing
1. Create mock test suite validating:
   - Manifest sorting and schema.
   - Cache hit/miss and 30-day expiration.
   - Bit rot detection on tampered file.
   - Full cycle: groom -> manual ledger edit -> sync execution.
