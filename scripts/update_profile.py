"""Fetch public GitHub data and render the profile card using only the standard library."""
import argparse
import base64
from datetime import datetime, timezone
from html import escape
import json
import os
import re
from pathlib import Path
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ET.register_namespace('', 'http://www.w3.org/2000/svg')


def api(path, token, payload=None, method=None):
    body = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        'https://api.github.com/' + path,
        data=body,
        method=method,
        headers={
            'Authorization': 'Bearer ' + token,
            'Accept': 'application/vnd.github+json',
            'Content-Type': 'application/json',
            'User-Agent': 'cankatdev-profile',
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def fetch_data(config, token):
    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionCalendar { totalContributions }
        }
        repositories(first: 100, privacy: PUBLIC, ownerAffiliations: OWNER,
          orderBy: {field: PUSHED_AT, direction: DESC}) {
          nodes {
            name url pushedAt isFork isArchived isEmpty
            primaryLanguage { name color }
          }
        }
      }
    }
    """
    result = api('graphql', token, {'query': query, 'variables': {'login': config['username']}})
    if result.get('errors'):
        raise RuntimeError('GitHub query failed: ' + json.dumps(result['errors']))
    user = result['data']['user']
    if not user:
        raise RuntimeError('GitHub user not found')
    projects = [
        repo for repo in user['repositories']['nodes']
        if repo['name'] in config['projects']
        and not repo['isFork'] and not repo['isArchived'] and not repo['isEmpty']
    ]
    if not projects:
        raise RuntimeError('No public selected projects found')
    latest = max(projects, key=lambda repo: repo['pushedAt'] or '')
    return {
        'contributions': user['contributionsCollection']['contributionCalendar']['totalContributions'],
        'latest': latest,
        'updated': datetime.now(timezone.utc).strftime('%d %b %Y · %H:%M UTC'),
    }


def render(config, data, icons):
    parts = ['''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="842" viewBox="0 0 1000 842" role="img" aria-labelledby="title desc">
<title id="title">cankatdev GitHub profile</title>
<desc id="desc">Automatically refreshed public GitHub contributions, latest selected project, technology stack and education.</desc>''']

    def box(x, y, width, height, fill='#171717', stroke='#292929', radius=15):
        parts.append(f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" fill="{fill}" stroke="{stroke}"/>')

    def text(x, y, value, size=18, color='#efefef', weight=400, spacing=0):
        parts.append(f'<text x="{x}" y="{y}" fill="{color}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}" letter-spacing="{spacing}">{escape(str(value))}</text>')

    def label(x, y, value):
        text(x, y, value, 12, '#9b9b9b', 700, 1.3)

    def logo(name, x, y, size=28, color=None):
        root = ET.fromstring(icons[name])
        root.set('x', str(x))
        root.set('y', str(y))
        root.set('width', str(size))
        root.set('height', str(size))
        if color:
            root.set('fill', color)
        parts.append(ET.tostring(root, encoding='unicode'))

    box(1, 1, 998, 840, '#090909', '#292929', 20)
    parts.append('<circle cx="80" cy="82" r="35" fill="#141a24" stroke="#3889ff" stroke-width="2"/>')
    text(58, 91, '</>', 25, '#83b6ff', 700)
    text(136, 79, config['username'], 33, weight=700)
    text(136, 108, config['tagline'], 17, '#aaaaaa')

    box(44, 151, 443, 125)
    box(509, 151, 447, 125)
    label(66, 181, 'TOTAL CONTRIBUTIONS')
    text(66, 226, format(data['contributions'], ','), 36, '#3889ff', 700)
    text(66, 253, 'Past 12 months · Public GitHub activity', 12, '#858585')
    label(531, 181, 'LATEST WORK')
    latest = data['latest']
    display_name = latest['name']
    if len(display_name) > 29:
        display_name = display_name[:28] + '…'
    text(531, 220, display_name, 24, weight=700)
    language = latest['primaryLanguage'] or {'name': 'Project', 'color': '#8b949e'}
    color = language.get('color') or '#8b949e'
    parts.append(f'<circle cx="536" cy="245" r="5" fill="{escape(color, quote=True)}"/>')
    text(549, 251, language['name'], 15, '#aaaaaa')

    box(44, 296, 912, 143)
    label(66, 326, 'TECH STACK')
    technologies = config['languages'] + config['tools']
    for index, technology in enumerate(technologies):
        x = 66 + index * 87
        box(x, 345, 46, 44, '#252525', '#252525', 9)
        logo(technology['icon'], x + 8, 353, 28, technology.get('color'))
        text(x, 413, technology['label'], 12, '#a9a9a9', 600)

    box(44, 459, 443, 293)
    label(66, 490, 'EXPERIENCE & EDUCATION')
    parts.append('<path d="M81 528 V666" stroke="#303030" stroke-width="2"/>')
    for y, symbol in [(537, '01'), (665, '02')]:
        parts.append(f'<circle cx="81" cy="{y}" r="17" fill="#252525"/>')
        text(74, y + 4, symbol, 10, '#7b9ac5', 700)
    text(113, 535, 'ELTE', 21, weight=700)
    text(113, 561, config['education']['degree'], 16, '#b7b7b7')
    text(113, 587, config['education']['institution'], 14, '#858585')
    text(113, 661, config['hackathon']['project'], 20, weight=700)
    text(113, 687, config['hackathon']['achievement'], 15, '#b7b7b7')
    text(113, 713, 'Local AI · Recipe generation', 14, '#858585')

    box(509, 459, 447, 170)
    label(531, 490, 'FEATURED PROJECT')
    text(531, 531, 'FridgeChef AI', 25, weight=700)
    text(531, 559, 'Meal ideas from fridge photos.', 16, '#aaaaaa')
    text(531, 600, 'Python · Flask · Ollama', 14, '#88b3ed')

    box(509, 649, 447, 103)
    label(531, 679, 'ALSO BUILT')
    text(531, 709, 'IT Support Portal', 22, weight=700)
    text(531, 736, 'Power Apps · Dataverse · Power Automate', 14, '#aaaaaa')

    parts.append('<path d="M44 776 H956" stroke="#252525"/>')
    text(44, 808, config['subtitle'], 12, '#858585')
    text(570, 808, 'GitHub sync · ' + data['updated'], 11, '#737373')
    parts.append('</svg>')
    svg = '\n'.join(parts) + '\n'
    ET.fromstring(svg)
    return svg


def publish(svg, token):
    repository = os.environ['GITHUB_REPOSITORY']
    path = 'repos/' + repository + '/contents/profile-card.svg'
    current = api(path + '?ref=main', token)
    previous = base64.b64decode(current['content']).decode()
    if previous == svg:
        print('Profile is already current')
        return
    result = api(path, token, {
        'message': 'Refresh public GitHub profile data',
        'branch': 'main',
        'sha': current['sha'],
        'content': base64.b64encode(svg.encode()).decode(),
    }, method='PUT')
    # Immutable image URLs prevent GitHub's image proxy from retaining an older card.
    commit = result['commit']['sha']
    readme_path = 'repos/' + repository + '/contents/README.md'
    readme = api(readme_path + '?ref=main', token)
    content = base64.b64decode(readme['content']).decode()
    image_url = 'https://raw.githubusercontent.com/' + repository + '/' + commit + '/profile-card.svg'
    pattern = r'!\[cankatdev profile[^\]]*\]\([^\n)]+\)'
    replacement = '![cankatdev profile — refreshed automatically from GitHub](' + image_url + ')'
    updated, count = re.subn(pattern, replacement, content)
    if count != 1:
        raise RuntimeError('Expected exactly one profile image in README')
    api(readme_path, token, {
        'message': 'Point README at the refreshed profile card',
        'branch': 'main',
        'sha': readme['sha'],
        'content': base64.b64encode(updated.encode()).decode(),
    }, method='PUT')
    print('Profile card and README image refreshed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--fixture', type=Path)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    if args.fixture and args.publish:
        parser.error('Fixture data cannot be published')
    config = json.loads((ROOT / 'profile.json').read_text())
    icons = json.loads((ROOT / 'assets/icons.json').read_text())
    token = os.environ.get('GH_TOKEN', '')
    if args.fixture:
        data = json.loads(args.fixture.read_text())
    else:
        if not token:
            parser.error('GH_TOKEN is required for live GitHub data')
        data = fetch_data(config, token)
    svg = render(config, data, icons)
    (ROOT / 'profile-card.svg').write_text(svg)
    if args.publish:
        publish(svg, token)


if __name__ == '__main__':
    main()
