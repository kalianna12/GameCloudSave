"""GPU core contract, isolated persistence and asynchronous lifecycle regressions."""
from pathlib import Path
import json
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from graphics_enhancement import DEFAULT, Engine, GraphicsEnhancement, make_config, normalize, extract_verified,intensity_profile
from services import ROOT, Store, write_json
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication([])


def spin_until(predicate, timeout=5):
    end = time.monotonic()+timeout
    while not predicate() and time.monotonic()<end:
        app.processEvents(); time.sleep(.005)
    app.processEvents()
    assert predicate(), 'Timed out waiting for graphics worker'


class GraphicsTests(unittest.TestCase):
    def test_intensity_preserves_output_and_high_uses_full_anime_sharpness(self):
        base=normalize(dict(enabled=True,preset='anime-fast',display='windowed',window_scale=3,fps=120,capture=3))
        for level,sharpness,preset in [('low',35,'anime-fast'),('medium',70,'anime-quality'),('high',100,'anime-quality')]:
            changes=intensity_profile('anime-quality',level)
            self.assertEqual(changes,dict(preset=preset,sharpness=sharpness))
            profile=normalize(dict(base,**changes));self.assertEqual((profile['display'],profile['window_scale'],profile['fps'],profile['capture']),('windowed',3,120,3))
        config=make_config(dict(base,**intensity_profile('anime-fast','high')),'x','Y','High')
        effects=config['scalingModes'][0]['effects'];self.assertTrue(effects[0]['name'].endswith('_L'));self.assertEqual(effects[-1]['parameters']['sharpness'],1)
        self.assertEqual(intensity_profile('fsr','high'),dict(preset='fsr',sharpness=100))
        self.assertEqual(intensity_profile('nearest','high')['sharpness'],0)
        for preset,level in [('invalid','low'),('anime-fast','invalid')]:
            with self.assertRaises(ValueError):intensity_profile(preset,level)
    def test_strict_numeric_and_choice_validation(self):
        self.assertEqual(normalize({}), DEFAULT)
        for value in ({'fps': float('nan')}, {'sharpness': True}, {'capture': 1},
                      {'preset': 'missing'}, {'enabled': 'yes'}, {'window_scale': 0}):
            with self.assertRaises(ValueError): normalize(value)
        self.assertFalse(normalize({'display': 'windowed', 'game_3d': True})['game_3d'])

    def test_real_shader_chains_and_exact_window_rule(self):
        for preset in ('anime-fast', 'anime-quality', 'fsr', 'lanczos', 'nearest'):
            config = make_config({'preset': preset, 'sharpness': 40}, r'D:\Games\game.exe', 'Chrome_WidgetWin_88', 'Fixture')
            effects = config['scalingModes'][0]['effects']
            self.assertEqual(config['profiles'][1]['classNameRule'], 'Chrome_WidgetWin_1')
            self.assertEqual(config['profiles'][1]['pathRule'], r'D:\Games\game.exe')
            self.assertEqual(config['profiles'][1]['autoScale'], 1)
            self.assertEqual(config['profiles'][0]['scalingMode'], -1, 'Other windows must not inherit the game shader')
            self.assertFalse(config['autoCheckForUpdates'])
            if preset.startswith('anime'):
                self.assertTrue(effects[0]['name'].startswith('Anime4K\\Anime4K_Upscale_Denoise_'))
                self.assertEqual(effects[1]['scalingType'], 1)
            elif preset=='fsr':
                self.assertEqual([e['name'] for e in effects], ['FSR\\FSR_EASU', 'FSR\\FSR_RCAS'])
            elif preset=='nearest': self.assertEqual(len(effects), 1)
        config = make_config({'display': 'windowed', 'fit': 'stretch', 'window_scale': 1.75}, 'x', 'Y', 'Z')
        self.assertEqual(config['profiles'][1]['autoScale'], 2)
        self.assertEqual(config['profiles'][1]['customInitialWindowedScaleFactor'], 1.75)
        self.assertEqual(config['scalingModes'][0]['effects'][1]['scalingType'], 1)

    def test_untrusted_zip_rejected_without_touching_install(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); archive = root/'fake.zip'; archive.write_bytes(b'not a release')
            with self.assertRaisesRegex(ValueError, '校验失败'): extract_verified(archive, root/'core', 'x64')
            self.assertFalse((root/'core').exists())

    def test_unrelated_engine_is_never_controlled_or_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            engine=Engine(temp);other=MagicMock();other.info={'name':'Magpie.exe','pid':555}
            with patch.object(engine,'installed',return_value=True),patch('graphics_enhancement.supported',return_value=True),patch('psutil.process_iter',return_value=[other]),patch('graphics_enhancement.target_identity') as target:
                with self.assertRaisesRegex(ValueError,'先退出'):engine.start({},1,2,'Fixture',threading.Event())
                target.assert_not_called();other.terminate.assert_not_called()
                self.assertFalse((engine.directory/'config/config.json').exists())

    def test_runtime_state_and_target_pid_reuse_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            engine=Engine(temp);process=MagicMock();process.pid=55;process.poll.return_value=None
            engine.process=process;engine.target=(123,2.5)
            target=MagicMock();target.create_time.return_value=2.5;target.is_running.return_value=True
            with patch('psutil.Process',return_value=target),patch('graphics_enhancement.scaling_visible',return_value=True):
                self.assertEqual(engine.poll(),'active')
            with patch('psutil.Process',return_value=target),patch('graphics_enhancement.scaling_visible',return_value=False):
                self.assertEqual(engine.poll(),'ready')
            target.create_time.return_value=9.0
            with patch('psutil.Process',return_value=target),patch.object(engine,'stop') as stop:
                self.assertEqual(engine.poll(),'game-exited');stop.assert_called_once()

    def test_save_two_games_is_async_local_and_survives_reload(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temp:
            store = Store(temp, 'graphics-unit'); store.games = [{'id':'a','name':'A'}, {'id':'b','name':'B'}]
            store.local = {'a':{'exe':r'D:\a.exe','save_dir':'unmodified'}, 'b':{'exe':r'D:\b.exe'}}
            write_json(store.root/'library.json', store.games); before = (store.root/'library.json').read_bytes()
            controller = GraphicsEnhancement(store); saved = []; controller.saved.connect(saved.append)
            try:
                original = store.save_game
                def slow(*args): time.sleep(.15); original(*args)
                start=time.perf_counter()
                with patch.object(store, 'save_game', side_effect=slow):
                    controller.save('a', {'enabled':True, 'preset':'fsr', 'sharpness':65})
                    self.assertLess(time.perf_counter()-start, .05)
                    self.assertTrue(controller.state['busy']); spin_until(lambda:not controller.state['busy'])
                controller.save('b', {'enabled':True, 'preset':'anime-quality'})
                spin_until(lambda:not controller.state['busy'])
                reloaded=Store(temp,'graphics-unit')
                self.assertEqual(reloaded.local['a']['graphics']['sharpness'],65)
                self.assertEqual(reloaded.local['b']['graphics']['preset'],'anime-quality')
                self.assertEqual(reloaded.local['a']['save_dir'],'unmodified')
                self.assertEqual((store.root/'library.json').read_bytes(),before)
                self.assertEqual(saved,['a','b']); self.assertIsNone(controller.engine.process)
            finally:controller.shutdown();controller.pool.shutdown(wait=True)

    def test_cancel_pending_window_discovery_never_launches_core(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temp:
            store=Store(temp,'graphics-cancel');store.games=[{'id':'a','name':'A'}]
            store.local={'a':{'exe':r'D:\game.exe','graphics':{'enabled':True}}}
            controller=GraphicsEnhancement(store); entered=threading.Event()
            def wait(probe,cancel,timeout):
                entered.set();cancel.wait(3);return {'phase':'cancelled'}
            try:
                with patch.object(controller.engine,'installed',return_value=True), patch('launch_ready.wait',side_effect=wait), patch.object(controller.engine,'start') as start:
                    controller.apply('a');self.assertTrue(entered.wait(1));controller.cancel()
                    spin_until(lambda:not controller.state['busy']);start.assert_not_called()
                self.assertEqual(controller.state['message'],'已取消画质增强')
            finally:controller.shutdown();controller.pool.shutdown(wait=True)

    def test_window_handoff_waits_for_inflight_install(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temp:
            store=Store(temp,'graphics-queued');store.games=[{'id':'a','name':'A'}]
            store.local={'a':{'graphics':{'enabled':True}}}
            controller=GraphicsEnhancement(store);gate=threading.Event()
            try:
                with patch.object(controller.engine,'installed',return_value=True),patch.object(controller.engine,'start') as start:
                    controller.submit('installing','Installing fixture',lambda:(gate.wait(2) and {'phase':'idle','message':'Installed'}))
                    controller.startForGame('a',77,88,automatic=True)
                    self.assertEqual(controller._pending,('a',77,88));start.assert_not_called()
                    gate.set();spin_until(lambda:start.called and not controller.state['busy'])
                    self.assertEqual(start.call_args.args[1:4],(88,77,'A'))
                    self.assertIsNone(controller._pending)
            finally:gate.set();controller.shutdown();controller.pool.shutdown(wait=True)

    def test_automatic_only_after_window_handoff_and_not_abandoned(self):
        from main import Bridge
        with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temp:
            store=Store(temp,'graphics-launch');store.settings.update(watch=False,recommendations_enabled=False)
            backend=Bridge(store)
            try:
                backend._launch_state={'phase':'ready','ident':'a','pid':77,'hwnd':88}
                with patch('launch_ready.activate') as activate, patch.object(backend.graphics,'startForGame') as start:
                    backend.finishLaunchPresentation();activate.assert_called_once_with(88,77)
                    start.assert_called_once_with('a',77,88,automatic=True)
                    backend._launch_state['phase']='ready';backend._launch_abandoned=True
                    backend.finishLaunchPresentation();self.assertEqual(start.call_count,1)
            finally:backend.shutdownWatch();backend.graphics.pool.shutdown(wait=True);backend.pool.shutdown(wait=True)

    def test_actual_official_archive_optional(self):
        archive=ROOT/'build/Magpie-v0.13.0-x64.zip'
        if not archive.is_file():self.skipTest('Official ZIP not cached')
        with tempfile.TemporaryDirectory(dir=ROOT/'test-data') as temp:
            engine=Engine(temp)
            if engine.arch!='x64':self.skipTest('x64 cached package')
            engine.install(threading.Event(),lambda _:None,archive)
            self.assertTrue(engine.installed())
            (engine.directory/'effects/Lanczos.hlsl').unlink()
            self.assertFalse(engine.installed())
            engine.install(threading.Event(),lambda _:None,archive)
            self.assertTrue(engine.installed())
            self.assertFalse((engine.directory/'logs').exists())


if __name__=='__main__':unittest.main()
