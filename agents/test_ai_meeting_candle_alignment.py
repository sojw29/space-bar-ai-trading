from datetime import datetime, timezone, timedelta
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ohlcv_indicators_v225 import build, indicators, publish
from agent_indicator_interpretation_v228 import interpret

NOW = datetime(2026, 11, 3, 0, 10, tzinfo=timezone.utc)


def response(symbol):
    end = int(NOW.timestamp()*1000) - (300000 if symbol == 'SOLUSDT' else 0)
    rows = [[str(end-(220-i)*300000), '100', '101', '99', '100', '50', '0'] for i in range(220)]
    return {'retCode': 0, 'result': {'list': rows}}


class CandleAlignmentTests(unittest.TestCase):
    def test_one_market_lagging_by_one_bar_is_not_a_coherent_snapshot(self):
        with patch('ohlcv_indicators_v225.datetime') as date:
            date.now.return_value = NOW
            date.fromtimestamp.side_effect = datetime.fromtimestamp
            with self.assertRaisesRegex(ValueError, 'MISALIGNED_MARKET_CANDLES'):
                build(response)

    def test_common_cutoff_excludes_a_bar_that_closes_mid_collection_for_both_venues(self):
        for provider in ('bybit', 'okx'):
            with self.subTest(provider=provider), patch('ohlcv_indicators_v225.datetime') as date:
                started = NOW-timedelta(seconds=1)
                date.now.side_effect = [started, NOW+timedelta(seconds=1)]
                date.fromtimestamp.side_effect = datetime.fromtimestamp
                def fetch(symbol):
                    rows = response('BTCUSDT')['result']['list']
                    if provider=='bybit':return {'retCode':0,'result':{'list':rows}}
                    return {'code':'0','data':[r[:5]+['9000',r[5],'5000','1'] for r in rows]}
                result = build(fetch, provider=provider)
                stamps = {m['last_completed_candle_utc'] for m in result['markets']}
                self.assertEqual(stamps, {(NOW-timedelta(minutes=10)).isoformat()})
                self.assertEqual(result['generated_at_utc'], (NOW+timedelta(seconds=1)).isoformat())
                self.assertEqual(date.now.call_count, 2)

    def test_collection_clock_rollback_and_expiry_before_publication_are_blocked(self):
        for finished, message in ((NOW-timedelta(seconds=1), 'COLLECTION_CLOCK_MOVED_BACKWARD'),
                                   (NOW+timedelta(hours=1, microseconds=1), 'STALE_OR_UNFINISHED_MARKET_CANDLE')):
            with self.subTest(finished=finished), patch('ohlcv_indicators_v225.datetime') as date:
                date.now.side_effect = [NOW, finished]
                date.fromtimestamp.side_effect = datetime.fromtimestamp
                with self.assertRaisesRegex(ValueError, message):
                    build(lambda symbol: response('BTCUSDT'))

    def test_final_one_hour_freshness_boundary_is_inclusive(self):
        with patch('ohlcv_indicators_v225.datetime') as date:
            date.now.side_effect=[NOW,NOW+timedelta(hours=1)]
            date.fromtimestamp.side_effect=datetime.fromtimestamp
            snapshot=build(lambda symbol:response('BTCUSDT'))
        self.assertEqual(snapshot['generated_at_utc'],(NOW+timedelta(hours=1)).isoformat())
        interpret(snapshot,now=NOW+timedelta(hours=1))

    def test_timestamp_fraction_bool_and_shifted_grid_are_rejected_for_both_venues(self):
        for provider in ('bybit','okx'):
            for stamp in (True, 1.5, '1.5', 'not-a-timestamp', '0', str(int(NOW.timestamp()*1000)+1)):
                rows = response('BTCUSDT')['result']['list']
                rows[10][0] = stamp
                if provider=='bybit':data={'retCode':0,'result':{'list':rows}}
                else:data={'code':'0','data':[r[:5]+['9000',r[5],'5000','1'] for r in rows]}
                with self.subTest(provider=provider,stamp=stamp), self.assertRaisesRegex(ValueError,'INVALID_CANDLE_TIMESTAMP'):
                    indicators('BTCUSDT',lambda symbol:data,provider=provider,now=NOW)

    def test_misalignment_discards_old_output_and_never_publishes_partial_snapshot(self):
        with tempfile.TemporaryDirectory() as directory, patch('ohlcv_indicators_v225.datetime') as date:
            date.now.return_value=NOW
            date.fromtimestamp.side_effect=datetime.fromtimestamp
            target=Path(directory)/'indicators.json'
            target.write_text('old snapshot')
            with self.assertRaisesRegex(ValueError,'MISALIGNED_MARKET_CANDLES'):
                publish(target,response)
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(directory).glob('*.tmp')),[])

    def test_marked_snapshot_cannot_bypass_alignment_by_calling_interpretation_directly(self):
        with patch('ohlcv_indicators_v225.datetime') as date:
            date.now.return_value=NOW
            date.fromtimestamp.side_effect=datetime.fromtimestamp
            snapshot=build(lambda symbol:response('BTCUSDT'))
        for stamp in ((NOW-timedelta(minutes=10)).isoformat(), NOW.isoformat(),
                      (NOW-timedelta(hours=2)).isoformat(), '2026-11-03T00:04:01+00:00'):
            snapshot['markets'][2]['last_completed_candle_utc']=stamp
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):interpret(snapshot,now=NOW)


if __name__ == '__main__': unittest.main()
