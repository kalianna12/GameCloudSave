"""Read-only local binary records; unknown statistics never become achievements."""
from pathlib import Path
import struct
import zlib


def sse_progress(path):
    path=Path(path)
    if path.stat().st_size>8*1024*1024:raise ValueError('本地成就记录超过读取上限')
    data=path.read_bytes()
    if len(data)<4:raise ValueError('SSE 记录尚未写入完整')
    count=struct.unpack_from('<I',data)[0]
    if count>5000 or len(data)!=4+count*24:raise ValueError('不支持的 stats.bin 或记录尚未写入完整')
    result={}
    for offset in range(4,len(data),24):
        crc,stamp,value=struct.unpack_from('<I',data,offset)[0],struct.unpack_from('<I',data,offset+8)[0],struct.unpack_from('<i',data,offset+20)[0]
        # SSE shares this file with stats. Only a schema-correlated CRC is used.
        if value in (0,1):result[f'crc32:{crc:08x}']={'unlocked':value==1,'time':stamp,'progress':0}
    return result


def crc_names(schema):
    result={}
    for row in schema:
        value=f"crc32:{zlib.crc32(row['id'].encode()):08x}"
        result[value]=row['id'] if value not in result else None
    return {key:value for key,value in result.items() if value is not None}
