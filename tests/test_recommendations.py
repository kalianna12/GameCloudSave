"""Store parsing, anonymous pricing, concurrency, caches, cancellation and safe page actions."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json
import io
import hashlib
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QCoreApplication,QUrl
from PySide6.QtGui import QImage
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
    def picture_fixture(self):
        self.seed_sections()
        row=next(r for r in self.feed._rows['steam'] if r['category']=='new')
        row['images']=['https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/1/header.jpg']
        fixture=Path(self.temp.name)/'fixture.png'
        image=QImage(120,90,QImage.Format_RGB32);image.fill(0xff547890);image.save(str(fixture))
        return row,fixture.read_bytes()

    def test_artwork_cache_hit_is_stable_but_corrupt_repair_changes_url(self):
        row,raw=self.picture_fixture()
        with patch('recommendation_sources.request',return_value=raw) as fetch:
            self.feed._picture('steam',row,self.feed._token,self.feed._cancel);app.processEvents()
            first=row=next(r for r in self.feed._rows['steam'] if r['category']=='new')
            url=first['coverUrl'];file=Path(QUrl(url).toLocalFile());mtime=file.stat().st_mtime_ns
            self.feed._picture('steam',row,self.feed._token,self.feed._cancel);app.processEvents()
            self.assertEqual(next(r for r in self.feed._rows['steam'] if r['category']=='new')['coverUrl'],url)
            self.assertEqual(file.stat().st_mtime_ns,mtime);self.assertEqual(fetch.call_count,1)
            file.write_bytes(b'broken image')
            self.feed._picture('steam',row,self.feed._token,self.feed._cancel);app.processEvents()
            repaired=next(r for r in self.feed._rows['steam'] if r['category']=='new')
            self.assertNotEqual(repaired['coverUrl'],url);self.assertFalse(QImage(str(file)).isNull())
            self.assertEqual(fetch.call_count,2)

    def test_failed_artwork_can_retry_one_card_without_catalog_fetch(self):
        row,raw=self.picture_fixture()
        with patch('recommendation_sources.request',side_effect=TimeoutError):
            self.feed._picture('steam',row,self.feed._token,self.feed._cancel);app.processEvents()
        failed=next(r for r in self.feed._rows['steam'] if r['category']=='new');self.assertTrue(failed['artworkFailed'])
        with patch('recommendation_sources.request',return_value=raw),patch('recommendation_sources.fetch') as catalog:
            self.feed.retryArtwork(row['id'],'new')
            self.idle(lambda:any(r.get('coverUrl','').startswith('file:') and not r.get('artworkFailed') and not r.get('artworkLoading') for r in self.feed._rows['steam'] if r['category']=='new'))
            catalog.assert_not_called()

    def test_image_prune_protects_catalog_images_even_when_old(self):
        folder=self.store.profile/'recommendations';directory=folder/'images';directory.mkdir(parents=True)
        url='https://shared.fastly.steamstatic.com/protected.jpg';name=hashlib.sha256(url.encode()).hexdigest()
        stamp=time.time()-3*86400
        for i in range(162):
            file=directory/((name if i==0 else f'{i:064x}')+'.jpg');file.write_bytes(b'cache')
            os.utime(file,(stamp+i,stamp+i))
        (folder/'steam.json').write_text(json.dumps({'rows':[{'images':[url]}]}),encoding='utf-8')
        self.feed._prune_images(directory)
        self.assertTrue((directory/(name+'.jpg')).is_file())
        self.assertFalse((directory/(f'{1:064x}'+'.jpg')).exists())

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
        self.assertEqual([s['id'] for s in self.feed.sections],['store:new','store:sale','store:popular','store:xbox'])
        self.assertTrue(next(s for s in self.feed.sections if s['id']=='store:sale')['items'])
        self.assertIn('Xbox',next(s for s in self.feed.sections if s['id']=='store:xbox')['message'])
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
        self.assertEqual(next(s for s in self.feed.sections if s['id']=='store:sale')['items'][0]['price'],'¥9.9')
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

    def seed_sections(self):
        self.feed._providers=('steam','xbox');self.feed._started=True
        self.feed._rows={provider:[{**row,'coverUrl':'file:///old-'+row['category']+'.jpg'} for row in rows(provider)] for provider in self.feed._providers}
        self.feed._rows['steam'].append({**self.feed._rows['steam'][0],'category':'new','coverUrl':'file:///old-new.jpg'})

    def test_scoped_refresh_keeps_other_categories_and_existing_artwork(self):
        self.seed_sections();before={s['id']:s for s in self.feed.sections}
        incoming=[{**row,'name':'Updated '+row['name']} for row in self.feed._rows['steam']]
        for row in incoming:row.pop('coverUrl',None)
        entered=threading.Event();gate=threading.Event()
        def fetch(provider):entered.set();assert gate.wait(3);return incoming
        with patch('recommendation_sources.fetch',side_effect=fetch) as fetch_call,patch.object(self.feed,'_artwork') as art:
            try:
                self.feed.refreshSection('store:new');self.idle(entered.is_set)
                current={s['id']:s for s in self.feed.sections}
                self.assertTrue(current['store:new']['loading'])
                for ident in ('store:sale','store:popular','store:xbox'):self.assertEqual(current[ident],before[ident])
                self.assertEqual(current['store:new']['items'][0]['coverUrl'],'file:///old-new.jpg')
            finally:gate.set()
            self.idle()
        fetch_call.assert_called_once_with('steam')
        current={s['id']:s for s in self.feed.sections}
        for ident in ('store:sale','store:popular','store:xbox'):self.assertEqual(current[ident],before[ident])
        self.assertTrue(current['store:new']['items'][0]['name'].startswith('Updated'))
        self.assertEqual(current['store:new']['items'][0]['coverUrl'],'file:///old-new.jpg')
        self.assertEqual({r['category'] for r in art.call_args.args[1]},{'new'})

    def test_scoped_picture_cannot_change_same_game_in_another_category(self):
        self.seed_sections();self.feed._requests['new']=(1,threading.Event())
        self.feed.receive_art('steam','store:steam:1','file:///new.jpg',self.feed._token,'new',1)
        current={s['id']:s for s in self.feed.sections}
        self.assertEqual(current['store:new']['items'][0]['coverUrl'],'file:///new.jpg')
        self.assertEqual(current['store:sale']['items'][0]['coverUrl'],'file:///old-sale.jpg')
        self.feed.receive_art('steam','store:steam:1','file:///late-startup.jpg',self.feed._token)
        current={s['id']:s for s in self.feed.sections}
        self.assertEqual(current['store:new']['items'][0]['coverUrl'],'file:///new.jpg')

    def test_failed_scoped_refresh_keeps_displayed_cards_and_noop_art_emits_nothing(self):
        self.seed_sections();before=list(self.feed._rows['steam'])
        with patch('recommendation_sources.fetch',side_effect=ValueError('offline')),patch.object(self.feed,'_artwork'):
            self.feed.refreshSection('store:new');self.idle()
        self.assertEqual(self.feed._rows['steam'],before)
        changes=[];self.feed.changed.connect(lambda:changes.append(True))
        self.feed.receive_art('steam','store:steam:2','file:///old-popular.jpg',self.feed._token)
        self.assertEqual(changes,[])

    def test_independent_sections_can_refresh_concurrently(self):
        self.seed_sections();entered={p:threading.Event() for p in ('steam','xbox')};gate=threading.Event()
        def fetch(provider):entered[provider].set();assert gate.wait(3);return rows(provider)
        with patch('recommendation_sources.fetch',side_effect=fetch),patch.object(self.feed,'_artwork'):
            try:
                self.feed.refreshSection('store:sale');self.feed.refreshSection('store:xbox')
                self.idle(lambda:all(event.is_set() for event in entered.values()))
                current={s['id']:s for s in self.feed.sections}
                self.assertTrue(current['store:sale']['loading']);self.assertTrue(current['store:xbox']['loading'])
                self.assertFalse(current['store:popular']['loading'])
            finally:gate.set()
            self.idle()

    def test_failed_source_remains_visible_and_immediate_manual_retry_bypasses_fresh_cache(self):
        self.store.settings['recommendations_xbox']=False
        with patch('recommendation_sources.fetch',side_effect=TimeoutError('fixture')),patch.object(self.feed,'_artwork'):
            self.feed.start();self.idle()
        failed=self.feed.sections
        self.assertEqual(len(failed),3)
        self.assertTrue(all(not s['items'] and 'Steam' in s['message'] and s['refresh'] and not s['loading'] for s in failed))
        self.assertLessEqual(self.feed._timer.interval(),60000)
        with patch('recommendation_sources.fetch',return_value=rows('steam')) as fetch,patch.object(self.feed,'_artwork'):
            self.feed.refresh();self.idle();fetch.assert_called_once_with('steam')
        sale=next(s for s in self.feed.sections if s['id']=='store:sale')
        self.assertTrue(sale['items']);self.assertIn('已更新',sale['message']);self.assertEqual(self.feed.status,'')
        self.assertEqual(self.feed._timer.interval(),TTL*1000)
        # A manual refresh must fetch even if the just-written disk cache is fresh.
        with patch('recommendation_sources.fetch',return_value=rows('steam')) as fetch,patch.object(self.feed,'_artwork'):
            self.feed.refreshSection('store:sale');self.idle();fetch.assert_called_once_with('steam')
        sale=next(s for s in self.feed.sections if s['id']=='store:sale')
        self.assertIn('暂无新推荐',sale['message'])

    def test_network_success_is_delivered_even_if_cache_cannot_be_written(self):
        self.store.settings['recommendations_xbox']=False
        original=Path.write_text
        def write(path,*args,**kwargs):
            if path.parent.name=='recommendations':raise PermissionError('fixture read-only cache')
            return original(path,*args,**kwargs)
        with patch('recommendation_sources.fetch',return_value=rows('steam')),patch.object(self.feed,'_artwork'),patch.object(Path,'write_text',write):
            self.feed.start();self.idle()
        self.assertEqual(self.feed.status,'')
        self.assertTrue(next(s for s in self.feed.sections if s['id']=='store:sale')['items'])

    def test_scoped_failure_shows_error_keeps_cards_and_does_not_change_other_notices(self):
        self.seed_sections();before={s['id']:s for s in self.feed.sections}
        with patch('recommendation_sources.fetch',side_effect=TimeoutError('fixture')),patch.object(self.feed,'_artwork'):
            self.feed.refreshSection('store:new');self.idle()
        after={s['id']:s for s in self.feed.sections}
        self.assertEqual(after['store:new']['items'],before['store:new']['items'])
        self.assertIn('保留已有推荐',after['store:new']['message'])
        for ident in ('store:sale','store:popular','store:xbox'):self.assertEqual(after[ident],before[ident])
        with patch('recommendation_sources.fetch',return_value=self.feed._rows['steam']),patch.object(self.feed,'_artwork'):
            self.feed.refreshSection('store:new');self.idle()
        self.assertEqual(self.feed.status,'')

    def test_slow_response_has_an_overall_budget_and_limit(self):
        class Slow(io.BytesIO):
            def read1(self,count):return super().read(min(count,1))
        with patch('recommendation_sources.urlopen',return_value=Slow(b'abc')),patch('recommendation_sources.time.monotonic',side_effect=[0,1,21]):
            with self.assertRaises(TimeoutError):sources.request(sources.STEAM)
        with patch('recommendation_sources.urlopen',return_value=io.BytesIO(b'abc')):
            with self.assertRaises(ValueError):sources.request(sources.STEAM,2)
        with patch('recommendation_sources.urlopen',return_value=io.BytesIO(b'abc')):
            self.assertEqual(sources.request(sources.STEAM,3),b'abc')

    def test_auto_refresh_defers_when_a_manual_request_is_still_running(self):
        self.feed._section_pending.add('new');self.feed._auto_refresh()
        self.assertTrue(self.feed._timer.isActive());self.assertEqual(self.feed._timer.interval(),1000)
        self.feed._section_pending.clear()

    def test_bad_cached_expiration_does_not_discard_other_valid_rows(self):
        cached=rows('steam');cached[0]['expires']='bad'
        self.assertEqual(len(self.feed._cached_rows(cached,TTL+1)),len(cached))

    def test_fresh_but_empty_or_invalid_cache_does_not_hide_the_network(self):
        self.store.settings['recommendations_xbox']=False
        directory=self.store.profile/'recommendations';directory.mkdir()
        (directory/'steam.json').write_text(json.dumps({'version':1,'time':time.time(),'rows':[{'invalid':True}]}))
        with patch('recommendation_sources.fetch',return_value=rows('steam')) as fetch,patch.object(self.feed,'_artwork'):
            self.feed.start();self.idle();fetch.assert_called_once_with('steam')
        self.assertTrue(next(s for s in self.feed.sections if s['id']=='store:sale')['items'])


if __name__=='__main__':unittest.main(verbosity=2)
