import gc
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QSignalSpy
from services import Store,ROOT
from main import Bridge
from ai_match import identify_game
from matching import scan
app=QCoreApplication([])

class Iteration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'test-data')
        self.store=Store(Path(self.temp.name),'iteration-test')
        self.ident=str(uuid.uuid4())
        self.store.games=[{'id':self.ident,'name':'中文游戏','installed':True,'cover':''}]
        self.save=Path(self.temp.name)/'save'; self.save.mkdir()
        (self.save/'save.json').write_text('{}')
        self.store.save_game(self.ident,{'save_dir':str(self.save)})
        self.bridge=Bridge(self.store); self.bridge.timer.stop()
    def tearDown(self):
        self.bridge.layoutTimer.stop(); self.bridge.pool.shutdown(wait=True)
        gc.collect(); self.temp.cleanup()
    def wait(self,seconds=.5):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            app.processEvents(); time.sleep(.005)
    def test_layout_and_settings_do_not_reset_game_model(self):
        spy=QSignalSpy(self.bridge.gamesChanged)
        self.bridge.saveLayout({'cover_size':253,'columns':0})
        self.wait()
        self.assertEqual(spy.count(),0)
        self.assertEqual(self.store.settings['cover_size'],253)
        self.bridge.saveSettings({'cloud_folder':'电脑/GameCloudSave'})
        self.wait()
        self.assertEqual(spy.count(),0)
    def test_transfer_states_distinguish_failure(self):
        states=[]
        self.bridge.transfersChanged.connect(lambda:states.append(self.bridge.transferStates.get(self.ident)))
        with patch.object(self.store,'upload',side_effect=ValueError('offline')):
            self.bridge.cloudSave(self.ident); self.wait()
        self.assertEqual(states,['saving','uploading','failed'])
        self.assertTrue(Path(self.store.history(self.ident)[0]['archive_path']).exists())
    def test_transfer_success(self):
        with patch.object(self.store,'upload',return_value=None):
            self.bridge.cloudSave(self.ident); self.wait()
        self.assertEqual(self.bridge.transferStates[self.ident],'success')
    def test_folder_preview_does_not_block_navigation(self):
        self.bridge.previewCloud('',{'Name':'电脑','IsDir':True},{})
        self.assertFalse(self.bridge.busy)
        self.assertEqual(self.bridge.cloudPreview['name'],'电脑')
    def test_dav_listing_includes_files_and_folders(self):
        self.store.save_settings({'password':'dummy'})
        rows=[{'Name':'save.zip','IsDir':False,'Size':12},{'Name':'folder','IsDir':True,'Size':-1}]
        responses=[subprocess.CompletedProcess([],0,'obscured',''),subprocess.CompletedProcess([],0,json.dumps(rows),'')]
        with patch('services.run_process',side_effect=responses) as run:
            result=self.store.rclone('list')
        self.assertEqual([r['Name'] for r in result],['folder','save.zip'])
        self.assertNotIn('--dirs-only',run.call_args.args[0])
    def test_text_preview_is_bounded(self):
        with patch.object(self.store,'rclone',return_value='{"进度":42}') as run:
            result=self.store.preview_cloud('电脑',{'Name':'save.json','Size':12,'IsDir':False})
        self.assertIn('进度',result['text'])
        self.assertEqual(run.call_args.args[0][-2:],['--head','32768'])
    def test_direct_launch_preserves_arguments_without_playnite(self):
        exe=Path(self.temp.name)/'Game With Spaces.exe'; exe.write_bytes(b'fixture')
        self.store.save_game(self.ident,{'launch_mode':'direct','exe':str(exe),'arguments':'--language zh-CN','working_dir':str(exe.parent)})
        with patch('services.subprocess.Popen') as start: self.store.launch(self.ident)
        self.assertIsInstance(start.call_args.args[0],str)
        self.assertIn('--language zh-CN',start.call_args.args[0])
        self.assertNotIn('Playnite',start.call_args.args[0])
        self.assertNotIn('shell',start.call_args.kwargs)
    def test_ai_hints_cannot_escape_roots(self):
        response={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'english_name':'Game','aliases':[],'hints':[{'root':'local','relative':'../secret'}]})}}]}
        with patch('ai_match.urlopen',return_value=io.BytesIO(json.dumps(response).encode())):
            with self.assertRaises(ValueError): identify_game('中文名','Game','dummy','test')
    def test_matching_keeps_not_found_separate_from_existing(self):
        identity={'english_name':'Game','aliases':[],'hints':[{'root':'local','relative':'save','reason':'known'},{'root':'local','relative':'missing','reason':'unknown'}],'note':''}
        result,checked=scan('中文游戏',{},identity,{'local':Path(self.temp.name)})
        self.assertEqual(len(result),1)
        self.assertEqual([r['exists'] for r in checked],[True,False])
    def test_model_failure_retains_local_candidates(self):
        self.store.save_settings({'ai_enabled':True,'ai_key':'dummy'})
        with patch('ai_match.identify_game',side_effect=ValueError('DeepSeek：账户余额不足')):
            result=self.store.match_game(self.ident)
        self.assertEqual(result['status'],'failed')
        self.assertIn('余额不足',result['message'])
    def test_confirmed_match_is_persisted(self):
        chosen=Path(self.temp.name)/'chosen-save'; chosen.mkdir()
        self.bridge.receiveMatch({'id':self.ident,'name':'中文游戏','status':'review','candidates':[{'path':str(chosen)}]})
        self.bridge.applyMatch(self.ident,str(chosen)); self.wait()
        self.assertEqual(self.store.local[self.ident]['save_dir'],str(chosen))
        self.assertEqual(self.bridge.matchResults[0]['status'],'applied')
        self.assertEqual(Store(self.store.root,'iteration-test').match_report[0]['status'],'applied')

if __name__=='__main__': unittest.main(verbosity=2)
