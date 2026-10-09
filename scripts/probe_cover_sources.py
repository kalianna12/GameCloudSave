"""Live catalog/image probes and public search-page reachability; no game edits."""
from pathlib import Path
import sys,json,time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
from urllib.parse import quote
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from services import Store,ROOT
from cover_sources import search,download,PROVIDERS
from PySide6.QtGui import QImageReader
output=ROOT/'test-data/v22-cover-probe';output.mkdir(exist_ok=True);store=Store(output/'data','probe')
def probe(item):
    if item['kind']=='api':
        if item['id']=='custom':return {'source':'custom','result':'covered by local JSON contract tests'}
        query='Celeste' if item['id']=='steam' else 'Fate/stay night'
        try:
            rows=search(store,query,item['id']);file=download(store,rows[0]);reader=QImageReader(file);size=reader.size();del reader
            return {'source':item['id'],'result':'PASS','query':query,'results':len(rows),'first':rows[0]['name'],'image_size':[size.width(),size.height()]}
        except Exception as error:return {'source':item['id'],'result':'FAIL','error':str(error)}
    url=item['url'].replace('{query}',quote('Celeste game cover'))
    try:
        with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=15) as response:
            response.read(2048);status=response.status
        return {'source':item['id'],'mode':'browser','url':url,'http_status':status,'result':'reachable (browser search, not an in-app API)'}
    except Exception as error:
        return {'source':item['id'],'mode':'browser','url':url,'result':'automated request unavailable; browser entry retained','error':type(error).__name__+': '+str(error)}
with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(probe,PROVIDERS))
(output/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
for row in results:print(row['source'],row['result'],row.get('http_status',row.get('image_size','')),flush=True)
sys.exit(any(row['result']=='FAIL' for row in results))
