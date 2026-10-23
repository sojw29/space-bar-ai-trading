"""V57 render performance controls stay UI-only, bounded, accessible and read-only."""
import unittest
from pathlib import Path
HTML=Path(__file__).resolve().parent.parent/"web"/"office_3d.html"
class V57Quality(unittest.TestCase):
    def setUp(self):
        self.html=HTML.read_text(encoding="utf-8")
    def test_accessible_quality_controls_and_render_metrics(self):
        for part in ('id="performance-panel"','id="quality-controls"',
                     'data-quality="low"','data-quality="balanced"','data-quality="high"',
                     'aria-pressed="true"','id="perf-state"','id="perf-fps"',
                     'id="perf-resolution"','const qualityCaps={low:1,balanced:1.5,high:2}',
                     'function activePixelRatio()','renderer.setPixelRatio(activePixelRatio())',
                     'Math.round(performanceFrameCount*1000/elapsed)',
                     'qualityMode=button.dataset.quality'):
            self.assertIn(part,self.html)
    def test_pause_reset_and_no_trade_regression(self):
        for part in ('function stopRendering()','resetPerformanceSample();',
                     'if(document.hidden)stopRendering();',
                     'setRenderState("WebGL 오류")',
                     'function resetResearch(reason)','function verifyEnvelope(payload)',
                     'PAPER RESEARCH ONLY'):
            self.assertIn(part,self.html)
        for dangerous in ('innerHTML=', 'api/v1/orders', 'createOrder(',
                          'apiKey', 'Math.random()'):
            self.assertNotIn(dangerous,self.html)
if __name__=="__main__":
    unittest.main(verbosity=2)
