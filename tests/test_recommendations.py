"""Store parsing, anonymous pricing, concurrency, caches, cancellation and safe page actions."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QCoreApplication
from services import Store, ROOT
from recommendations import Recommendations, TTL
import recommendation_sources as sources

app=QCoreApplication.instance() or QCoreApplication([])


def steam_item(ident=1, **extra):
    return {'id':ident,'type':0,'name':'Fixture game','windows_available':True,'final_price':990,
            'original_price':1990,'currency':'CNY','discount_percent':50,**extra}


def rows(provider):
    if provider=='steam':return sources.steam_rows({'specials':{'items':[steam_item()]},'top_sellers':{'items':[steam_item(2)]}})
    return [{'id':'store:xbox:ABCDEF123456','name':'Xbox fixture','provider':'xbox','category':'xbox','images':[],
             'platformLabel':'Xbox 港区','page':'https://www.xbox.com/zh-HK/games/store/-/ABCDEF123456','price':'HK$10','originalPrice':'','discount':0,'expires':0}]


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data')
        self.store=Store(self.temp.name,'recommend-test')
        self.feed=Recommendations(self.store)
    def tearDown(self):
        self.feed.shutdown();self.feed._pool.shutdown(wait=True);self.feed._images.shutdown(wait=True)
        app.processEvents();self.temp.cleanup()
    def idle(self, condition=None):
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            app.processEvents();time.sleep(.002)
            if condition() if condition else not self.feed.loading:return
        self.fail('Feed did not reach expected state')
    def test_steam_has_correct_currency_dedup_and_excludes_non_windows_and_bundles(self):
        output=sources.steam_rows({'specials':{'items':[steam_item(),steam_item(),steam_item(2,type=1),steam_item(3,windows_available=False)]}})
        self.assertEqual(len(output),1)
        self.assertEqual(output[0]['price'],'¥9.9');self.assertEqual(output[0]['originalPrice'],'¥19.9')
        self.assertEqual(output[0]['discount'],50);self.assertTrue(output[0]['page'].endswith('/1/'))
    def test_unknown_price_is_not_treated_as_free(self):
        row=sources.steam_rows({'new_releases':{'items':[steam_item(final_price=None)]}})[0]
        self.assertEqual(row['price'],'')
        self.assertEqual(sources.price(0,'CNY'),'免费');self.assertEqual(sources.price(-1,'HKD'),'')
    def test_non_game_promotion_and_zero_discount_not_shown_as_sale(self):
        with self.assertRaises(ValueError):sources.steam_rows({'specials':{'items':[steam_item(discount_percent=0)]}})
    def test_xbox_preserves_catalog_order_and_regular_price_not_membership_price(self):
        game={'title':'Fixture','productKind':'Game','availableOn':['PC','XboxSeriesX'],
              'images':{'poster':{'url':'https://store-images.s-microsoft.com/image/test'}},
              'specificPrices':{'purchaseable':[{'listPrice':1,'currency':'HKD','eligibilityInfo':{'eligibility':'Subscriber'}},
                                                {'listPrice':80,'msrp':100,'currency':'HKD','discountPercentage':20,'eligibilityInfo':{'eligibility':'None'}}]}}
        state={'core2':{'channels':{'channelData':{'x':{'data':{'products':[{'productId':'ABCDEF123456'}]}}}},'products':{'productSummaries':{'ABCDEF123456':game}}}}
        output=sources.xbox_rows('<script>window.__PRELOADED_STATE__ = '+json.dumps(state)+';doNotExecute()</script>')
        self.assertEqual(output[0]['price'],'HK$80');self.assertEqual(output[0]['discount'],20)
        self.assertEqual(output[0]['platformLabel'],'PC / Xbox 港区')
    def test_invalid_xbox_html_fails_without_evaluating_scripts(self):
        with self.assertRaises(ValueError):sources.xbox_rows('<script>alert(1)</script>')
    def test_links_and_image_sources_are_bounded(self):
        for url in ['javascript:alert(1)','https://store.steampowered.com.evil.test/app/1/','https://www.xbox.com/zh-HK/games/store/-/../']:
            self.assertFalse(sources.valid_page(url))
        self.assertFalse(sources.image_url('https://example.com/private'))
        self.assertFalse(sources.image_url('file:///C:/Windows/test.jpg'))
    def test_default_on_and_invalid_preferences_rejected(self):
        self.assertEqual(self.feed.enabled_providers(),('steam','xbox'))
        with self.assertRaises(ValueError):self.store.save_settings({'recommendations_enabled':'true'})
    def test_sources_start_concurrently_and_failed_source_keeps_success(self):
        entered={p:threading.Event() for p in ('steam','xbox')};gate=threading.Event()
        def fetch(provider):
            entered[provider].set();assert gate.wait(3)
            if provider=='xbox':raise ValueError('offline')
            return rows(provider)
        with patch('recommendation_sources.fetch',side_effect=fetch),patch.object(self.feed,'_artwork'):
            try:
                start=time.monotonic();self.feed.start()
                self.assertLess(time.monotonic()-start,.1)
                self.idle(lambda:all(event.is_set() for event in entered.values()))
            finally:gate.set()
            self.idle()
        self.assertEqual([s['id'] for s in self.feed.sections],['store:sale','store:popular'])
        self.assertIn('Xbox',self.feed.status)
    def test_disabling_during_request_ignores_late_results_and_cache_write(self):
        gate=threading.Event();entered=threading.Event()
        def fetch(provider):
            entered.set();assert gate.wait(3);return rows(provider)
        with patch('recommendation_sources.fetch',side_effect=fetch),patch.object(self.feed,'_artwork'):
            try:
                self.feed.start();self.idle(entered.is_set)
                self.store.settings['recommendations_enabled']=False;self.feed.sync()
            finally:gate.set()
            self.feed._pool.shutdown(wait=True);app.processEvents()
        self.assertEqual(self.feed.sections,[])
        self.assertFalse((self.store.profile/'recommendations/steam.json').exists())
    def test_fresh_cache_avoids_network_and_expired_prices_are_hidden(self):
        self.store.settings['recommendations_xbox']=False
        directory=self.store.profile/'recommendations';directory.mkdir()
        (directory/'steam.json').write_text(json.dumps({'version':1,'time':time.time(),'rows':rows('steam')}))
        with patch('recommendation_sources.fetch',side_effect=AssertionError('Fresh cache must not fetch')),patch.object(self.feed,'_artwork'):
            self.feed.start();self.idle()
        self.assertEqual(self.feed.sections[0]['items'][0]['price'],'¥9.9')
        stale=self.feed._cached_rows(rows('steam'),TTL+1)
        self.assertEqual(stale[0]['price'],'价格待刷新');self.assertEqual(stale[0]['discount'],0)
        expired=rows('steam');expired[0]['expires']=time.time()-1
        self.assertEqual(len(self.feed._cached_rows(expired,TTL+1)),1)
    def test_page_open_only_uses_current_feed_rows(self):
        self.feed._providers=('steam',);self.feed._rows={'steam':rows('steam')}
        with patch('recommendations.QDesktopServices.openUrl',return_value=True) as opened:
            self.assertFalse(self.feed.open('https://example.com'))
            self.assertTrue(self.feed.open('store:steam:1'))
            self.assertEqual(opened.call_args.args[0].host(),'store.steampowered.com')
    def test_artwork_deduplicates_games_repeated_in_multiple_sections(self):
        repeated=rows('steam');repeated.append({**repeated[0],'category':'new'})
        with patch.object(self.feed._images,'submit') as submit:
            self.feed._artwork('steam',repeated,1,threading.Event())
        self.assertEqual(submit.call_count,2)


if __name__=='__main__':unittest.main(verbosity=2)
