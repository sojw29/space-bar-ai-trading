import json
import tempfile
import unittest
from pathlib import Path
from news_taxonomy_v128 import classify_article,classify_snapshot,main

def article(title,topic="BTC"):
    return {"title":title,"topic":topic,"article_id":"test"}

class NewsTaxonomyTests(unittest.TestCase):
    def test_etf(self):
        self.assertIn("ETF",classify_article(article("Bitcoin ETF inflows"))["categories"])
    def test_inflation(self):
        self.assertIn("INFLATION",classify_article(article("US CPI inflation rises", "MACRO"))["categories"])
    def test_monetary_policy(self):
        self.assertIn("MONETARY_POLICY",classify_article(article("Federal Reserve rate cut"))["categories"])
    def test_security(self):
        self.assertIn("EXCHANGE_SECURITY",classify_article(article("Crypto exchange hack reported"))["categories"])
    def test_network(self):
        self.assertIn("NETWORK",classify_article(article("Ethereum network upgrade"))["categories"])
    def test_token_supply(self):
        self.assertIn("TOKEN_SUPPLY",classify_article(article("Token unlock planned"))["categories"])
    def test_regulation(self):
        self.assertIn("REGULATION",classify_article(article("SEC crypto regulation"))["categories"])
    def test_asset_explicit(self):
        self.assertEqual(classify_article(article("Solana network upgrade"))["explicit_title_asset_mentions"],["SOL"])
    def test_no_ambiguous_sol(self):
        self.assertEqual(classify_article(article("SOL weather satellite"))["explicit_title_asset_mentions"],[])
    def test_unknown_direction(self):
        self.assertEqual(classify_article(article("Bitcoin ETF"))["impact_direction"],"UNKNOWN")
    def test_no_importance_invented(self):
        self.assertIsNone(classify_article(article("Bitcoin ETF"))["importance_score"])
    def test_other(self):
        self.assertEqual(classify_article(article("Unrelated headline"))["categories"],["OTHER_UNCLASSIFIED"])
    def test_snapshot_counts(self):
        result=classify_snapshot({"version":"V127.0","articles":[article("Bitcoin ETF"),article("US CPI","MACRO")]})
        self.assertEqual(result["article_count"],2)
        self.assertEqual(result["category_counts"]["ETF"],1)
    def test_empty_snapshot(self):
        self.assertEqual(classify_snapshot({"version":"V127.0","articles":[]})["article_count"],0)
    def test_invalid_version(self):
        with self.assertRaisesRegex(ValueError,"INVALID_V127_SNAPSHOT"):
            classify_snapshot({"version":"V126.0","articles":[]})
    def test_invalid_topic(self):
        with self.assertRaisesRegex(ValueError,"INVALID_TOPIC"):
            classify_article(article("Bitcoin ETF","DOGE"))
    def test_no_orders(self):
        result=classify_snapshot({"version":"V127.0","articles":[article("Bitcoin ETF")]})
        self.assertFalse(result["live_trading_approved"])
        self.assertEqual(result["orders_submitted_to_exchange"],0)
    def test_deterministic(self):
        data={"version":"V127.0","articles":[article("Bitcoin ETF")]}
        self.assertEqual(classify_snapshot(data),classify_snapshot(data))

if __name__=="__main__":
    unittest.main()
