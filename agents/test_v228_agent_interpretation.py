import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone, timedelta
from agent_indicator_interpretation_v228 import interpret, publish, SYMBOLS
NOW=datetime(2026,10,31,2,tzinfo=timezone.utc)
def sample():
    return {"version":"V225.0","research_only":True,"orders_enabled":False,
      "realtime":False,"trade_signals_available":False,"ai_agents_running":False,
      "generated_at_utc":NOW.isoformat(),
      "markets":[{"symbol":s,"close":101.0,"sma50":105.0,"sma200":100.0,
                  "volume20":20.0,"volume_latest":30.0,
                  "trend_label":"SMA50_ABOVE_SMA200"} for s in SYMBOLS]}
class AgentInterpretationTests(unittest.TestCase):
    def test_descriptive_only(self):
        result=interpret(sample(),NOW)
        self.assertEqual(len(result["markets"]),3)
        self.assertEqual(result["markets"][0]["QUANT"]["volume_ratio_20"],1.5)
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["ai_agents_running"])
    def test_inconsistent_trend_rejected(self):
        data=sample();data["markets"][0]["trend_label"]="SMA50_BELOW_SMA200"
        with self.assertRaises(ValueError):interpret(data,NOW)
    def test_stale_rejected(self):
        with self.assertRaises(ValueError):interpret(sample(),NOW+timedelta(hours=9))
    def test_unsafe_rejected(self):
        data=sample();data["orders_enabled"]=True
        with self.assertRaises(ValueError):interpret(data,NOW)
    def test_invalid_input_removes_stale_public_output(self):
        with TemporaryDirectory() as folder:
            source=Path(folder)/"input.json"
            target=Path(folder)/"public.json"
            source.write_text(json.dumps({"orders_enabled":True}),encoding="utf-8")
            target.write_text('{"old":"unsafe"}',encoding="utf-8")
            with self.assertRaises(ValueError):
                publish(source,target)
            self.assertFalse(target.exists())
    def test_missing_source_removes_stale_public_output(self):
        with TemporaryDirectory() as folder:
            source=Path(folder)/"missing.json"
            target=Path(folder)/"public.json"
            target.write_text('{"old":"unsafe"}',encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                publish(source,target)
            self.assertFalse(target.exists())
    def test_source_output_collision_preserves_source(self):
        with TemporaryDirectory() as folder:
            source=Path(folder)/"input.json"
            content=json.dumps(sample())
            source.write_text(content,encoding="utf-8")
            with self.assertRaises(ValueError):
                publish(source,source)
            self.assertEqual(source.read_text(encoding="utf-8"),content)
    def test_valid_input_publishes_research_only(self):
        with TemporaryDirectory() as folder:
            source=Path(folder)/"input.json"
            target=Path(folder)/"public.json"
            data=sample()
            data["generated_at_utc"]=datetime.now(timezone.utc).isoformat()
            source.write_text(json.dumps(data),encoding="utf-8")
            publish(source,target)
            output=json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(output["version"],"V228.0")
            self.assertFalse(output["orders_enabled"])
if __name__=="__main__":unittest.main()
