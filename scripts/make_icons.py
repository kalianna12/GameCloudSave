from pathlib import Path
root = Path(__file__).resolve().parents[1] / 'ui/icons'
root.mkdir(parents=True, exist_ok=True)
paths = {
    'success': '<path d="m5 12 4 4L19 6" stroke="#b4f49b" stroke-width="2"/>',
    'failed': '<circle cx="12" cy="12" r="9" stroke="#ffae9e"/><path d="m9 9 6 6m0-6-6 6" stroke="#ffae9e"/>',
    'spark': '<path d="m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5z"/>',
    'play': '<path d="M8 5v14l11-7z" fill="#183018" stroke="none"/>',
    'settings': '<path d="m9 3-1 3-3 1-2 3 2 2-1 3 2 2 3-1 2 3 3-1 1-3 3-1 1-3-2-2 1-3-2-2-3 1-2-2z"/><circle cx="12" cy="12" r="3"/>',
    'cloud': '<path d="M7 18a5 5 0 1 1 1-10 6 6 0 0 1 11 2 4 4 0 0 1-1 8H7"/><path d="m9 13 3-3 3 3m-3-3v10"/>',
    'delete': '<path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7"/>',
    'grid': '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    'app': '<rect x="1" y="1" width="22" height="22" rx="7" fill="#8ce34f" stroke="none"/><path d="M6 15v-4a6 6 0 0 1 12 0v4M6 15h3v-4H6m12 4h-3v-4h3m-3 4v3h-4" stroke="#183018"/>',
}
for name, body in paths.items():
    color = '#19331b' if name == 'grid' else '#d3e0d6'
    (root / f'{name}.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round">{body}</svg>', encoding='utf-8')
