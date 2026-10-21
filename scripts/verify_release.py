"""Run isolated regression processes sequentially, retaining per-case release logs."""
from pathlib import Path
import argparse,ast,json,os,re,subprocess,sys,time
sys.stdout.reconfigure(encoding='utf-8')
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('unit','ui'),required=True);parser.add_argument('--version',default='2.6.0');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
if not re.fullmatch(r'\d+\.\d+\.\d+',args.version):raise ValueError('Invalid version')
out=ROOT/'build'/('release-'+args.version);out.mkdir(parents=True,exist_ok=True)
if args.phase=='unit':
    cases=[]
    for path in sorted((ROOT/'tests').glob('test_*.py')):
        tree=ast.parse(path.read_text(encoding='utf-8-sig'))
        if any(isinstance(node,ast.ClassDef) and any(isinstance(base,ast.Attribute) and base.attr=='TestCase' or isinstance(base,ast.Name) and base.id=='TestCase' for base in node.bases) for node in tree.body):cases.append(path.name)
else:
    cases=['test_shelf_incremental_ui.py','test_recommendation_refresh_ui.py','test_recommendations_ui.py','test_home_transfer_ui.py',
           'test_home_spatial_input.py','test_layout_audio_ui.py','test_navigation_audio_output.py','test_audio_settings_ui.py','test_navigation_latency_ui.py','test_new_games_save_scope_ui.py','test_toolbar_navigation.py','test_fullscreen_lifecycle.py','test_mapping_chord_editor_ui.py',
           'test_input_mapping_ui.py','test_mapping_capture_ui.py','test_mapping_performance_ui.py','test_mapping_model_geometry_ui.py',
           'test_mapping_templates_ui.py','test_save_ui.py','test_async_artwork.py','test_inline_artwork_ui.py',
           'test_immersive_controls.py','test_library_experiences.py','test_launch_ui.py','test_cinema_backdrop.py','test_ui_enrichment.py',
           'test_time_ui.py','test_save_rclone.py']
previous=json.loads((out/(args.phase+'-results.json')).read_text()) if args.resume and (out/(args.phase+'-results.json')).exists() else []
passed={row['script']:row for row in previous if row['exit_code']==0}
results=[]
for name in cases:
    if name in passed:
        results.append(passed[name]);continue
    started=time.perf_counter();log=out/(args.phase+'-'+Path(name).stem+'.log')
    with log.open('w',encoding='utf-8') as stream:
        try:
            code=subprocess.run([sys.executable,str(ROOT/'tests'/name)],cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,timeout=240,env={**os.environ,'PYTHONIOENCODING':'utf-8','PYTHONPATH':str(ROOT)+os.pathsep+os.environ.get('PYTHONPATH','')}).returncode
        except subprocess.TimeoutExpired:code=124
    content=log.read_text(encoding='utf-8',errors='replace');count=re.search(r'Ran (\d+) tests?',content)
    row={'script':name,'exit_code':code,'seconds':round(time.perf_counter()-started,2),'tests':int(count[1]) if count else None}
    results.append(row);(out/(args.phase+'-results.json')).write_text(json.dumps(results,indent=2),encoding='utf-8')
    print(('PASS' if code==0 else 'FAIL')+' '+name+' '+str(row['seconds'])+'s',flush=True)
    if code:
        print(content[-6000:],flush=True);sys.exit(code)
print('PASS '+args.phase+': '+str(len(results))+' processes, '+str(sum(row['tests'] or 0 for row in results))+' unittest cases',flush=True)
