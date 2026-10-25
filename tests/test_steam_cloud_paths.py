from pathlib import Path
import struct,sys,tempfile,unittest,threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from steam_cloud_paths import page_rules,hints,local_rules

class CloudRules(unittest.TestCase):
    def test_page_rules_and_windows_only_hints(self):
        rows=page_rules('<table><td>root</td><td>WinAppDataLocal</td><td>path</td><td>Ori and the Will of The Wisps</td><td>pattern</td><td>*.uberstate</td></table>')
        self.assertEqual(rows,[dict(root='WinAppDataLocal',path='Ori and the Will of The Wisps',pattern='*.uberstate')])
        self.assertEqual(hints(rows,{},'https://steamdb.info/app/1057090/ufs/')[0]['root'],'local')
        self.assertEqual(hints([dict(root='MacAppSupport',path='X')],{},'test'),[])
        self.assertEqual(hints([dict(root='WinAppDataLocal',path='../wrong')],{},'test'),[])
    def test_v39_v40_v41_selected_record(self):
        for version in (39,40,41):
            keys=['appinfo','ufs','savefiles','0','root','path','pattern']
            def key(name):return struct.pack('<I',keys.index(name)) if version==41 else name.encode()+b'\0'
            def obj(name,body):return b'\0'+key(name)+body+b'\x08'
            def text(name,value):return b'\x01'+key(name)+value.encode()+b'\0'
            payload=obj('appinfo',obj('ufs',obj('savefiles',obj('0',text('root','WinSavedGames')+text('path','Example/{64BitSteamID}')+text('pattern','*.sav')))))+b'\x08'
            metadata=b'\0'*(60 if version>=40 else 40)
            record=struct.pack('<II',42,len(metadata)+len(payload))+metadata+payload+b'\0'*4
            header=struct.pack('<II',0x07564400+version,1)
            if version==41:header+=struct.pack('<Q',16+len(record))
            content=header+record
            if version==41:content+=struct.pack('<I',len(keys))+b''.join(k.encode()+b'\0' for k in keys)
            with tempfile.TemporaryDirectory() as temp:
                file=Path(temp)/'appinfo.vdf';file.write_bytes(content)
                rules=local_rules(file,42);self.assertEqual(rules[0]['pattern'],'*.sav')
                self.assertEqual(hints(rules,{},'test')[0]['relative'],'Example/*')
                self.assertEqual(local_rules(file,999),[])
    def test_real_local_evidence_for_steam_rule(self):
        from matching import scan
        from save_workflow import select_candidate
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);save=root/'UnknownProject';save.mkdir();(save/'SaveGame01.sav').write_bytes(b'fixture')
            rules=[dict(root='WinAppDataLocal',path='UnknownProject',pattern='*.sav')]
            identity=dict(english_name='Completely Different',aliases=[],developers=[],publishers=[],hints=hints(rules,{},'https://steamdb.info/app/42/ufs/'))
            found,_=scan('Other title',{},identity,root_override={'local':root},cancel=threading.Event())
            self.assertTrue(any(r.get('verified_rule') for r in found))
            self.assertIsNotNone(select_candidate({'candidates':found}))

if __name__=='__main__':unittest.main()
