#!/usr/bin/env python3
"""Generate aggregate profile SVGs with Python and authenticated GitHub CLI."""
import collections
from functools import lru_cache
import datetime as dt
import html
import json
import math
from pathlib import Path
import re
import subprocess
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

OUTPUT = Path(__file__).resolve().parents[1] / 'assets' / 'stats'
FONT_PATH = OUTPUT.parent / 'fonts' / 'Montserrat.ttf'
PALETTE = [
    '#8B5CF6', '#3B82F6', '#EC4899', '#10B981', '#F59E0B', '#06B6D4',
    '#EF4444', '#6366F1', '#84CC16', '#F97316', '#14B8A6', '#A855F7',
    '#0EA5E9', '#EAB308', '#F43F5E', '#22C55E',
]
OTHER_LANGUAGES = {
    'Makefile', 'CMake', 'Dockerfile', 'Shell', 'PowerShell', 'TeX', 'Tcl',
    'GDB', 'LLVM', 'Rich Text Format', 'ShaderLab', 'HLSL', 'GLSL', 'QML',
    'PLpgSQL',
}


def api(query, **variables):
    result = subprocess.run(['gh', 'api', 'graphql', '--input', '-'],
                            input=json.dumps({'query': query, 'variables': variables}),
                            text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError('Falha na API do GitHub. Verifique autenticação e permissões; nenhum gráfico atualizado.')
    response = json.loads(result.stdout)
    if response.get('errors'):
        raise RuntimeError('Resposta incompleta do GitHub; nenhum gráfico atualizado.')
    return response['data']


# Convert Montserrat glyphs to paths: GitHub image rendering cannot rely on webfonts.
@lru_cache(maxsize=6)
def font(weight):
    return instantiateVariableFont(TTFont(FONT_PATH), {'wght': weight}, inplace=True)


def _round_path(commands):
    def fmt(match):
        val = round(float(match.group(0)), 1)
        return str(int(val)) if val.is_integer() else f'{val:.1f}'
    return re.sub(r'-?\d+\.\d+', fmt, commands)


@lru_cache(maxsize=4096)
def glyph(character, weight):
    face = font(weight)
    name = face.getBestCmap().get(ord(character), '.notdef')
    pen = SVGPathPen(face.getGlyphSet())
    face.getGlyphSet()[name].draw(pen)
    return _round_path(pen.getCommands()), face['hmtx'][name][0]


def text_width(value, size=16, weight=450, tracking=0.0):
    value = str(value)
    if not value:
        return 0.0
    scale = size / font(weight)['head'].unitsPerEm
    shapes = [glyph(c, weight) for c in value]
    step_extra = tracking * size
    return sum(advance for _, advance in shapes) * scale + step_extra * max(0, len(shapes) - 1)


def text(x, y, value, size=16, fill='currentColor', weight=450, anchor='start', tracking=0.0):
    value = str(value)
    if not value:
        return ''
    upm = font(weight)['head'].unitsPerEm
    scale = size / upm
    shapes = [glyph(c, weight) for c in value]
    extra_units = tracking * upm
    total_units = sum(advance for _, advance in shapes) + extra_units * max(0, len(shapes) - 1)
    width = total_units * scale
    x -= width / 2 if anchor == 'middle' else width if anchor == 'end' else 0
    paths, cursor = [], 0.0
    for outline, advance in shapes:
        if outline:
            cx = int(round(cursor)) if round(cursor, 1).is_integer() else round(cursor, 1)
            paths.append(f'<path transform="translate({cx} 0)" d="{outline}"/>')
        cursor += advance + extra_units
    return (
        f'<g aria-label="{html.escape(value, quote=True)}" role="img" fill="{fill}" '
        f'transform="translate({x:.2f} {y:.2f}) scale({scale:.5f} {-scale:.5f})">'
        f'<title>{html.escape(value)}</title>{"".join(paths)}</g>'
    )


def theme_colors(dark):
    if dark:
        return {
            'bg': '#060609',
            'surface': '#0d0c14',
            'fg': '#f2f0f8',
            'muted': '#9e99b0',
            'border': '#242130',
            'accent': '#8B5CF6',
            'accent_bright': '#A78BFA',
        }
    return {
        'bg': '#faf9fd',
        'surface': '#f1eef9',
        'fg': '#14111f',
        'muted': '#625b73',
        'border': '#dcd8e8',
        'accent': '#7C3AED',
        'accent_bright': '#6D28D9',
    }


def card(title, body, height, dark, width=960):
    c = theme_colors(dark)
    w_title = text_width(title, 26 if width < 600 else 28, weight=600, tracking=-0.03)
    title_y, line_y = 54, 80
    header = text(32, title_y, title, 26 if width < 600 else 28, c['fg'], weight=600, tracking=-0.03)
    header += text(32 + w_title + 1, title_y, '.', 26 if width < 600 else 28, c['accent'], weight=700)
    content = (
        body.replace('MUTED', c['muted'])
        .replace('BORDER', c['border'])
        .replace('ACCENT_BRIGHT', c['accent_bright'])
        .replace('ACCENT', c['accent'])
        .replace('SURFACE', c['surface'])
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">
<title>{html.escape(title)}</title>
<defs>
  <radialGradient id="halo" cx="95%" cy="0%" r="80%">
    <stop stop-color="{c["accent"]}" stop-opacity="{'.14' if dark else '.08'}"/>
    <stop offset="1" stop-color="{c["accent"]}" stop-opacity="0"/>
  </radialGradient>
</defs>
<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="16" fill="{c["bg"]}" stroke="{c["border"]}"/>
<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="16" fill="url(#halo)"/>
<g color="{c["fg"]}">
{header}
<path d="M32 {line_y}H{width-32}" stroke="{c["border"]}"/>
{content}</g></svg>'''


def language_chart(languages, dark, compact=False):
    grouped = collections.Counter()
    other_total = 0
    for name, count in languages.items():
        if name in OTHER_LANGUAGES:
            other_total += count
        else:
            grouped[name] += count
    ordered = sorted(grouped.items(), key=lambda item: (-item[1], item[0].casefold()))
    if other_total:
        ordered.append(('Outras', other_total))
    total = sum(languages.values())
    width = 480 if compact else 960
    rows = len(ordered) if compact else math.ceil(len(ordered) / 2)
    height = max(490, (395 if compact else 140) + rows * 38 + 60)
    cx, cy, radius = (240, 232, 94) if compact else (175, 260, 108)
    body, offset = '', 0
    body += f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="BORDER" stroke-width="24" opacity=".45"/>'
    max_prop = max((c / total for _, c in ordered), default=1)
    for i, (name, count) in enumerate(ordered):
        proportion = count / total
        color = '#64748B' if name == 'Outras' else PALETTE[i % len(PALETTE)]
        circumference = radius * 2 * math.pi
        gap = min(2.4, proportion * circumference * 0.18)
        seg = max(0, proportion * circumference - gap)
        body += (
            f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{color}" stroke-width="24" '
            f'stroke-dasharray="{seg:.3f} {circumference - seg:.3f}" '
            f'stroke-dashoffset="{-offset * circumference:.3f}" transform="rotate(-90 {cx} {cy})">'
            f'<title>{html.escape(name)}: {proportion * 100:.2f}%</title></circle>'
        )
        offset += proportion
        col, row = (0, i) if compact else divmod(i, rows)
        x = 32 if compact else 352 + col * 294
        y = (402 if compact else 140) + row * 38
        right = width - 32 if compact else x + 264
        bar_w = (right - x) * (proportion / max_prop) if ordered else 0
        body += f'<circle cx="{x + 5}" cy="{y - 5}" r="4.5" fill="{color}"/>'
        body += text(x + 19, y, name, 14.5, weight=500 if i < 6 else 450)
        percentage = f'{proportion * 100:.1f}%' if proportion >= 0.001 else '< 0.1%'
        body += text(right, y, percentage, 13.5, 'MUTED', weight=500 if i < 6 else 450, anchor='end')
        body += f'<path d="M{x} {y + 12}H{right}" stroke="BORDER" stroke-opacity=".55"/>'
        if bar_w >= 2:
            body += f'<path d="M{x} {y + 12}H{x + bar_w:.1f}" stroke="{color}" stroke-width="2" stroke-opacity=".95"/>'
    body += text(cx, cy + 5, len(grouped), 46, weight=600, anchor='middle', tracking=-0.03)
    body += text(cx, cy + 31, 'linguagens', 13.5, 'MUTED', anchor='middle')
    if not compact:
        body += text(cx, cy + radius + 50, 'Volume de código', 12, 'MUTED', anchor='middle')
    if not total:
        body += text(width / 2, 400, 'Sem linguagens identificadas', 16, 'MUTED', anchor='middle')
    body += text(32, height - 24, 'Públicos + privados acessíveis · sem forks', 12, 'MUTED')
    return card('Linguagens', body, height, dark, width)


def activity_chart(contributions, since, until, dark, compact=False):
    total = contributions['contributionCalendar']['totalContributions']
    width, height = (480, 600) if compact else (960, 475)
    body = text(32, 160, f'{total:,}'.replace(',', '.'), 56, weight=600, tracking=-0.03)
    body += text(32, 187, 'contribuições (12 meses)', 13.5, 'MUTED')

    monthly = collections.Counter()
    active_days = 0
    for week in contributions['contributionCalendar']['weeks']:
        for day in week['contributionDays']:
            if since.date().isoformat() <= day['date'] <= until.date().isoformat():
                count = day['contributionCount']
                monthly[day['date'][:7]] += count
                if count > 0:
                    active_days += 1
    ordered = sorted(monthly.items())
    peak = max(monthly.values(), default=0) or 1
    monthly_avg = round(total / max(len(ordered), 1))

    metrics = [
        (active_days, 'dias ativos'),
        (monthly_avg, 'média / mês'),
        (peak, 'pico mensal'),
    ]
    for i, (value, label) in enumerate(metrics):
        if compact:
            x = 32 + i * 142
            y = 255
            box_w = 132
            body += f'<rect x="{x}" y="{y - 38}" width="{box_w}" height="68" rx="12" fill="SURFACE" stroke="BORDER"/>'
            body += text(x + 14, y - 4, f'{value:,}'.replace(',', '.'), 26, weight=600)
            body += text(x + 14, y + 18, label, 12.5, 'MUTED')
        else:
            x = 396 + i * 178
            y = 154
            box_w = 164
            body += f'<rect x="{x}" y="110" width="{box_w}" height="82" rx="14" fill="SURFACE" stroke="BORDER"/>'
            body += text(x + 20, y, f'{value:,}'.replace(',', '.'), 30, weight=600, tracking=-0.02)
            body += text(x + 20, y + 25, label, 13, 'MUTED')

    chart_top, baseline = (352, 512) if compact else (266, 386)
    chart_width = width - 64
    step = chart_width / max(len(ordered), 1)
    labels = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']
    body += text(32, chart_top - 28, 'Contribuições por mês', 14, 'MUTED', weight=500)
    for fraction in (0, 0.5, 1):
        y = baseline - (baseline - chart_top) * fraction
        body += f'<path d="M32 {y:.1f}H{width - 32}" stroke="BORDER" stroke-dasharray="3 6"/>'
    for i, (month, value) in enumerate(ordered):
        x = 32 + i * step + 5
        h = max(3.0 if value > 0 else 0.0, value / peak * (baseline - chart_top))
        bar_width = step - 12
        label = labels[int(month[5:]) - 1]
        is_peak = value == peak and value > 0
        opacity = 0.45 + 0.55 * (value / peak)
        body += (
            f'<rect x="{x:.2f}" y="{baseline - h:.2f}" width="{bar_width:.2f}" height="{h:.2f}" rx="5" '
            f'fill="ACCENT" opacity="{opacity:.3f}"><title>{month}: {value} contribuições</title></rect>'
        )
        val_color = 'ACCENT_BRIGHT' if is_peak else 'MUTED'
        val_weight = 600 if is_peak else 450
        body += text(x + bar_width / 2, baseline - h - 9, value, 10 if compact else 12, val_color, weight=val_weight, anchor='middle')
        body += text(x + bar_width / 2, baseline + 24, label, 10 if compact else 12.5, 'MUTED', anchor='middle')
    body += text(32, height - 24, f'{since:%d/%m/%Y} a {until:%d/%m/%Y}', 12, 'MUTED')
    if not compact:
        body += text(width - 32, height - 24, 'Públicos + privados acessíveis', 12, 'MUTED', anchor='end')
    return card('Atividade no GitHub', body, height, dark, width)


def main():
    until = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    since = until - dt.timedelta(days=365)
    languages = collections.Counter()
    cursor = None
    while True:
        data = api('''query($cursor:String) { viewer { repositories(first:100, after:$cursor,
          ownerAffiliations:[OWNER], isFork:false) {
          nodes { languages(first:100) { edges { size node { name } } pageInfo { hasNextPage } } }
          pageInfo { hasNextPage endCursor }
        } } }''', cursor=cursor)['viewer']['repositories']
        for repo in data['nodes']:
            if repo['languages']['pageInfo']['hasNextPage']:
                raise RuntimeError('Um repositório tem mais de 100 linguagens; paginação adicional necessária.')
            for edge in repo['languages']['edges']:
                languages[edge['node']['name']] += edge['size']
        if not data['pageInfo']['hasNextPage']:
            break
        cursor = data['pageInfo']['endCursor']
    contributions = api('''query($from:DateTime!, $to:DateTime!) { viewer {
      contributionsCollection(from:$from, to:$to) {
        totalCommitContributions totalPullRequestContributions totalPullRequestReviewContributions
        contributionCalendar { totalContributions weeks { contributionDays { date contributionCount } } }
      }
    } }''', **{'from': since.isoformat(), 'to': until.isoformat()})['viewer']['contributionsCollection']
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for dark in (False, True):
        theme = 'dark' if dark else 'light'
        for compact in (False, True):
            suffix = f'-{theme}' + ('-mobile' if compact else '') + '.svg'
            (OUTPUT / ('languages' + suffix)).write_text(language_chart(languages, dark, compact))
            (OUTPUT / ('activity' + suffix)).write_text(activity_chart(contributions, since, until, dark, compact))
    print('Gráficos de linguagens e contribuições gerados. Somente agregados foram salvos.')


if __name__ == '__main__':
    main()
