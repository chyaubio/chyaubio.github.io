"""Build translated copies of chyaubio.com from the English index.html.

    python3 i18n/build.py            # writes /<lang>/index.html for every i18n/<lang>.json
    python3 i18n/build.py --extract  # writes i18n/strings.en.json (every translatable string)

index.html is the English source: edit it, then re-run this script. Each i18n/<lang>.json maps
an English string (the element's inner HTML, or an attribute value) to its translation. A string
with no translation stays in English, and the script lists it so the file can be completed.
"""
import json, os, re, sys
from bs4 import BeautifulSoup, NavigableString, Tag

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://chyaubio.com'
LANGS = {  # code: (native name, og:locale)
    'en': ('English', 'en_US'), 'ne': ('नेपाली', 'ne_NP'), 'hi': ('हिन्दी', 'hi_IN'), 'zh': ('中文', 'zh_CN'),
    'de': ('Deutsch', 'de_DE'), 'es': ('Español', 'es_ES'), 'fr': ('Français', 'fr_FR'), 'pt': ('Português', 'pt_BR'),
}
INLINE = {'sub', 'sup', 'strong', 'em', 'b', 'br', 'i', 'a', 'small'}
SKIP = {'script', 'style', 'iframe', 'svg', 'noscript'}
ATTRS = ['alt', 'aria-label', 'title', 'data-caption', 'placeholder']
META = ['description', 'og:title', 'og:description']


def load_source():
    with open(os.path.join(ROOT, 'index.html'), 'rb') as f:
        return f.read().decode('utf-8').replace('\r\n', '\n')


def inner(el):
    return el.decode_contents().strip()


def units(soup):
    """Elements whose content is one translatable string: they hold text and only inline tags."""
    out = []
    def walk(el):
        for child in el.children:
            if not isinstance(child, Tag) or child.name in SKIP:
                continue
            if child.has_attr('data-notranslate') or 'brand' in (child.get('class') or []):
                continue
            descendants = [d for d in child.descendants if isinstance(d, Tag)]
            has_text = child.get_text(strip=True) != ''
            if has_text and all(d.name in INLINE for d in descendants) and child.name not in INLINE | {'html', 'body'}:
                out.append(child)
            elif has_text and child.name in {'a', 'strong', 'em', 'small'} and all(d.name in INLINE for d in descendants):
                out.append(child)
            else:
                walk(child)
    walk(soup.body)
    return out


def strings(soup):
    found = []
    found.append(soup.title.string.strip())
    for m in soup.find_all('meta'):
        if m.get('name') in META or m.get('property') in META:
            found.append(m['content'])
    found += [inner(u) for u in units(soup)]
    for el in soup.body.find_all(True):
        for a in ATTRS:
            if el.has_attr(a) and el[a].strip() and not el.find_parent(attrs={'data-notranslate': True}):
                found.append(el[a])
    seen, ordered = set(), []
    for s in found:
        if s not in seen and re.search(r'[A-Za-z]', s):
            seen.add(s); ordered.append(s)
    return ordered


def build(lang, table):
    html = load_source()
    soup = BeautifulSoup(html, 'html.parser')
    missing = set()
    keep = {el.get_text(strip=True) for el in soup.find_all(attrs={'data-notranslate': True})}
    def tr(s):
        if s in table:
            return table[s]
        if s not in keep:
            missing.add(s)
        return s
    soup.html['lang'] = lang
    soup.title.string = tr(soup.title.string.strip())
    for m in soup.find_all('meta'):
        if m.get('name') in META or m.get('property') in META:
            m['content'] = tr(m['content'])
    for u in units(soup):
        src = inner(u)
        if not re.search(r'[A-Za-z]', src):
            continue
        new = tr(src)
        if new != src:
            u.clear()
            u.append(BeautifulSoup(new, 'html.parser'))
    for el in soup.body.find_all(True):
        if el.find_parent(attrs={'data-notranslate': True}):
            continue
        for a in ATTRS:
            if el.has_attr(a) and re.search(r'[A-Za-z]', el[a]):
                el[a] = tr(el[a])
    url = f'{SITE}/{lang}/'
    soup.find('link', rel='canonical')['href'] = url
    soup.find('meta', property='og:url')['content'] = url
    soup.find('meta', property='og:locale')['content'] = LANGS[lang][1]
    cur = soup.find(class_='lang-current')
    if cur:
        cur.string = LANGS[lang][0]
    # The location redirect only runs on the English root page.
    redirect = soup.find('script', id='lang-redirect')
    if redirect:
        redirect.decompose()
    if lang in ('ne', 'hi'):
        head_font = soup.new_tag('link', rel='stylesheet', href='https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;600&family=Noto+Serif+Devanagari:wght@600;700&display=swap')
        soup.head.find('link', rel='stylesheet').insert_before(head_font)
    out = str(soup).replace('\n', '\r\n')
    os.makedirs(os.path.join(ROOT, lang), exist_ok=True)
    with open(os.path.join(ROOT, lang, 'index.html'), 'wb') as f:
        f.write(out.encode('utf-8'))
    return sorted(missing)


def sitemap():
    alts = ''.join(f'<xhtml:link rel="alternate" hreflang="{c}" href="{SITE}/{"" if c == "en" else c + "/"}"/>' for c in LANGS)
    alts += f'<xhtml:link rel="alternate" hreflang="x-default" href="{SITE}/"/>'
    urls = '\n'.join(f'  <url><loc>{SITE}/{"" if c == "en" else c + "/"}</loc>{alts}<changefreq>monthly</changefreq><priority>{"1.0" if c == "en" else "0.8"}</priority></url>' for c in LANGS)
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n{urls}\n</urlset>\n'
    with open(os.path.join(ROOT, 'sitemap.xml'), 'w') as f:
        f.write(xml)


if __name__ == '__main__':
    soup = BeautifulSoup(load_source(), 'html.parser')
    if '--extract' in sys.argv:
        with open(os.path.join(ROOT, 'i18n', 'strings.en.json'), 'w', encoding='utf-8') as f:
            json.dump(strings(soup), f, ensure_ascii=False, indent=1)
        print(len(strings(soup)), 'strings')
        sys.exit()
    for code in LANGS:
        if code == 'en':
            continue
        path = os.path.join(ROOT, 'i18n', f'{code}.json')
        table = json.load(open(path, encoding='utf-8')) if os.path.exists(path) else {}
        missing = build(code, table)
        print(f'{code}: {len(table)} translations, {len(missing)} missing')
        for m in missing:
            print('   missing:', m[:90])
    sitemap()
