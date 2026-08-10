import unittest
from pathlib import Path
from backend.capture_matcher import classify_role, make_capture_key, normalized_stem


class CaptureMatcherTests(unittest.TestCase):
    def test_edited_suffix_normalization(self):
        self.assertEqual(normalized_stem("DSC01234-Edit.jpg"), "dsc01234")
        self.assertEqual(normalized_stem("DSC01234_修图.jpg"), "dsc01234")

    def test_folder_roles(self):
        raw={".arw", ".cr3"}
        self.assertEqual(classify_role(Path("旅游/名古屋RAW/DSC1.ARW"),raw,["修图","edited"],["jpg"]),"raw")
        self.assertEqual(classify_role(Path("旅游/名古屋RAW/修图/DSC1.jpg"),raw,["修图","edited"],["jpg"]),"edited")
        self.assertEqual(classify_role(Path("旅游/jpg/DSC1.JPG"),raw,["修图","edited"],["jpg"]),"camera_jpeg")

    def test_capture_key_merges_raw_jpg_and_edit(self):
        common=dict(shot_at="2026-08-10T12:01:02",camera_serial="SER123",camera_model="ILCE-1M2",theme="旅游")
        a=make_capture_key(filename="DSC01234.ARW",relative_path="旅游/名古屋RAW/DSC01234.ARW",**common)
        b=make_capture_key(filename="DSC01234.JPG",relative_path="旅游/jpg/DSC01234.JPG",**common)
        c=make_capture_key(filename="DSC01234-Edit.jpg",relative_path="旅游/名古屋RAW/修图/DSC01234-Edit.jpg",**common)
        self.assertEqual(a,b); self.assertEqual(a,c)

    def test_same_filename_different_time_does_not_merge(self):
        a=make_capture_key(filename="DSC00001.ARW",shot_at="2021-01-01T00:00:00",camera_serial="S",camera_model="M",theme="旅游",relative_path="旅游/a/DSC00001.ARW")
        b=make_capture_key(filename="DSC00001.ARW",shot_at="2026-01-01T00:00:00",camera_serial="S",camera_model="M",theme="旅游",relative_path="旅游/b/DSC00001.ARW")
        self.assertNotEqual(a,b)


if __name__ == "__main__": unittest.main()
