import os
import shutil
import tempfile
import unittest
from pathlib import Path

import baki


class TestBaki(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="baki_test_"))
        self.src_dir = self.test_dir / "src"
        self.dst_dir = self.test_dir / "dst"
        self.dst2_dir = self.test_dir / "dst2"
        self.src_dir.mkdir(parents=True)
        self.dst_dir.mkdir(parents=True)
        self.dst2_dir.mkdir(parents=True)
        self.manifests_root = self.test_dir / "baki_manifests"

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_glob_filtering(self):
        self.assertTrue(baki.is_active_path("doc/notes.txt", ["*.tmp"], []))
        self.assertFalse(baki.is_active_path("cache/data.tmp", ["*.tmp"], []))
        self.assertFalse(
            baki.is_active_path("node_modules/pkg/index.js", ["node_modules/*"], [])
        )
        self.assertTrue(
            baki.is_active_path(
                "node_modules/pkg/app.important.js",
                ["node_modules/*"],
                ["*.important.js"],
            )
        )

    def test_tiered_ttl_caching(self):
        large_file = self.src_dir / "large.bin"
        large_file.write_bytes(b"A" * (1024 * 1024 + 10))
        small_file = self.src_dir / "small.txt"
        small_file.write_text("tiny text", encoding="utf-8")

        entries_1, bad_1, stats_1 = baki.build_manifest(self.src_dir, {}, None, "src")
        self.assertEqual(len(entries_1), 2)
        self.assertEqual(stats_1.rehashed_count, 2)
        self.assertEqual(stats_1.cached_count, 0)

        cached = {e.rel_path: e for e in entries_1}
        entries_2, bad_2, stats_2 = baki.build_manifest(
            self.src_dir, cached, None, "src"
        )
        self.assertEqual(stats_2.cached_count, 2)
        self.assertEqual(stats_2.rehashed_count, 0)

    def test_cross_target_and_subfolder_manifest_reuse(self):
        sub_dir = self.src_dir / "sub"
        sub_dir.mkdir()
        (sub_dir / "file_in_sub.bin").write_bytes(b"subfolder content" * 100)
        (self.src_dir / "root_file.txt").write_text("root file", encoding="utf-8")

        sub_entries, _, sub_stats = baki.build_manifest(sub_dir, {}, None, "sub")
        sub_slug = baki.path_to_slug(sub_dir)
        sub_csv = self.manifests_root / sub_slug / "2026-08-29_20-00-00.csv"
        baki.write_manifest_csv(sub_csv, sub_dir, sub_entries, sub_stats)

        parent_cache = baki.load_manifest_cache_for_path(
            self.manifests_root, self.src_dir
        )
        self.assertIn("sub/file_in_sub.bin", parent_cache)

        parent_entries, _, parent_stats = baki.build_manifest(
            self.src_dir, parent_cache, None, "src"
        )
        self.assertEqual(parent_stats.cached_count, 1)
        self.assertEqual(parent_stats.rehashed_count, 1)

        src_slug = baki.path_to_slug(self.src_dir)
        src_csv = self.manifests_root / src_slug / "2026-08-29_20-05-00.csv"
        baki.write_manifest_csv(src_csv, self.src_dir, parent_entries, parent_stats)

        targetB_cache = baki.load_manifest_cache_for_path(
            self.manifests_root, self.src_dir
        )
        self.assertIn("sub/file_in_sub.bin", targetB_cache)
        self.assertIn("root_file.txt", targetB_cache)

        _, _, targetB_src_stats = baki.build_manifest(
            self.src_dir, targetB_cache, None, "src"
        )
        self.assertEqual(targetB_src_stats.cached_count, 2)
        self.assertEqual(targetB_src_stats.rehashed_count, 0)

    def test_bit_rot_detection(self):
        test_file = self.src_dir / "data.bin"
        test_file.write_bytes(b"Initial content")
        stat1 = test_file.stat()

        entries_1, _, _ = baki.build_manifest(self.src_dir, {}, None, "src")
        cached = {e.rel_path: e for e in entries_1}

        test_file.write_bytes(b"Tampered contnt")
        os.utime(test_file, (stat1.st_atime, stat1.st_mtime))

        entries_2, bad_2, _ = baki.build_manifest(self.src_dir, cached, 0, "src")
        self.assertEqual(len(bad_2), 1)
        self.assertEqual(bad_2[0].rel_path, "data.bin")
        self.assertTrue(entries_2[0].is_rot)

    def test_full_groom_and_sync_cycle(self):
        (self.src_dir / "file1.txt").write_text("file 1 content", encoding="utf-8")
        (self.src_dir / "sub").mkdir()
        (self.src_dir / "sub" / "file2.txt").write_text(
            "file 2 content", encoding="utf-8"
        )
        (self.src_dir / "empty_dir").mkdir()

        (self.dst_dir / "old_to_delete.txt").write_text("old file", encoding="utf-8")
        (self.dst_dir / "to_restore.txt").write_text(
            "restored backup", encoding="utf-8"
        )

        src_entries, _, src_stats = baki.build_manifest(self.src_dir, {}, None, "src")
        dst_entries, _, dst_stats = baki.build_manifest(self.dst_dir, {}, None, "dst")

        src_manifest = (
            self.manifests_root
            / baki.path_to_slug(self.src_dir)
            / "2026-08-29_20-00-00.csv"
        )
        dst_manifest = (
            self.manifests_root
            / baki.path_to_slug(self.dst_dir)
            / "2026-08-29_20-00-00.csv"
        )
        baki.write_manifest_csv(src_manifest, self.src_dir, src_entries, src_stats)
        baki.write_manifest_csv(dst_manifest, self.dst_dir, dst_entries, dst_stats)

        ledger_path = self.test_dir / "baki_review_t1.txt"
        baki.generate_ledger(
            src_entries,
            dst_entries,
            [],
            [],
            self.src_dir,
            self.dst_dir,
            src_manifest,
            dst_manifest,
            ledger_path,
        )

        ledger_content = ledger_path.read_text(encoding="utf-8")
        self.assertIn("[WRITE] file1.txt", ledger_content)
        self.assertIn("[WRITE] sub/file2.txt", ledger_content)
        self.assertIn("[MKDIR] empty_dir", ledger_content)
        self.assertIn("[MISSING] old_to_delete.txt", ledger_content)
        self.assertIn("[MISSING] to_restore.txt", ledger_content)

        modified_ledger = ledger_content.replace(
            "[MISSING] old_to_delete.txt", "[DELETE] old_to_delete.txt"
        )
        modified_ledger = modified_ledger.replace(
            "[MISSING] to_restore.txt", "[RESTORE] to_restore.txt"
        )
        ledger_path.write_text(modified_ledger, encoding="utf-8")

        baki.execute_sync_ledger(ledger_path)

        self.assertTrue((self.dst_dir / "file1.txt").exists())
        self.assertTrue((self.dst_dir / "sub" / "file2.txt").exists())
        self.assertTrue((self.dst_dir / "empty_dir").is_dir())
        self.assertFalse((self.dst_dir / "old_to_delete.txt").exists())
        self.assertTrue((self.src_dir / "to_restore.txt").exists())
        self.assertEqual(
            (self.src_dir / "to_restore.txt").read_text(encoding="utf-8"),
            "restored backup",
        )

        report_file = self.test_dir / "baki_postsync_t1.txt"
        self.assertTrue(report_file.exists())


if __name__ == "__main__":
    unittest.main()
