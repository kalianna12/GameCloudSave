"""Cached phonetic search keys, independent of keyboard/IME composition."""
from functools import lru_cache
import re


@lru_cache(maxsize=8192)
def phonetic(text):
    from pypinyin import lazy_pinyin
    parts=lazy_pinyin(text,errors=lambda word:re.findall(r'[a-zA-Z0-9]+',word))
    return ''.join(parts).casefold(),''.join(word[0] for word in parts if word).casefold()


def search_keys(game):
    aliases=game.get('aliases',[])
    if isinstance(aliases,str):aliases=[aliases]
    values=[game.get('name',''),*aliases,game.get('series',''),*game.get('tags',[])]
    return ' '.join(key for value in values if isinstance(value,str) for key in phonetic(value))
