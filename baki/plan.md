Act as an expert Python engineer. Write a production-ready, single-file command-line utility called `baki`. 

The purpose of `baki` is to provide a deterministic, human-readable, two-stage one-way backup sync using the `xxhash` library (XXH3-128). 

DEPENDENCY CONSTRAINT: 
The only external library allowed is `xxhash`. Do not use third-party TOML libraries for writing. Use Python's built-in tomllib to read `settings.toml`, and write out the flat manifest text file using csv writer.

CORE ARCHITECTURE:

1. CONFIGURATION & CLI INTERFACE
- On startup, look for a `settings.toml` in the current working directory.
- Parse `paths.source`, `paths.targets` (a list supporting multiple destinations), `filters.excludes`, and `filters.includes` using the built-in `tomllib`.
- Implement a CLI using `argparse` with two subcommands:
  * `baki groom [--target <path>]` (If target is omitted, iterate through all targets found in settings.toml)
  * `baki sync --review <file>`

2. GLOB FILTERS & DIRECTORY HANDLING
- Match files against the parsed `excludes` and `includes` glob patterns.
- Explicitly track empty folders. Log them in manifests using an empty string "" as their hash.

3. MANIFEST GENERATION (Native sorted flat-text output)
- Save manifests under a visible directory named `baki_manifests/[target_name]_[YYYY-MM-DD_HH-MM]/`.
- Generate one file with csv list of columns: relative path, size, mtime, hash (mtime in human readable format, seconds precision or something minimalist)
- Every entry MUST be formatted in common industry standard similar to `relative/path/to/file,589458,2026-08-26_15-43...` and written in strict alphabetical order (lexicographically) by path. This ensures `git diff` works perfectly across runs on the manifest.

4. STAGE 1: THE 'groom' COMMAND
- Scan source and targets. Compare current states against past records to flag data state anomalies.
- Generate an editable, text-based action ledger called `baki_review.txt` listing files line-by-line using action tokens:
  * [COPY] path/to/file     (New file on source)
  * [SYNC] path/to/file     (Legitimate user edit on source; size/mtime changed)
  * [DELETE] path/to/file   (File deleted from source)
  * [MKDIR] path/to/dir     (Missing target folder structure)
  * [RMDIR] path/to/dir     (Orphaned target folder structure)
  * [SKIP] path/to/file     (Placeholder or manually bypassed by user)

5. BIT ROT PROTECTION & SAFETY
- A file is flagged as ROTTED if its size/mtime matches its history but its XXH3-128 hash changed unexpectedly.
- If rotted on either or both sides, comment out its line in `baki_review.txt` with a `# [WARNING_BIT_ROT]` comment.
- Simultaneously log full error telemetry details to a clean text-based file named `badfiles.csv` so human can review damaged paths and manually change the action token to force an overwrite if needed.

6. STAGE 2: THE 'sync' COMMAND
- Read and parse the modified `baki_review.txt`.
- Safely execute the exact copies, directory structures, and deletions requested.
- Print clear progress bars or logs showing file counts and chunk-processing milestones.
- Ensure strict error handling for file I/O operations and missing paths.
