"""Offline regression tests for V163 historical OHLCV ingestion."""
import math
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent))
import history


class HistoryIntegrityTests(unittest.TestCase):
    def test_reject_nonfinite_values(self):
        valid = ["300000", "10", "11", "9", "10", "2"]
        for column in range(1, 6):
            with self.subTest(column=column):
                for value in ("nan", "inf", "-inf"):
                    row = valid.copy()
                    row[column] = value
                    candles = {}
                    history.add_rows(candles, [row], 300, 301)
                    self.assertEqual(candles, {})

    def test_accept_valid_row(self):
        candles = {}
        added = history.add_rows(candles, [["300000", "10", "11", "9", "10", "2"]], 300, 301)
        self.assertEqual(added, 1)
        self.assertTrue(all(math.isfinite(x) for x in candles[300]))


    def test_missing_count_includes_requested_window_edges(self):
        # Requested minutes: 60, 120, 180, 240, 300, 360.
        # Observed: 120, 180, 300 => one leading, internal, trailing gap.
        rows = [[120], [180], [300]]
        self.assertEqual(history.count_missing_candles(rows, 60, 420), (1, 1, 1))
        self.assertEqual(history.count_missing_candles([[60], [120], [180]], 60, 240), (0, 0, 0))
        self.assertEqual(history.count_missing_candles([[60], [120]], 60, 240), (0, 0, 1))
        self.assertEqual(history.count_missing_candles([], 60, 240), (0, 0, 3))

    def test_collection_rejects_even_one_missing_minute_before_save(self):
        start = datetime(2026, 1, 2, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        ts = int(start.timestamp())
        complete = [[str((ts+i*60)*1000), "10", "11", "9", "10", "2"] for i in range(1440)]
        for missing in (0, 720, 1439):
            with self.subTest(missing=missing), patch.object(history, "download_zip", return_value=complete[:missing]+complete[missing+1:]), patch.object(history, "save_csv") as save:
                with self.assertRaisesRegex(RuntimeError, "incomplete history"):
                    history.collect_symbol("BTCUSDT", start, end)
                save.assert_not_called()

    def test_complete_collection_saves_all_timeframes(self):
        start = datetime(2026, 1, 2, tzinfo=timezone.utc)
        ts = int(start.timestamp())
        rows = [[str((ts+i*60)*1000), "10", "11", "9", "10", "2"] for i in range(1440)]
        with patch.object(history, "download_zip", return_value=rows), patch.object(history, "save_csv") as save:
            history.collect_symbol("BTCUSDT", start, start+timedelta(days=1))
        self.assertEqual([len(call.args[2]) for call in save.call_args_list], [1440, 288, 96])

    def test_publication_window_excludes_known_unpublished_archive(self):
        now = datetime(2026, 11, 2, 9, 20, tzinfo=timezone.utc)
        start, end = history.collection_window(now)
        self.assertEqual(end, datetime(2026, 10, 26, tzinfo=timezone.utc))
        self.assertEqual(end-start, timedelta(days=365))
        self.assertNotEqual(history.PUBLICATION_DELAY_DAYS, 0)
        self.assertLess(end, datetime(2026, 10, 28, tzinfo=timezone.utc))
        local = now.astimezone(timezone(timedelta(hours=9)))
        self.assertEqual(history.collection_window(local), (start,end))
        with self.assertRaisesRegex(ValueError,"NAIVE_NOW"):
            history.collection_window(now.replace(tzinfo=None))

    def test_aggregation_rejects_duplicate_or_unsorted_minutes(self):
        valid=[[i*60,10+i,12+i,9+i,11+i,2] for i in range(5)]
        duplicate=[valid[0],valid[1],valid[1],valid[3],valid[4]]
        unsorted=[valid[1],valid[0],*valid[2:]]
        for rows in (duplicate,unsorted):
            with self.subTest(rows=rows):
                with self.assertRaisesRegex(ValueError,"INVALID_MINUTE_ORDER"):
                    history.aggregate_candles(rows,5)

    def test_aggregation_rejects_invalid_timeframe_and_grid(self):
        rows=[[0,10,12,9,11,2]]
        for timeframe in (0,-1,True,5.0,"5"):
            with self.subTest(timeframe=timeframe):
                with self.assertRaisesRegex(ValueError,"INVALID_TIMEFRAME"):
                    history.aggregate_candles(rows,timeframe)
        for timestamp in (30,-60,True,60.0,"60"):
            with self.subTest(timestamp=timestamp):
                with self.assertRaisesRegex(ValueError,"INVALID_MINUTE_TIMESTAMP"):
                    history.aggregate_candles([[timestamp,10,12,9,11,2]],5)

    def test_aggregation_preserves_ohlcv_and_drops_incomplete_bucket(self):
        complete=[[i*60,10+i,12+i,9+i,11+i,i+1] for i in range(5)]
        self.assertEqual(history.aggregate_candles(complete,5),[[0,10,16,9,15,15]])
        later=[[300+i*60,20,22,19,21,2] for i in range(5)]
        self.assertEqual(history.aggregate_candles(complete[:2]+complete[3:]+later,5),[[300,20,22,19,21,10]])
        self.assertEqual(history.aggregate_candles([],5),[])

    def test_identical_archive_overlap_is_idempotent(self):
        candles={}
        row=["300000","10","11","9","10","2"]
        self.assertEqual(history.add_rows(candles,[row],300,360),1)
        before={key:list(value) for key,value in candles.items()}
        equivalent=["300000","10.0","11.00","9.0","10.0","2.00"]
        self.assertEqual(history.add_rows(candles,[equivalent],300,360),0)
        self.assertEqual(candles,before)

    def test_conflicting_archive_overlap_preserves_existing_candle(self):
        row=["300000","10","11","9","10","2"]
        for column,value in ((1,"10.5"),(2,"12"),(3,"8"),(4,"10.5"),(5,"3")):
            with self.subTest(column=column):
                candles={}
                history.add_rows(candles,[row],300,360)
                before={key:list(value) for key,value in candles.items()}
                conflict=row.copy()
                conflict[column]=value
                with self.assertRaisesRegex(RuntimeError,"CONFLICTING_CANDLE"):
                    history.add_rows(candles,[conflict],300,360)
                self.assertEqual(candles,before)


    def test_collection_conflict_stops_before_any_csv_save(self):
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        end=datetime(2026,2,1,tzinfo=timezone.utc)
        stamp=str(int(start.timestamp())*1000)
        monthly=[[stamp,"10","11","9","10","2"]]
        daily=[[stamp,"10","12","9","10","2"]]
        with patch.object(history,"download_zip",side_effect=[monthly,daily]),patch.object(history,"save_csv") as save:
            with self.assertRaisesRegex(RuntimeError,"CONFLICTING_CANDLE"):
                history.collect_symbol("BTCUSDT",start,end)
            save.assert_not_called()


    def test_atomic_csv_save_replaces_symlink_not_its_target(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            unrelated=root/"unrelated.csv"
            unrelated.write_bytes(b"preserve me")
            target=root/"BTC_1m.csv"
            target.symlink_to(unrelated)
            with patch.object(history,"DATA_DIR",directory):
                history.save_csv("BTCUSDT",1,[[60,10,11,9,10,2]])
            self.assertEqual(unrelated.read_bytes(),b"preserve me")
            self.assertFalse(target.is_symlink())
            self.assertEqual(target.read_text().splitlines(),["timestamp,open,high,low,close,volume","60,10,11,9,10,2"])
            self.assertEqual(list(root.glob(".history-*.tmp")),[])

    def test_failed_csv_save_preserves_existing_data_and_cleans_temp(self):
        for failure in ("rows","replace"):
            with self.subTest(failure=failure),TemporaryDirectory() as directory:
                root=Path(directory)
                target=root/"BTC_1m.csv"
                target.write_bytes(b"previous complete history")
                def failing_rows():
                    yield [60,10,11,9,10,2]
                    raise OSError("injected row write failure")
                rows=failing_rows() if failure=="rows" else [[60,10,11,9,10,2]]
                with patch.object(history,"DATA_DIR",directory),patch.object(history.os,"replace",side_effect=OSError("injected replace failure")):
                    with self.assertRaisesRegex(OSError,"injected"):
                        history.save_csv("BTCUSDT",1,rows)
                self.assertEqual(target.read_bytes(),b"previous complete history")
                self.assertEqual(list(root.glob(".history-*.tmp")),[])



if __name__ == "__main__":
    unittest.main()
