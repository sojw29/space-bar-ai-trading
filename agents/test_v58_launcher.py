"""V58 localhost desktop launcher lifecycle; does not require a window in CI."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
import space_bar_launcher as launcher


def csv_fixture(path, *, count=80, gap=False):
    start=1700000100-(1700000100%300)
    with open(path,"w",newline="",encoding="utf-8") as fp:
        writer=csv.writer(fp)
        writer.writerow(["timestamp","open","high","low","close","volume"])
        for i in range(count):
            timestamp=start+i*300
            if gap and i>=22:
                timestamp+=300
            writer.writerow([timestamp,100+i/10,101+i/10,99+i/10,100.5+i/10,100+i])


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.file=Path(self.temp.name)/"BTC_5m.csv"
        csv_fixture(self.file)
    def tearDown(self):
        self.temp.cleanup()

    def test_history_validation_fail_closed(self):
        self.assertEqual(launcher.validate_history(self.file),self.file.resolve())
        for reason in ["too_few","gap","missing"]:
            with self.subTest(reason=reason):
                file=Path(self.temp.name)/(reason+".csv")
                if reason=="too_few":csv_fixture(file,count=30)
                if reason=="gap":csv_fixture(file,gap=True)
                with self.assertRaises((ValueError,FileNotFoundError)):
                    launcher.validate_history(file)

    def test_server_start_stop_and_post_denial(self):
        service=launcher.LocalResearchService(port=18581)
        self.addCleanup(service.stop)
        self.assertFalse(service.running)
        self.assertFalse(service.stop())
        with patch.object(launcher, "validate_history", wraps=launcher.validate_history) as check:
            url=service.start(self.file)
            check.assert_called_once()
        self.assertTrue(service.running)
        self.assertEqual(url,"http://127.0.0.1:18581")
        self.assertFalse(service.health()["orders_enabled"])
        with urlopen(url+"/api/v1/agents",timeout=4) as response:
            self.assertEqual(response.status,200)
        with urlopen(url+"/api/v1/market",timeout=4) as response:
            self.assertEqual(response.status,200)
        with urlopen(url+"/office3d",timeout=4) as response:
            self.assertIn(b'PAPER RESEARCH ONLY',response.read())
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(url+"/api/v1/agents",method="POST",data=b'{"BUY":true}'),timeout=3)
        self.assertEqual(error.exception.code,405)
        with self.assertRaises(RuntimeError):
            service.start(self.file)
        self.assertTrue(service.stop())
        self.assertFalse(service.running)
        self.assertFalse(service.stop())

    def test_port_conflict_and_bad_configuration(self):
        for host,port in (("0.0.0.0",18582),("127.0.0.1",80),("127.0.0.1",True)):
            with self.assertRaises(ValueError):
                launcher.LocalResearchService(host=host,port=port)
        a=launcher.LocalResearchService(port=18582)
        b=launcher.LocalResearchService(port=18582)
        self.addCleanup(a.stop)
        a.start(self.file)
        with self.assertRaises(OSError):
            b.start(self.file)
        self.assertFalse(b.running)

    def test_cli_check_does_not_start_gui_or_server(self):
        with patch.object(launcher, "run_gui") as gui:
            self.assertEqual(launcher.main(["--check-history",str(self.file)]),0)
            gui.assert_not_called()

    def test_double_click_entrypoint_has_local_only_disclosure(self):
        cmd=(ROOT/"START_SPACE_BAR_WINDOWS.bat").read_text(encoding="utf-8")
        self.assertIn('cd /d "%~dp0"',cmd)
        self.assertIn("space_bar_launcher.py",cmd)
        self.assertNotIn("live_dashboard_v39",cmd)
        self.assertNotIn("api_key",cmd.lower())

if __name__=="__main__":
    unittest.main(verbosity=2)
