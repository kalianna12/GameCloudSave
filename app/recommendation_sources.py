"""Anonymous official storefront feeds. No account, library or API key is sent."""
import json
import math
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

STEAM = 'https://store.steampowered.com/api/featuredcategories/?cc=cn&l=schinese'
XBOX = 'https://www.xbox.com/zh-HK/games/browse'
SECTIONS = {
    'new': ('新发布', 'https://store.steampowered.com/explore/new/'),
    'sale': ('正在促销', 'https://store.steampowered.com/specials/'),
    'popular': ('Steam 热门', 'https://store.steampowered.com/charts/topselling/'),
    'xbox': ('Xbox 精选', XBOX),
}


def request(url, limit=4 * 1024 * 1024):
    with urlopen(Request(url, headers={'User-Agent': 'GameCloudSave/2.5', 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.5'}), timeout=10) as response:
        raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('商店响应过大')
    return raw


def image_url(value):
    if not isinstance(value, str):
        return ''
    if value.startswith('//'):
        value = 'https:' + value
    parsed = urlsplit(value)
    host = (parsed.hostname or '').lower()
    allowed = host.endswith('.steamstatic.com') or host == 'store-images.s-microsoft.com'
    return value[:2000] if parsed.scheme == 'https' and allowed and not parsed.username else ''


def amount(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def price(value, currency):
    if not amount(value) or currency not in ('CNY', 'HKD', 'USD', 'EUR', 'GBP', 'JPY'):
        return ''
    if value == 0:
        return '免费'
    symbol = {'CNY': '¥', 'HKD': 'HK$', 'USD': 'US$', 'EUR': '€', 'GBP': '£', 'JPY': 'JP¥'}[currency]
    return symbol + f'{value:,.2f}'.rstrip('0').rstrip('.')


def steam_rows(data):
    if not isinstance(data, dict):
        raise ValueError('Steam 返回格式已变化')
    output = []
    for key, category in [('new_releases', 'new'), ('specials', 'sale'), ('top_sellers', 'popular')]:
        section = data.get(key, {})
        items = section.get('items', []) if isinstance(section, dict) else []
        seen = set()
        for item in items:
            if not isinstance(item, dict) or item.get('type') != 0 or not item.get('windows_available'):
                continue
            ident = str(item.get('id', ''))
            name = item.get('name')
            if not re.fullmatch(r'\d{1,12}', ident) or not isinstance(name, str) or not name.strip() or ident in seen:
                continue
            discount = item.get('discount_percent', 0)
            discount = int(discount) if amount(discount) and discount <= 100 else 0
            if category == 'sale' and not discount:
                continue
            seen.add(ident)
            final = item.get('final_price')
            currency = item.get('currency', '')
            output.append({'id': 'store:steam:' + ident, 'name': name[:200], 'provider': 'steam', 'category': category,
                           'platformLabel': 'Steam', 'page': 'https://store.steampowered.com/app/' + ident + '/',
                           'images': [url for url in [image_url(item.get('large_capsule_image')), image_url(item.get('header_image'))] if url],
                           'price': price(final / 100, currency) if amount(final) else '',
                           'originalPrice': price(item['original_price'] / 100, currency) if discount and amount(item.get('original_price')) else '',
                           'discount': discount, 'expires': item.get('discount_expiration') if amount(item.get('discount_expiration')) else 0})
            if len(seen) >= 10:
                break
    if not output:
        raise ValueError('Steam 暂无可显示的游戏')
    return output


def xbox_rows(html):
    marker = re.search(r'window\.__PRELOADED_STATE__\s*=\s*', html)
    if not marker:
        raise ValueError('Xbox 商店页面格式已变化')
    state = json.JSONDecoder().raw_decode(html[marker.end():])[0]
    core = state.get('core2', {})
    channels = core.get('channels', {}).get('channelData', {})
    summaries = core.get('products', {}).get('productSummaries', {})
    ids = []
    for channel in channels.values():
        for row in channel.get('data', {}).get('products', []):
            ident = row.get('productId', '')
            if ident not in ids:
                ids.append(ident)
    output = []
    for ident in ids:
        item = summaries.get(ident, {})
        if not re.fullmatch(r'[A-Z0-9]{12}', ident) or item.get('productKind') != 'Game' or not item.get('title'):
            continue
        images = item.get('images', {})
        pictures = [image_url(images.get(kind, {}).get('url', '')) for kind in ('superHeroArt', 'featurePromotionalSquareArt', 'boxArt')]
        prices = item.get('specificPrices', {}).get('purchaseable', [])
        # Membership-only offers are not the anonymous storefront price.
        regular = [p for p in prices if p.get('eligibilityInfo', {}).get('eligibility', 'None') == 'None' and amount(p.get('listPrice'))]
        offer = min(regular, key=lambda p: p['listPrice']) if regular else {}
        discount = offer.get('discountPercentage', 0)
        discount = int(discount) if amount(discount) and discount <= 100 else 0
        devices = item.get('availableOn', [])
        device_label = 'PC / Xbox' if 'PC' in devices and any(str(d).startswith('Xbox') for d in devices) else 'PC' if 'PC' in devices else 'Xbox'
        output.append({'id': 'store:xbox:' + ident, 'name': str(item['title'])[:200], 'provider': 'xbox', 'category': 'xbox',
                       'platformLabel': device_label + ' 港区', 'page': 'https://www.xbox.com/zh-HK/games/store/-/' + ident,
                       'images': [url for url in pictures if url], 'price': price(offer.get('listPrice'), offer.get('currency')),
                       'originalPrice': price(offer.get('msrp'), offer.get('currency')) if discount else '', 'discount': discount, 'expires': 0})
        if len(output) >= 10:
            break
    if not output:
        raise ValueError('Xbox 暂无可显示的游戏')
    return output


def fetch(provider):
    if provider == 'steam':
        return steam_rows(json.loads(request(STEAM)))
    if provider == 'xbox':
        return xbox_rows(request(XBOX).decode('utf-8'))
    raise ValueError('未知推荐来源')


def valid_page(url):
    return url in [page for title, page in SECTIONS.values()] or bool(re.fullmatch(
        r'https://(?:store\.steampowered\.com/app/\d{1,12}/|www\.xbox\.com/zh-HK/games/store/-/[A-Z0-9]{12})', url))
