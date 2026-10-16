from datetime import datetime
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from time_display import local_time


class LocalTimeDisplay(unittest.TestCase):
    def test_offset_timestamps_use_computer_timezone(self):
        for value in ('2026-10-16T12:53:17+00:00', '2026-10-16T12:53:17Z',
                      '2026-10-16T20:53:17+08:00', '2026-10-16T07:53:17-05:00',
                      '2026-10-16T23:53:17.123456789Z'):
            with self.subTest(value=value):
                expected = datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone().strftime('%Y-%m-%d %H:%M:%S')
                self.assertEqual(local_time(value), expected)

    def test_equivalent_instants_display_identically(self):
        self.assertEqual(local_time('2026-10-16T12:53:17Z'), local_time('2026-10-16T20:53:17+08:00'))

    def test_legacy_local_dates_and_unknown_values_are_preserved(self):
        self.assertEqual(local_time('2026-10-16T20:53:17'), '2026-10-16 20:53:17')
        self.assertEqual(local_time('2026-10-16'), '2026-10-16')
        self.assertEqual(local_time(''), '')
        self.assertEqual(local_time('unknown timestamp'), 'unknown timestamp')


if __name__ == '__main__':
    unittest.main()
