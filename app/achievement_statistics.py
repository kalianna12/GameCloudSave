"""Small immutable chart snapshots, built on the achievement worker."""
from collections import Counter
from datetime import datetime,timedelta
import math,time

RARITY_LABELS=['极稀有','稀有','不常见','常见','未知']


def game_snapshot(game,summary,schema,record):
    definitions={r['id']:r for r in schema};unlocks=record.get('unlocks',{});days=Counter();rarity=[0]*5;unknown=0
    for key,stamp in unlocks.items():
        if key not in definitions:continue
        row=definitions[key];percent=row.get('rarity',0)
        known=row.get('rarity_known',percent>0)
        rarity[4 if not known else 0 if percent<=1 else 1 if percent<=10 else 2 if percent<=50 else 3]+=1
        if stamp>0 and stamp<=time.time()+86400:
            days[datetime.fromtimestamp(stamp).strftime('%Y-%m-%d')]+=1
        else:unknown+=1
    return dict(id=game['id'],name=game['name'],total=summary['total'],unlocked=summary['unlocked'],days=dict(days),rarity=rarity,unknown_dates=unknown)


def statistics(snapshots,ident='',period=30,now=None):
    now=now or datetime.now();today=now.date();rows=[r for r in snapshots if not ident or r['id']==ident]
    total=sum(r['total'] for r in rows);unlocked=sum(r['unlocked'] for r in rows);daily=Counter()
    for row in rows:daily.update(row['days'])
    start=today-timedelta(days=period-1) if period else datetime.strptime(min(daily,default=today.isoformat()),'%Y-%m-%d').date()
    start=max(start,today-timedelta(days=365*20));length=max(1,(today-start).days+1);bucket=max(1,math.ceil(length/40))
    dates=[start+timedelta(days=i) for i in range(0,length,bucket)];counts=[0]*len(dates)
    for key,value in daily.items():
        day=datetime.strptime(key,'%Y-%m-%d').date()
        if start<=day<=today:counts[min(len(counts)-1,(day-start).days//bucket)]+=value
    cumulative=[];n=0
    for value in counts:n+=value;cumulative.append(n)
    rarity=[sum(r['rarity'][i] for r in rows) for i in range(5)]
    leaders=sorted(rows,key=lambda r:(-r['unlocked'],-r['total'],r['name']))[:7]
    return dict(total=total,unlocked=unlocked,locked=max(0,total-unlocked),percent=round(unlocked/total*100,1) if total else 0,
                games=len(rows),completed_games=sum(r['total']>0 and r['unlocked']==r['total'] for r in rows),
                unknown_dates=sum(r['unknown_dates'] for r in rows),rarity=rarity,rarity_labels=RARITY_LABELS,
                daily=counts,cumulative=cumulative,dates=[min(d+timedelta(days=bucket-1),today).strftime('%y/%m/%d' if period in (0,365) else '%m/%d') for d in dates],dated_unlocks=sum(counts),bucket_days=bucket,
                bar_values=rarity if ident else [r['unlocked'] for r in leaders],
                bar_labels=RARITY_LABELS if ident else [r['name'] for r in leaders],period=period)
