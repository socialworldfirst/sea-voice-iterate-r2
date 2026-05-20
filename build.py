"""SEA Voice Iterate — original → polish iteration + fact-check engine."""
import json, html, os, glob, re

DATA_DIR = '/Users/steven/Documents/Claude/sea-voice-iterate-r2/data'
OUT = '/Users/steven/Documents/Claude/sea-voice-iterate-r2/index.html'


def esc(s):
    return html.escape(str(s or ''))


def render_diff(markup):
    """Convert <del>...</del> and <ins>...</ins> markers in agent output to safe HTML.
    Agent output may contain raw < > so we sanitize everything else."""
    if not markup:
        return ''
    # Replace markers with placeholders, escape, then restore
    placeholders = {}
    counter = [0]
    def stash(match):
        tag = match.group(1)
        content = match.group(2)
        key = f"__DIFF_{counter[0]}__"
        counter[0] += 1
        placeholders[key] = (tag, content)
        return key
    s = re.sub(r'<(del|ins)>(.*?)</\1>', stash, markup, flags=re.DOTALL)
    s = html.escape(s)
    for key, (tag, content) in placeholders.items():
        css_class = 'diff-del' if tag == 'del' else 'diff-ins'
        s = s.replace(key, f'<span class="{css_class}">{html.escape(content)}</span>')
    return s


def _normalize_script(s):
    """Some agents used variant_id/variant_name instead of id/subtitle. Normalize."""
    if 'id' not in s and 'variant_id' in s:
        s['id'] = s['variant_id']
    if 'subtitle' not in s and 'variant_name' in s:
        s['subtitle'] = s['variant_name']
    return s


import re as _re


def load_hooks(slide_id):
    """Load per-card hooks for a slide.
    Returns a dict: {script_id: [hook,...]} for the new per_card schema.
    Falls back to {'_all': [...]} when only flat slide-level hooks are available."""
    path = os.path.join(os.path.dirname(__file__), 'hooks', f'{slide_id}.json')
    if not os.path.exists(path):
        return {}
    try:
        data = json.load(open(path))
        if 'per_card' in data and isinstance(data['per_card'], dict):
            return data['per_card']
        if 'hooks' in data and isinstance(data['hooks'], list):
            return {'_all': data['hooks']}
        return {}
    except Exception:
        return {}


def body_core(vo):
    """Strip the first sentence (the original embedded hook) so a library hook can lead instead."""
    if not vo:
        return ''
    m = _re.search(r'[.!?]\s', vo)
    if not m:
        return vo
    return vo[m.end():].strip()


def load_slide_data(slide_id):
    """Load per-slide combined JSON. Returns (hormozi, garyvee, factcheck) tuple or (None, None, {})."""
    path = os.path.join(DATA_DIR, slide_id, 'full.json')
    if not os.path.exists(path):
        return None, None, {}
    try:
        d = json.load(open(path))
        h = d.get('hormozi') or {}
        g = d.get('garyvee') or {}
        if h.get('scripts'):
            h['scripts'] = [_normalize_script(s) for s in h['scripts']]
        if g.get('scripts'):
            g['scripts'] = [_normalize_script(s) for s in g['scripts']]
        return h or None, g or None, d.get('factcheck', {})
    except Exception:
        return None, None, {}


# My ratings on the iterated (brand-polished) versions
def _rate(s, a, p, note):
    return {'social': s, 'audience': a, 'sales': p, 'overall': round((s+a+p)/3, 1), 'note': note}

RATINGS = {
    'PH1': _rate(4.2, 4.0, 4.3, "'This is not a fee problem. This is a hidden margin problem.' is a strong reframe line. Clean PAS rhythm intact after polish."),
    'PH2': _rate(4.5, 4.2, 4.3, "Compounding maths (1.2K → 28.8K/yr → 144K/5yr) lands hard. 'A salary. A warehouse. Your kid's college fund.' = concrete stakes."),
    'PH3': _rate(4.4, 3.9, 4.3, "Accusation opener is visceral. 'You signed off on it' might still feel slightly attacking — close to the line for SEA register."),
    'PH4': _rate(4.1, 4.1, 4.2, "'The fee is not the fee' = sharp reframe. 'Banks make billions' is a broad claim that could draw pushback."),
    'PH5': _rate(4.3, 4.1, 4.2, "1-2-3 structural reveal works well. Listing what you saw vs didn't see is clean teaching."),
    'PG1': _rate(4.0, 4.1, 4.2, "Lost some of the original Gary Vee punch after polish. Still works but feels closer to baseline."),
    'PG2': _rate(4.3, 4.1, 4.2, "'Your bank is the most expensive part of your supply chain' is the sharpest single line in this batch. Tight at 97 words."),
    'PG3': _rate(4.0, 4.2, 4.2, "Hammer/wood analogy is plain English and lands. 'Use the right tool for the job' is generic but clean."),
    'PG4': _rate(4.2, 4.1, 4.0, "'Your bank doesn't make money on the wire fee. They make money on the exchange rate.' = the kind of line a peer would quote. CTA soft — no explicit 'Search WorldFirst'."),
    'PG5': _rate(4.4, 4.3, 4.2, "Call-the-bank scenario is the most relatable in the batch. 'You sleep' close is a strong payoff line."),
}


def render_script(script_id, subtitle, original_vo, iterated_vo, diff_markup, skill_name='', factcheck=None, rating=None, rank=None, slide_id='', slide_hooks=None, iterated_vo_clarity='', ship_version_default='final'):
    diff_html = render_diff(diff_markup) if diff_markup else esc(iterated_vo)
    slide_hooks = slide_hooks or []
    core = body_core(iterated_vo)
    # Clarity body — graceful fallback to iterated_vo when not yet generated
    has_clarity_body = bool(iterated_vo_clarity and iterated_vo_clarity.strip())
    clarity_text = iterated_vo_clarity if has_clarity_body else iterated_vo
    core_clarity = body_core(clarity_text)
    # Hook options: library hooks (recommended first) + the variant's own original hook as last option
    opts = []
    rec_idx = 0
    for i, h in enumerate(slide_hooks):
        if h.get('recommended'):
            rec_idx = i
    ordered = ([slide_hooks[rec_idx]] + [h for i, h in enumerate(slide_hooks) if i != rec_idx]) if slide_hooks else []
    radio_name = f"hook-{esc(slide_id)}-{esc(script_id)}"
    for i, h in enumerate(ordered):
        cat = h.get('category', '').replace(' Hooks', '')
        htext = h.get('text', '')
        # Ultra Clarity is the explicit 7th hook genre — distinct visual class, special marker
        is_ultra = cat.lower().startswith('ultra clarity') or cat.lower() == 'ultra-clarity'
        ultra_class = ' hook-opt-ultra' if is_ultra else ''
        ultra_marker = '<span class="ho-ultra">✦</span>' if is_ultra else ''
        star = '<span class="ho-star">★</span>' if i == 0 else (ultra_marker or '<span class="ho-num">' + str(i+1) + '</span>')
        checked = ' checked' if i == 0 else ''
        rec_badge = '<span class="ho-rec">recommended</span>' if i == 0 else ''
        opts.append(
            f'<label class="hook-opt{ultra_class}">'
            f'<input type="radio" name="{radio_name}" class="hook-radio" '
            f'data-slide="{esc(slide_id)}" data-vid="{esc(script_id)}" '
            f'data-hook="{esc(htext)}" data-label="{esc(cat)}" data-val="{i}"{checked}>'
            f'<span class="ho-mark"></span>'
            f'<span class="ho-body">'
            f'<span class="ho-text">{esc(htext)}</span>'
            f'<span class="ho-meta">{star} <span class="ho-cat">{esc(cat)}</span> {rec_badge}</span>'
            f'</span>'
            f'</label>'
        )
    # original hook = the iterated_vo's own first sentence
    m = _re.search(r'[.!?]\s', iterated_vo or '')
    orig_hook = iterated_vo[:m.end()].strip() if m else (iterated_vo or '')
    opts.append(
        f'<label class="hook-opt hook-opt-orig">'
        f'<input type="radio" name="{radio_name}" class="hook-radio" '
        f'data-slide="{esc(slide_id)}" data-vid="{esc(script_id)}" '
        f'data-hook="{esc(orig_hook)}" data-label="Original" data-val="orig">'
        f'<span class="ho-mark"></span>'
        f'<span class="ho-body">'
        f'<span class="ho-text">{esc(orig_hook)}</span>'
        f'<span class="ho-meta"><span class="ho-num">·</span> <span class="ho-cat">Original</span></span>'
        f'</span>'
        f'</label>'
    )
    default_hook = ordered[0]['text'] if ordered else orig_hook
    hook_block = f'''
  <div class="hook-ctl">
    <div class="block-label">Hook · library-driven · click any to swap (★ = recommended default)</div>
    <div class="hook-opts" data-core="{esc(core)}">{''.join(opts)}</div>
  </div>'''

    # Tabbed VO view: Pure original → Brand polish → Final VO → Final VO (Clarity)
    # Default active tab = whichever version is the ship default (final or clarity)
    is_clarity_default = ship_version_default == 'clarity'
    final_tab_active = '' if is_clarity_default else ' active'
    clarity_tab_active = ' active' if is_clarity_default else ''
    final_pane_hidden = ' hidden' if is_clarity_default else ''
    clarity_pane_hidden = '' if is_clarity_default else ' hidden'
    final_rec_badge = '' if is_clarity_default else '<span class="vo-rec">★</span>'
    clarity_rec_badge = '<span class="vo-rec">★</span>' if is_clarity_default else ''
    clarity_word_count = len(clarity_text.split()) if has_clarity_body else 0
    clarity_pending_note = '' if has_clarity_body else '<div class="vo-pending">Clarity version pending generation. Showing Final VO as fallback.</div>'
    # Tabs ARE the ship-version selector. Clicking a tab = picking that version. Active tab = picked version.
    vo_tabs_block = f'''
  <div class="vo-tabs" data-slide="{esc(slide_id)}" data-vid="{esc(script_id)}">
    <div class="vo-tab-nav">
      <button class="vo-tab" data-tab="original" data-version="Pure original" type="button">Pure original</button>
      <span class="vo-arrow">→</span>
      <button class="vo-tab" data-tab="polish" data-version="Brand polish" type="button">Brand polish</button>
      <span class="vo-arrow">→</span>
      <button class="vo-tab{final_tab_active}" data-tab="final" data-version="Final VO" type="button">Final VO {final_rec_badge}</button>
      <span class="vo-arrow">→</span>
      <button class="vo-tab{clarity_tab_active}" data-tab="final-clarity" data-version="Final VO (Clarity)" type="button">Final VO (Clarity) {clarity_rec_badge}</button>
    </div>
    <div class="vo-pane" data-pane="original" hidden>
      <p class="vo vo-original">{esc(original_vo)}</p>
    </div>
    <div class="vo-pane" data-pane="polish" hidden>
      <p class="vo vo-iterated">{diff_html}</p>
      <div class="diff-legend"><span class="diff-del">deleted</span> / <span class="diff-ins">added</span></div>
    </div>
    <div class="vo-pane final-vo" data-pane="final" data-vid="{esc(script_id)}"{final_pane_hidden}>
      <p class="vo vo-final"><span class="fv-hook">{esc(default_hook)}</span> <span class="fv-core">{esc(core)}</span></p>
    </div>
    <div class="vo-pane final-vo-clarity" data-pane="final-clarity" data-vid="{esc(script_id)}"{clarity_pane_hidden}>
      {clarity_pending_note}
      <p class="vo vo-final"><span class="fv-hook">{esc(default_hook)}</span> <span class="fv-core-clarity">{esc(core_clarity)}</span></p>
      <div class="vo-clarity-meta">{clarity_word_count} words {"(longer, 5th-6th grade English, story-mode)" if has_clarity_body else ""}</div>
    </div>
  </div>'''

    heat_pill = ''
    fc_note_text = ''
    if factcheck:
        heat = factcheck.get('red_flag', 'Low')
        heat_class = f"heat-{heat.lower()}"
        heat_tooltip = esc(factcheck.get('analysis', ''))
        heat_pill = f'<span class="heat-pill {heat_class}" title="{heat_tooltip}"><span class="hl">Heat</span><span class="hv">{esc(heat)}</span></span>'
        fc_note_text = factcheck.get('analysis', '')

    rating_row = ''
    if rating:
        rating_row = f'''
    <div class="rating-row">
      <span class="rp social"><span class="rl">Soc</span><span class="rv">{rating.get('social', '-')}</span></span>
      <span class="rp audience"><span class="rl">Aud</span><span class="rv">{rating.get('audience', '-')}</span></span>
      <span class="rp sales"><span class="rl">Sales</span><span class="rv">{rating.get('sales', '-')}</span></span>
      <span class="overall"><span class="rl">Overall</span><span class="rv">{rating.get('overall', '-')}</span></span>
      {heat_pill}
    </div>
    <p class="rating-note">{esc(rating.get('note', ''))}</p>'''

    factcheck_block = ''
    if factcheck:
        comments = factcheck.get('skeptic_comments', [])
        comment_items = []
        hidden_count = 0
        for c in comments:
            # Handle both old string format and new {text, severity} format
            if isinstance(c, str):
                text = c
                severity = 'mid'
            else:
                text = c.get('text', '')
                severity = c.get('severity', 'mid')
            hide = severity != 'high'
            hidden_class = ' sc-hidden' if hide else ''
            if hide:
                hidden_count += 1
            comment_items.append(f'<li class="sc-{severity}{hidden_class}"><span class="sc-mark"></span><span class="sc-text">{esc(text)}</span></li>')
        comments_html = '\n'.join(comment_items)
        toggle_html = ''
        if hidden_count > 0:
            toggle_html = f'<button class="sc-toggle" type="button" data-collapsed-label="Show {hidden_count} more" data-expanded-label="Hide lower-severity">Show {hidden_count} more</button>'
        factcheck_block = f'''
  <div class="factcheck-block">
    <div class="fc-head">
      <span class="block-label">Skeptic test · what a Malaysian SMB might push back on</span>
    </div>
    <div class="skeptic-comments" data-collapsed="true">
      <ul>{comments_html}</ul>
      {toggle_html}
    </div>
  </div>'''

    rank_chip = f'<span class="rank-chip">#{rank}</span>' if rank else ''

    return f'''
<article class="script-card" data-script-id="{esc(script_id)}">
  <header class="script-head">
    <div class="script-row">
      {rank_chip}
      <span class="script-id">{esc(script_id)}</span>
      <span class="skill-tag">{esc(skill_name)}</span>
      <span class="word-count">{len(iterated_vo.split())} words</span>
    </div>
    <p class="script-subtitle">{esc(subtitle)}</p>
    {rating_row}
  </header>

  {hook_block}

  {vo_tabs_block}

  {factcheck_block}

  <div class="actions">
    <label class="winner-radio">
      <input type="checkbox" class="wr" data-slide="{esc(slide_id)}" data-vid="{esc(script_id)}">
      <span class="winner-mark"></span>
      <span class="winner-label">Pick this for {esc(slide_id)}</span>
    </label>
    <button class="copy-btn" data-vo="{esc(iterated_vo)}" type="button">Copy polished</button>
  </div>

  <textarea class="script-comment" data-slide="{esc(slide_id)}" data-vid="{esc(script_id)}" placeholder="Comment on this variant. What's working? What needs to change?"></textarea>
</article>'''


def render_combined_section(hormozi, garyvee, factcheck, slide_id=''):
    """Merge all scripts, sort by Claude overall desc, render single list."""
    all_scripts = []
    if hormozi:
        for s in hormozi.get('scripts', []):
            all_scripts.append((s, hormozi['skill']))
    if garyvee:
        for s in garyvee.get('scripts', []):
            all_scripts.append((s, garyvee['skill']))

    HEAT_RANK = {'low': 0, 'medium': 1, 'med': 1, 'high': 2}

    def sort_key(item):
        s, _ = item
        r = RATINGS.get(s['id'])
        ov = r['overall'] if r else 0
        fc = factcheck.get(s['id']) or {}
        heat = (fc.get('red_flag') or 'High').lower()
        # higher overall first; tie-break: lower heat first
        return (-ov, HEAT_RANK.get(heat, 99))

    all_scripts.sort(key=sort_key)
    slide_hooks_map = load_hooks(slide_id)  # dict: {script_id: [...]} or {'_all': [...]} fallback

    def hooks_for(script_id):
        return slide_hooks_map.get(script_id) or slide_hooks_map.get('_all') or []

    scripts_html = '\n'.join(
        render_script(
            s['id'],
            s.get('subtitle', ''),
            s.get('original_vo', ''),
            s.get('iterated_vo', ''),
            s.get('diff_markup', ''),
            skill_name=skill,
            factcheck=factcheck.get(s['id']),
            rating=RATINGS.get(s['id']),
            rank=i + 1,
            slide_id=slide_id,
            slide_hooks=hooks_for(s['id']),
            iterated_vo_clarity=s.get('iterated_vo_clarity', ''),
            ship_version_default=s.get('ship_version_default', 'final'),
        )
        for i, (s, skill) in enumerate(all_scripts)
    )
    return f'''
<section class="combined-section">
  <div class="scripts-stack">
    {scripts_html}
  </div>
</section>'''


# Slideshow config — one entry per produced idea from the SEA brand channel batch
# Loaded from slides.json (generated from picks_v3_enriched.json)
SLIDES_PATH = os.path.join(os.path.dirname(__file__), 'slides.json')
try:
    SLIDES_RAW = json.load(open(SLIDES_PATH))
except Exception:
    SLIDES_RAW = []

# Normalize keys to match what the rendering loop expects
SLIDES = []
for s in SLIDES_RAW:
    slide_id = s['slide_id']
    has_data = os.path.exists(os.path.join(DATA_DIR, slide_id, 'full.json'))
    SLIDES.append({
        'id': slide_id,
        'card_id': s['card_id'],
        'title': s['video_title'],
        'card_title': s.get('card_title', ''),
        'approach': s.get('approach', ''),
        'pillar': s.get('pillar', ''),
        'topic': s.get('topic', ''),
        'format_spec': s.get('format_spec', ''),
        'has_data': has_data,
    })

slides_with_data = sum(1 for s in SLIDES if s['has_data'])
total_scripts = slides_with_data * 10

pending_banner = ''
if slides_with_data < len(SLIDES):
    pending_banner = f'<div class="pending-banner"><strong>Producing…</strong> {slides_with_data} of {len(SLIDES)} slides ready ({total_scripts} scripts so far). Page rebuilds as each agent lands.</div>'

import json as _json_mod
json_slide_meta = _json_mod.dumps([{'id': s['id'], 'title': s['title']} for s in SLIDES])


HTML_PAGE = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex, nofollow">
<title>SEA Voice Iterate — original → polish + fact check</title>
<style>
:root {{
  --bg: #ffffff;
  --ink: #1d1d1f;
  --ink-soft: #424245;
  --ink-mute: #6e6e73;
  --line: #d2d2d7;
  --line-soft: #e8e8ed;
  --tint: #f5f5f7;
  --pick: #0a6d2f;
  --del: #b03060;
  --ins: #0a6d2f;
  --flag-low: #6e6e73;
  --flag-medium: #946100;
  --flag-high: #b03060;
  --social: #1a6dcc;
  --audience: #946100;
  --product: #b03060;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ background: var(--bg); color: var(--ink);
  font-family: -apple-system, "SF Pro Text", "Helvetica Neue", sans-serif;
  font-size: 16px; line-height: 1.55; -webkit-font-smoothing: antialiased; }}

.wrap {{ max-width: 1400px; margin: 0 auto; padding: 50px 50px 220px; }}

/* Slideshow nav */
.slide-nav {{ position: sticky; top: 0; z-index: 50; background: var(--bg);
  display: grid; grid-template-columns: 48px 1fr 48px; gap: 14px; align-items: center;
  padding: 14px 20px; border: 1px solid var(--line); border-radius: 100px;
  margin: 20px 0 32px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }}
.nav-btn {{ width: 44px; height: 44px; border-radius: 50%; border: 1px solid var(--line);
  background: var(--bg); color: var(--ink); font-size: 18px; cursor: pointer;
  transition: all 0.15s; display: flex; align-items: center; justify-content: center; }}
.nav-btn:hover:not(:disabled) {{ background: var(--ink); color: #fff; border-color: var(--ink); }}
.nav-btn:disabled {{ opacity: 0.3; cursor: not-allowed; }}
.slide-info {{ display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; justify-content: center; }}
.slide-counter {{ font-family: var(--mono); font-size: 11px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ink-mute); font-weight: 600;
  padding: 4px 10px; border: 1px solid var(--line); border-radius: 100px; }}
.picks-counter {{ font-family: var(--mono); font-size: 11px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ink-mute); font-weight: 600;
  padding: 4px 10px; border: 1px solid var(--line); border-radius: 100px;
  transition: color 0.15s, border-color 0.15s, background 0.15s; }}
.picks-counter.has-picks {{ color: var(--pick); border-color: var(--pick);
  background: rgba(10,109,47,0.06); }}
.slide-id {{ font-family: var(--mono); font-size: 13px; font-weight: 700;
  letter-spacing: 0.04em; color: var(--ink); }}
.slide-title {{ font-size: 14px; color: var(--ink-soft); font-weight: 500; }}

.slide-meta {{ display: flex; gap: 14px; flex-wrap: wrap; align-items: center;
  font-family: var(--mono); font-size: 11px; color: var(--ink-mute);
  letter-spacing: 0.04em; margin-bottom: 24px; padding-bottom: 16px;
  border-bottom: 1px solid var(--line-soft); }}

/* Needs-update flag — sends signal to next stage that this idea needs new variants */
.needs-update-btn {{ margin-left: auto; padding: 5px 12px; border: 1px solid var(--line);
  border-radius: 100px; background: var(--bg); color: var(--ink-mute);
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase;
  cursor: pointer; transition: all 0.15s; font-weight: 600; }}
.needs-update-btn:hover {{ border-color: var(--flag-medium); color: var(--flag-medium); }}
.needs-update-btn.flagged {{ background: rgba(148,97,0,0.08); border-color: var(--flag-medium);
  color: var(--flag-medium); font-weight: 700; }}
.needs-update-btn.flagged::before {{ content: '✦ '; }}

.slide-pending {{ padding: 40px 30px; border: 1px dashed var(--line); border-radius: 8px;
  background: var(--tint); text-align: center; }}
.slide-pending strong {{ display: block; font-size: 15px; margin-bottom: 8px; color: var(--ink); }}
.slide-pending p {{ font-size: 13px; color: var(--ink-soft); max-width: 520px;
  margin: 0 auto; line-height: 1.55; }}

/* Per-card hook control */
.hook-ctl {{ padding: 14px 20px; border-top: 1px solid var(--line-s);
  background: rgba(10,109,47,0.035); }}
.hook-opts {{ display: flex; flex-direction: column; gap: 2px; margin-bottom: 14px; }}
.hook-opt {{ display: grid; grid-template-columns: 16px 1fr; gap: 8px;
  align-items: center; padding: 4px 10px; border: 1px solid var(--line);
  border-radius: 5px; background: var(--bg); cursor: pointer; position: relative;
  transition: border-color 0.12s, background 0.12s; min-height: 28px; }}
.hook-opt:hover {{ border-color: var(--pick); }}
.hook-opt input {{ position: absolute; opacity: 0; }}
.ho-mark {{ width: 12px; height: 12px; border: 2px solid var(--line);
  border-radius: 50%; position: relative; transition: all 0.12s; flex-shrink: 0; }}
.hook-opt input:checked ~ .ho-mark {{ border-color: var(--pick); }}
.hook-opt input:checked ~ .ho-mark::after {{ content: ''; display: block;
  width: 4px; height: 4px; border-radius: 50%; background: var(--pick);
  position: absolute; top: 2px; left: 2px; }}
.hook-opt:has(input:checked) {{ border-color: var(--pick);
  background: rgba(10,109,47,0.06); }}
.ho-body {{ display: flex; flex-direction: row; align-items: baseline; gap: 12px;
  min-width: 0; flex-wrap: nowrap; justify-content: space-between; }}
.ho-meta {{ display: inline-flex; align-items: center; gap: 6px;
  font-family: var(--mono); font-size: 9px; letter-spacing: 0.06em;
  text-transform: uppercase; color: var(--ink-mute); flex-shrink: 0;
  margin-left: auto; }}
.ho-star {{ color: var(--pick); font-size: 11px; }}
.ho-num {{ color: var(--ink-mute); font-size: 9px; }}
.ho-cat {{ color: var(--ink-mute); font-weight: 600; }}
.hook-opt input:checked ~ .ho-body .ho-cat {{ color: var(--pick); }}
.ho-rec {{ font-size: 8px; letter-spacing: 0.06em; color: var(--pick);
  background: rgba(10,109,47,0.10); padding: 1px 5px; border-radius: 100px;
  font-weight: 700; }}
.ho-text {{ font-size: 13px; line-height: 1.35; color: var(--ink);
  font-family: ui-serif, "New York", "Iowan Old Style", Georgia, serif;
  flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }}
.hook-opt:has(input:checked) .ho-text {{ white-space: normal; }}
.hook-opt-orig {{ border-style: dashed; }}
.hook-opt-orig .ho-text {{ color: var(--ink-soft); }}
@media (max-width: 700px) {{
  .hook-opt {{ padding: 5px 8px; min-height: 30px; }}
  .ho-body {{ flex-direction: row; gap: 8px; }}
  .ho-meta {{ font-size: 8px; }}
  .ho-text {{ font-size: 12.5px; }}
}}

.fv-hook {{ font-weight: 700; color: var(--pick); }}
.fv-core {{ color: var(--ink); }}

.hero {{ padding-bottom: 28px; border-bottom: 1px solid var(--line); margin-bottom: 40px; }}
.kicker {{ font-family: var(--mono); font-size: 11px; letter-spacing: 0.12em;
  text-transform: uppercase; color: var(--ink-mute); margin-bottom: 12px; }}
h1 {{ font-size: 30px; line-height: 1.18; letter-spacing: -0.02em; font-weight: 600; margin-bottom: 12px; }}
.lede {{ font-size: 16px; color: var(--ink-soft); max-width: 760px; line-height: 1.55; }}
.pending-banner {{ margin-top: 18px; padding: 12px 18px; border: 1px solid var(--line);
  border-radius: 6px; background: var(--tint); font-size: 13px; color: var(--ink-soft); }}

.skill-section {{ margin-bottom: 60px; }}
.skill-head {{ padding-bottom: 14px; border-bottom: 1px solid var(--ink); margin-bottom: 26px; }}
.skill-head h2 {{ font-size: 22px; font-weight: 700; letter-spacing: -0.01em; }}
.skill-blurb {{ font-size: 13px; color: var(--ink-soft); margin-top: 4px; font-style: italic; }}

.scripts-stack {{ display: flex; flex-direction: column; gap: 28px; }}

.script-card {{ border: 1px solid var(--line); border-radius: 10px; padding: 0; overflow: hidden;
  background: var(--bg); transition: border-color 0.15s, box-shadow 0.15s; }}
.script-card.winner {{ border-color: var(--pick); box-shadow: 0 0 0 2px rgba(10,109,47,0.1); }}

.script-head {{ padding: 16px 22px 14px; background: var(--tint); border-bottom: 1px solid var(--line-soft); }}
.script-row {{ display: flex; gap: 10px; align-items: baseline; margin-bottom: 4px; flex-wrap: wrap; }}
.rank-chip {{ font-family: var(--mono); font-size: 12px; font-weight: 700; color: var(--pick);
  padding: 2px 8px; border: 1px solid var(--pick); border-radius: 100px; letter-spacing: 0.04em; }}
.script-id {{ font-family: var(--mono); font-size: 14px; font-weight: 700; letter-spacing: 0.06em; }}
.skill-tag {{ font-family: var(--mono); font-size: 10px; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--ink-mute); padding: 2px 8px;
  border: 1px solid var(--line); border-radius: 100px; }}
.word-count {{ font-family: var(--mono); font-size: 11px; color: var(--ink-mute); margin-left: auto; }}
.script-subtitle {{ font-size: 13px; color: var(--ink-soft); font-style: italic; margin-bottom: 12px; }}

/* Inline rating row in header */
.script-head .rating-row {{ display: flex; gap: 6px; align-items: baseline; flex-wrap: wrap; margin: 0; }}
.script-head .rating-note {{ font-size: 12px; color: var(--ink-soft); font-style: italic; line-height: 1.5; margin-top: 8px; padding: 0; }}

/* Heat pill */
.heat-pill {{ display: inline-flex; align-items: baseline; gap: 4px; padding: 2px 8px;
  border-radius: 100px; font-family: var(--mono); font-weight: 600;
  border: 1px solid currentColor; margin-left: 4px; cursor: help; }}
.heat-pill .hl {{ font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase; opacity: 0.8; }}
.heat-pill .hv {{ font-size: 10px; }}
.heat-low {{ color: var(--flag-low); background: rgba(110,110,115,0.06); }}
.heat-medium {{ color: var(--flag-medium); background: rgba(148,97,0,0.08); }}
.heat-high {{ color: var(--flag-high); background: rgba(176,48,96,0.08); }}

/* Tabbed VO view: Pure original → Brand polish → Final VO */
.vo-tabs {{ border-top: 1px solid var(--line-soft); border-bottom: 1px solid var(--line-soft); }}
.vo-tab-nav {{ display: flex; align-items: center; gap: 6px; padding: 10px 22px;
  background: var(--tint); border-bottom: 1px solid var(--line-soft); flex-wrap: wrap; }}
.vo-tab {{ font-family: var(--mono); font-size: 10px; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--ink-mute); font-weight: 600;
  padding: 5px 11px; border: 1px solid var(--line); border-radius: 100px;
  background: var(--bg); cursor: pointer; transition: all 0.15s; }}
.vo-tab:hover {{ color: var(--ink); border-color: var(--ink-soft); }}
.vo-tab.active {{ color: var(--pick); border-color: var(--pick);
  background: rgba(10,109,47,0.08); }}
.vo-arrow {{ font-family: var(--mono); font-size: 12px; color: var(--ink-mute); user-select: none; }}
.vo-pane {{ padding: 18px 22px; }}
.vo-pane[hidden] {{ display: none; }}
.vo-pane.final-vo {{ background: rgba(10,109,47,0.025); border-top: 0;
  border: 0; border-radius: 0; }}
.vo-pane.final-vo .vo-final {{ font-size: 15px; line-height: 1.65; }}
.vo-pane[data-pane="original"] {{ background: rgba(0,0,0,0.012); }}
.vo-pane[data-pane="polish"] {{ background: rgba(10,109,47,0.015); }}
.diff-legend {{ font-family: var(--mono); font-size: 9px; letter-spacing: 0.06em;
  color: var(--ink-mute); margin-top: 8px; }}
.diff-legend .diff-del, .diff-legend .diff-ins {{ padding: 0 4px; border-radius: 3px; }}

/* Final VO (Clarity) pane meta + pending banner */
.vo-pane.final-vo-clarity {{ background: rgba(10,109,47,0.045); }}
.vo-pane.final-vo-clarity .fv-core-clarity {{ color: var(--ink); }}
.vo-clarity-meta {{ margin-top: 10px; font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.06em; color: var(--ink-mute); }}
.vo-pending {{ font-family: var(--mono); font-size: 11px; color: var(--ink-mute);
  padding: 8px 12px; background: rgba(0,0,0,0.04); border-radius: 6px; margin-bottom: 10px;
  border-left: 3px solid var(--ink-mute); }}

/* Recommended marker on a tab (★ = Claude's default ship version) */
.vo-rec {{ display: inline-block; margin-left: 4px; color: var(--pick); font-size: 11px; font-weight: 700; }}
.vo-tab.active .vo-rec {{ color: var(--pick); }}

/* Ultra Clarity hook — distinct visual */
.hook-opt-ultra {{ border-color: rgba(148,97,0,0.30); background: rgba(148,97,0,0.04); }}
.hook-opt-ultra:hover {{ border-color: rgba(148,97,0,0.55); }}
.hook-opt-ultra:has(input:checked) {{ border-color: rgba(148,97,0,0.85);
  background: rgba(148,97,0,0.10); }}
.hook-opt-ultra .ho-text {{ color: rgba(80,53,0,0.95); }}
.hook-opt-ultra:has(input:checked) .ho-text {{ color: rgba(80,53,0,1); font-weight: 500; }}
.ho-ultra {{ color: rgba(148,97,0,0.90); font-size: 11px; }}
.hook-opt-ultra .ho-cat {{ color: rgba(148,97,0,0.95); font-weight: 700; }}

.block-label {{ font-family: var(--mono); font-size: 10px; letter-spacing: 0.1em;
  text-transform: uppercase; color: var(--ink-mute); font-weight: 600; margin-bottom: 10px;
  display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }}
.legend {{ font-family: var(--mono); font-size: 9px; letter-spacing: 0.06em;
  text-transform: none; color: var(--ink-mute); }}
.legend .diff-del, .legend .diff-ins {{ padding: 0 4px; border-radius: 3px; }}

.vo {{ font-size: 14.5px; line-height: 1.65; color: var(--ink);
  font-family: ui-serif, "New York", "Iowan Old Style", Georgia, serif;
  letter-spacing: 0.005em; }}
.vo-original {{ color: var(--ink-soft); }}
.diff-del {{ text-decoration: line-through; color: var(--del); background: rgba(176,48,96,0.08); padding: 0 2px; border-radius: 2px; }}
.diff-ins {{ color: var(--ins); background: rgba(10,109,47,0.12); padding: 0 2px; border-radius: 2px; font-weight: 500; }}

/* Rating chips (used inline in header now) */
.rp {{ display: inline-flex; align-items: baseline; gap: 3px; padding: 2px 7px;
  border-radius: 100px; font-family: var(--mono); font-weight: 600; }}
.rp .rl {{ font-size: 9px; letter-spacing: 0.06em; text-transform: uppercase; opacity: 0.85; }}
.rp .rv {{ font-size: 10px; }}
.rp.social {{ background: rgba(26,109,204,0.13); color: var(--social); }}
.rp.audience {{ background: rgba(148,97,0,0.13); color: var(--audience); }}
.rp.sales {{ background: rgba(176,48,96,0.13); color: var(--product); }}
.overall {{ display: inline-flex; align-items: baseline; gap: 4px; padding: 2px 8px;
  margin-left: 4px; padding-left: 10px; border-left: 1px solid var(--line);
  font-family: var(--mono); font-weight: 700; color: var(--ink); }}
.overall .rl {{ font-size: 9px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-mute); font-weight: 600; }}
.overall .rv {{ font-size: 13px; }}

.factcheck-block {{ padding: 14px 22px; border-bottom: 1px solid var(--line-soft);
  background: rgba(176,48,96,0.03); }}
.fc-head {{ margin-bottom: 8px; }}
.fc-note {{ font-size: 12.5px; color: var(--ink-soft); line-height: 1.55; margin-bottom: 10px; font-style: italic; }}
.skeptic-comments {{ margin-top: 8px; }}
.sc-label {{ font-family: var(--mono); font-size: 9px; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--ink-mute); margin-bottom: 6px; font-weight: 600; }}
.skeptic-comments ul {{ list-style: none; padding-left: 0; }}
.skeptic-comments li {{ font-size: 13px; line-height: 1.5;
  padding: 7px 12px 7px 14px; border-left: 3px solid; background: rgba(0,0,0,0.018);
  border-radius: 0 4px 4px 0; margin-bottom: 4px; font-style: italic;
  display: grid; grid-template-columns: 14px 1fr; gap: 8px; align-items: start; }}
.sc-mark {{ width: 8px; height: 8px; border-radius: 50%; margin-top: 6px; }}
.sc-text {{ }}
.skeptic-comments li.sc-high {{ border-left-color: var(--flag-high); background: rgba(176,48,96,0.06); color: var(--ink); }}
.skeptic-comments li.sc-high .sc-mark {{ background: var(--flag-high); }}
.skeptic-comments li.sc-high .sc-text {{ color: var(--ink); font-weight: 500; }}
.skeptic-comments li.sc-mid {{ border-left-color: var(--flag-medium); color: var(--ink-soft); }}
.skeptic-comments li.sc-mid .sc-mark {{ background: var(--flag-medium); opacity: 0.6; }}
.skeptic-comments li.sc-low {{ border-left-color: var(--line); color: var(--ink-mute); }}
.skeptic-comments li.sc-low .sc-mark {{ background: var(--ink-mute); opacity: 0.4; }}
.skeptic-comments[data-collapsed="true"] li.sc-hidden {{ display: none; }}
.sc-toggle {{ font-family: var(--mono); font-size: 10px; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--ink-mute); font-weight: 600;
  background: none; border: 0; padding: 8px 0 2px; cursor: pointer;
  transition: color 0.15s; }}
.sc-toggle:hover {{ color: var(--ink); }}
.sc-toggle::before {{ content: '▾ '; }}
.skeptic-comments[data-collapsed="false"] .sc-toggle::before {{ content: '▴ '; }}

.actions {{ padding: 14px 22px; display: flex; justify-content: space-between; align-items: center; gap: 8px; flex-wrap: wrap; }}
.winner-radio {{ position: relative; display: inline-flex; align-items: center; gap: 8px; cursor: pointer; font-size: 12px; color: var(--ink-soft); font-family: var(--mono); letter-spacing: 0.04em; }}
.winner-radio input {{ position: absolute; opacity: 0; }}
.winner-mark {{ width: 18px; height: 18px; border: 2px solid var(--line); border-radius: 4px; background: var(--bg); position: relative; transition: all 0.15s; }}
.winner-radio input:checked ~ .winner-mark {{ border-color: var(--pick); background: var(--pick); }}
.winner-radio input:checked ~ .winner-mark::after {{ content: ''; display: block; width: 5px; height: 9px; border: solid #fff; border-width: 0 2px 2px 0; transform: rotate(45deg); position: absolute; top: 1px; left: 5px; }}
.winner-radio input:checked ~ .winner-label {{ color: var(--pick); font-weight: 600; }}
.copy-btn {{ padding: 7px 14px; background: var(--bg); border: 1px solid var(--line); border-radius: 100px;
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--ink-mute); cursor: pointer; }}
.copy-btn:hover {{ color: var(--ink); border-color: var(--ink); }}
.copy-btn.copied {{ background: var(--pick); color: #fff; border-color: var(--pick); }}

.script-comment {{ width: calc(100% - 44px); margin: 0 22px 18px; padding: 9px 12px;
  border: 1px solid var(--line); border-radius: 6px; font-family: inherit; font-size: 13px;
  line-height: 1.5; resize: vertical; min-height: 50px; background: var(--bg); }}
.script-comment:focus {{ outline: 1px solid var(--ink); border-color: var(--ink); }}
.script-comment::placeholder {{ color: rgba(0,0,0,0.32); }}

.bottom-panel {{ position: fixed; bottom: 0; left: 0; right: 0; background: var(--ink); color: #fff;
  z-index: 100; box-shadow: 0 -2px 16px rgba(0,0,0,0.18); }}
.bottom-panel.collapsed .panel-body {{ display: none; }}
.panel-bar {{ display: flex; align-items: center; justify-content: space-between;
  padding: 14px 22px; cursor: pointer; gap: 12px; min-height: 56px; }}
.panel-count {{ font-size: 14px; font-weight: 500; }}
.panel-count .count-zero {{ color: #888; font-weight: 400; }}
.panel-toggle {{ font-family: var(--mono); font-size: 11px; color: #aaa;
  text-transform: uppercase; letter-spacing: 0.05em; }}
.panel-body {{ padding: 6px 22px 18px; max-height: 60vh; overflow-y: auto; }}
.panel-label {{ display: block; font-family: var(--mono); font-size: 10px; color: #aaa;
  text-transform: uppercase; letter-spacing: 0.06em; margin: 10px 0 6px; }}
.panel-prompt {{ width: 100%; min-height: 200px; padding: 14px;
  border: 1px solid rgba(255,255,255,0.15); border-radius: 6px;
  background: rgba(255,255,255,0.05); color: #fff; font-family: var(--mono);
  font-size: 12px; line-height: 1.55; resize: vertical; white-space: pre-wrap; box-sizing: border-box; }}
.panel-actions {{ display: flex; gap: 8px; margin-top: 12px; flex-wrap: wrap; }}
.panel-btn {{ padding: 11px 18px; border-radius: 8px; font-size: 13px;
  font-weight: 500; cursor: pointer; border: none; min-height: 44px; font-family: inherit; }}
.btn-copy {{ background: #fff; color: #111; }}
.btn-copy.copied {{ background: var(--pick); color: #fff; }}

@media (max-width: 700px) {{
  .wrap {{ padding: 28px 14px 210px; }}
  h1 {{ font-size: 22px; }}
  .slide-nav {{ grid-template-columns: 40px 1fr 40px; gap: 8px; padding: 12px 12px; }}
  .nav-btn {{ width: 38px; height: 38px; font-size: 16px; }}
  .slide-info {{ gap: 6px; }}
  .slide-title {{ font-size: 12px; }}
  .script-card {{ border-radius: 8px; }}
  .script-head, .hook-ctl, .factcheck-block, .actions, .vo-pane, .vo-tab-nav {{ padding-left: 14px; padding-right: 14px; }}
  .rating-row {{ gap: 4px; }}
  .rp, .overall, .heat-pill {{ font-size: 9px; padding: 2px 6px; }}
  .hook-select {{ font-size: 14px; padding: 11px 12px; }}
  .vo-tab {{ font-size: 9px; padding: 4px 9px; }}
  .vo-arrow {{ font-size: 11px; }}
  .vo-pane.final-vo .vo-final {{ font-size: 15px; }}
  .script-comment {{ width: calc(100% - 28px); margin: 0 14px 16px; font-size: 14px; }}
  .vo, .vo-iterated, .vo-original, .vo-final {{ font-size: 14.5px; }}
  .skeptic-comments li {{ grid-template-columns: 12px 1fr; font-size: 13px; }}
  .panel-bar {{ padding: 13px 14px; }}
  .panel-body {{ padding: 6px 14px 16px; }}
  .bottom-panel textarea {{ font-size: 12px; }}
}}
@media (max-width: 420px) {{
  .slide-info {{ flex-wrap: wrap; }}
  .skill-tag {{ display: none; }}
}}
</style>
</head>
<body>
<div class="wrap">

<div class="hero">
  <div class="kicker">Sparkloop · /spark_script · round 2 · pending review</div>
  <h1>Round 2 - pending review</h1>
</div>

<!-- Slideshow nav -->
<div class="slide-nav">
  <button class="nav-btn" id="prevBtn" title="Previous idea (←)">←</button>
  <div class="slide-info">
    <span class="slide-counter" id="slideCounter">Idea 1 of {len(SLIDES)}</span>
    <span class="picks-counter" id="picksCounter">— picked</span>
    <span class="slide-id" id="slideId">{esc(SLIDES[0]['id'])}</span>
    <span class="slide-title" id="slideTitle">{esc(SLIDES[0]['title'])}</span>
  </div>
  <button class="nav-btn" id="nextBtn" title="Next idea (→)">→</button>
</div>

<div class="slides-container">
  {chr(10).join(
    f'<div class="slide" data-slide-id="{esc(s["id"])}" data-slide-idx="{i}" style="display:{ "block" if i == 0 else "none"};">'
    + f'<div class="slide-meta"><span class="sm-card">Card {esc(s["card_id"])}</span><span class="sm-pillar">Pillar {esc(s["pillar"])}</span><span class="sm-format">{esc(s["format_spec"])}</span><span class="sm-topic">Topic {esc(s["topic"])}</span><span class="sm-approach">{esc(s["approach"])}</span><button type="button" class="needs-update-btn" data-slide="{esc(s["id"])}">Needs update</button></div>'
    + (
        (lambda data: render_combined_section(data[0], data[1], data[2], slide_id=s['id']) if data[0] and data[1] else f'<div class="slide-pending"><strong>Voice variants pending generation.</strong><p>Agent for {esc(s["id"])} is still running. Page rebuilds as each lands.</p></div>')(load_slide_data(s['id']))
    )
    + '</div>'
    for i, s in enumerate(SLIDES)
  )}
</div>

</div>

<div class="bottom-panel collapsed" id="panel">
  <div class="panel-bar" id="panelBar">
    <div class="panel-count" id="panelCount"><span class="count-zero">0 picked · 0 comments</span></div>
    <div class="panel-toggle" id="panelToggle">expand ↑</div>
  </div>
  <div class="panel-body">
    <span class="panel-label">Voice iterate paste-back</span>
    <textarea class="panel-prompt" id="panelPrompt" readonly></textarea>
    <div class="panel-actions">
      <button class="panel-btn btn-copy" id="btnCopy">Copy prompt</button>
    </div>
  </div>
</div>

<script>
const STORAGE_KEY = 'sea_voice_iterate_r2';
const TOTAL_SLIDES = {len(SLIDES)};
function loadState() {{
  try {{ return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{{"picks":{{}},"comments":{{}}}}'); }}
  catch (e) {{ return {{picks: {{}}, comments: {{}}}}; }}
}}
function saveState(s) {{ localStorage.setItem(STORAGE_KEY, JSON.stringify(s)); }}
let state = loadState();
if (!state.picks) state.picks = {{}};
if (!state.comments) state.comments = {{}};
if (!state.hookpick) state.hookpick = {{}};
if (!state.versionpick) state.versionpick = {{}};
if (!state.needsUpdate) state.needsUpdate = {{}};
// Migrate legacy lowercase version labels to the new 4-tab labels
const VER_MIGRATE = {{ 'final': 'Final VO', 'clarity': 'Final VO (Clarity)' }};
Object.keys(state.versionpick).forEach(k => {{
  const v = state.versionpick[k];
  if (VER_MIGRATE[v]) state.versionpick[k] = VER_MIGRATE[v];
}});
// Migrate legacy single-string picks to array form (state.picks[slide] = [vid, ...])
Object.keys(state.picks).forEach(k => {{
  if (typeof state.picks[k] === 'string') state.picks[k] = [state.picks[k]];
  else if (!Array.isArray(state.picks[k])) state.picks[k] = [];
}});

// Hydrate per-slide picks (state.picks = {{ slideId: [scriptId, ...] }} — multi-pick)
document.querySelectorAll('.wr').forEach(cb => {{
  const slide = cb.getAttribute('data-slide');
  const vid = cb.getAttribute('data-vid');
  const arr = state.picks[slide] || [];
  if (arr.includes(vid)) {{ cb.checked = true; cb.closest('.script-card').classList.add('winner'); }}
}});
// Hydrate per-slide comments (key = slide::scriptId)
document.querySelectorAll('.script-comment').forEach(ta => {{
  const key = ta.getAttribute('data-slide') + '::' + ta.getAttribute('data-vid');
  if (state.comments[key]) ta.value = state.comments[key];
}});

// Multi-pick checkboxes: native toggle, multiple scripts per idea allowed
document.querySelectorAll('.wr').forEach(cb => {{
  cb.addEventListener('change', () => {{
    const slide = cb.getAttribute('data-slide');
    const vid = cb.getAttribute('data-vid');
    const card = cb.closest('.script-card');
    if (!state.picks[slide]) state.picks[slide] = [];
    const arr = state.picks[slide];
    if (cb.checked) {{
      if (!arr.includes(vid)) arr.push(vid);
      if (card) card.classList.add('winner');
    }} else {{
      const i = arr.indexOf(vid);
      if (i >= 0) arr.splice(i, 1);
      if (card) card.classList.remove('winner');
      if (arr.length === 0) delete state.picks[slide];
    }}
    saveState(state); updatePanel();
  }});
}});
document.querySelectorAll('.script-comment').forEach(ta => {{
  ta.addEventListener('input', () => {{
    const key = ta.getAttribute('data-slide') + '::' + ta.getAttribute('data-vid');
    if (ta.value.trim()) state.comments[key] = ta.value; else delete state.comments[key];
    saveState(state); updatePanel();
  }});
}});
// Per-card hook radios (state.hookpick = {{ "slide::vid": {{label, text}} }})
if (!state.hookpick) state.hookpick = {{}};
// Restore saved picks if present
document.querySelectorAll('.hook-radio').forEach(rb => {{
  const slide = rb.getAttribute('data-slide');
  const vid = rb.getAttribute('data-vid');
  const key = slide + '::' + vid;
  const hookText = rb.getAttribute('data-hook');
  if (state.hookpick[key] && state.hookpick[key].text === hookText) rb.checked = true;
}});
// Seed defaults from currently-checked radios so paste-back reflects what's visible on screen
document.querySelectorAll('.hook-radio:checked').forEach(rb => {{
  const slide = rb.getAttribute('data-slide');
  const vid = rb.getAttribute('data-vid');
  const key = slide + '::' + vid;
  if (!state.hookpick[key]) {{
    state.hookpick[key] = {{
      label: rb.getAttribute('data-label') || '',
      text: rb.getAttribute('data-hook') || ''
    }};
  }}
}});
// Sync visible Final + Clarity panes with current checked hook radio (each slide)
function syncFinalPanes(slideEl, vid, hookText) {{
  if (!slideEl) return;
  slideEl.querySelectorAll('.vo-pane[data-vid="' + vid + '"]').forEach(p => {{
    const h = p.querySelector('.fv-hook');
    if (h) h.textContent = hookText;
  }});
}}
document.querySelectorAll('.slide').forEach(sl => {{
  sl.querySelectorAll('.hook-radio:checked').forEach(rb => {{
    syncFinalPanes(sl, rb.getAttribute('data-vid'), rb.getAttribute('data-hook') || '');
  }});
}});
saveState(state);
document.querySelectorAll('.hook-radio').forEach(rb => {{
  rb.addEventListener('change', () => {{
    const slide = rb.getAttribute('data-slide');
    const vid = rb.getAttribute('data-vid');
    const key = slide + '::' + vid;
    const hook = rb.getAttribute('data-hook') || '';
    const label = rb.getAttribute('data-label') || '';
    // Update BOTH Final + Final (Clarity) panes inside this slide
    syncFinalPanes(rb.closest('.slide'), vid, hook);
    // Always record the active hook (including 'orig') so paste-back captures the current choice
    state.hookpick[key] = {{ label: label, text: hook }};
    saveState(state); updatePanel();
  }});
}});

// VO tabs ARE the ship-version selector. Active tab = picked version. No separate radio.
if (!state.versionpick) state.versionpick = {{}};
// Restore saved tab from state, OR seed default from server-rendered active tab
document.querySelectorAll('.vo-tabs').forEach(wrap => {{
  const slide = wrap.getAttribute('data-slide');
  const vid = wrap.getAttribute('data-vid');
  const key = slide + '::' + vid;
  const saved = state.versionpick[key];
  if (saved) {{
    // Find tab whose data-version matches the saved label
    const match = wrap.querySelector('.vo-tab[data-version="' + saved + '"]');
    if (match) {{
      wrap.querySelectorAll('.vo-tab').forEach(t => t.classList.toggle('active', t === match));
      const target = match.getAttribute('data-tab');
      wrap.querySelectorAll('.vo-pane').forEach(p => {{ p.hidden = p.getAttribute('data-pane') !== target; }});
    }}
  }} else {{
    // Seed from server-rendered active tab so paste-back has it even before user clicks
    const active = wrap.querySelector('.vo-tab.active');
    if (active) state.versionpick[key] = active.getAttribute('data-version');
  }}
}});
saveState(state);
document.querySelectorAll('.copy-btn').forEach(btn => {{
  btn.addEventListener('click', async (e) => {{
    e.stopPropagation();
    const vo = btn.getAttribute('data-vo');
    try {{ await navigator.clipboard.writeText(vo); btn.textContent = 'Copied'; btn.classList.add('copied');
      setTimeout(() => {{ btn.textContent = 'Copy polished'; btn.classList.remove('copied'); }}, 1500);
    }} catch (e) {{ console.error(e); }}
  }});
}});

// VO tabs — clicking a tab BOTH switches view AND records that as the ship version
document.querySelectorAll('.vo-tab').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const wrap = btn.closest('.vo-tabs');
    if (!wrap) return;
    const target = btn.getAttribute('data-tab');
    const version = btn.getAttribute('data-version');
    wrap.querySelectorAll('.vo-tab').forEach(t => t.classList.toggle('active', t === btn));
    wrap.querySelectorAll('.vo-pane').forEach(p => {{
      p.hidden = p.getAttribute('data-pane') !== target;
    }});
    const slide = wrap.getAttribute('data-slide');
    const vid = wrap.getAttribute('data-vid');
    if (slide && vid) {{
      state.versionpick[slide + '::' + vid] = version;
      saveState(state); updatePanel();
    }}
  }});
}});

// Skeptic comments toggle — show only high-severity by default, expand to all
document.querySelectorAll('.sc-toggle').forEach(btn => {{
  btn.addEventListener('click', () => {{
    const wrap = btn.closest('.skeptic-comments');
    if (!wrap) return;
    const collapsed = wrap.getAttribute('data-collapsed') === 'true';
    wrap.setAttribute('data-collapsed', collapsed ? 'false' : 'true');
    btn.textContent = collapsed
      ? btn.getAttribute('data-expanded-label')
      : btn.getAttribute('data-collapsed-label');
  }});
}});

// Needs-update flag per slide — signal to regenerate variants for this idea
document.querySelectorAll('.needs-update-btn').forEach(btn => {{
  const slide = btn.getAttribute('data-slide');
  if (state.needsUpdate[slide]) btn.classList.add('flagged');
  btn.addEventListener('click', () => {{
    const flagged = btn.classList.toggle('flagged');
    if (flagged) state.needsUpdate[slide] = true;
    else delete state.needsUpdate[slide];
    saveState(state); updatePanel();
  }});
}});

function buildPrompt() {{
  const lines = ['== SEA Voice Iterate paste-back =='];
  lines.push('');
  // Slides that have at least one pick
  const slidesWithPicks = Object.entries(state.picks).filter(([k, v]) => Array.isArray(v) && v.length > 0);
  const totalPicks = slidesWithPicks.reduce((acc, [k, v]) => acc + v.length, 0);
  lines.push(`PICKS (${{totalPicks}} scripts across ${{slidesWithPicks.length}} of ${{TOTAL_SLIDES}} ideas):`);
  if (slidesWithPicks.length === 0) lines.push('  (none yet)');
  // Order by DOM slide order; list every picked vid per slide with its chosen hook + version
  document.querySelectorAll('.slide').forEach(sl => {{
    const sid = sl.getAttribute('data-slide-id');
    const arr = state.picks[sid] || [];
    arr.forEach(vid => {{
      let line = `  ${{sid}} -> ${{vid}}`;
      const key = sid + '::' + vid;
      const ver = (state.versionpick && state.versionpick[key]) || 'Final VO';
      line += ` · VERSION[${{ver}}]`;
      const hp = state.hookpick && state.hookpick[key];
      if (hp) line += ` · HOOK[${{hp.label}}]: "${{hp.text}}"`;
      lines.push(line);
    }});
  }});
  const commentEntries = Object.entries(state.comments).filter(([k, v]) => (v || '').trim());
  lines.push('');
  lines.push(`COMMENTS (${{commentEntries.length}}):`);
  if (commentEntries.length === 0) lines.push('  (none)');
  commentEntries.forEach(([key, c]) => {{ lines.push(`  ${{key}}: "${{c.trim()}}"`); }});
  // Needs-update flags — slides that need fresh variants generated
  const needsUpdateIds = Object.keys(state.needsUpdate || {{}}).filter(k => state.needsUpdate[k]);
  lines.push('');
  lines.push(`NEEDS UPDATE (${{needsUpdateIds.length}}) — regenerate variants for these ideas:`);
  if (needsUpdateIds.length === 0) lines.push('  (none)');
  // Order by DOM
  document.querySelectorAll('.slide').forEach(sl => {{
    const sid = sl.getAttribute('data-slide-id');
    if (state.needsUpdate[sid]) lines.push(`  ${{sid}}`);
  }});
  lines.push('');
  lines.push('Action: each picked script = a final variant to ship for that idea. Multiple picks per idea = ship multiple. Comments = rework notes. NEEDS UPDATE = regenerate the 10 variants for that idea (fresh hook + body).');
  return lines.join('\\n');
}}
function updatePanel() {{
  const slidesWithPicks = Object.entries(state.picks).filter(([k, v]) => Array.isArray(v) && v.length > 0).length;
  const totalPicks = Object.values(state.picks).reduce((acc, v) => acc + (Array.isArray(v) ? v.length : 0), 0);
  const c = Object.values(state.comments).filter(v => (v || '').trim()).length;
  const ctx = document.getElementById('panelCount');
  if (totalPicks === 0 && c === 0) {{ ctx.innerHTML = '<span class="count-zero">0 scripts picked · 0 comments</span>'; }}
  else {{ ctx.textContent = `${{totalPicks}} scripts picked across ${{slidesWithPicks}} ideas · ${{c}} comments`; }}
  document.getElementById('panelPrompt').value = buildPrompt();
  updateIdeaPicksCounter();
}}
// Show "X / N picked" for the CURRENT idea only — X = picks in this slide, N = scripts in this slide
// Finds the visible slide directly (not via currentSlide index) so it works before the slideshow init runs
function updateIdeaPicksCounter() {{
  const pc = document.getElementById('picksCounter');
  if (!pc) return;
  let cur = null;
  document.querySelectorAll('.slide').forEach(sl => {{
    if (sl.style.display !== 'none' && !cur) cur = sl;
  }});
  if (!cur) cur = document.querySelector('.slide');
  if (!cur) return;
  const sid = cur.getAttribute('data-slide-id');
  const cards = cur.querySelectorAll('.script-card');
  const N = cards.length;
  const arr = state.picks && state.picks[sid];
  const X = Array.isArray(arr) ? arr.length : 0;
  pc.textContent = X + ' / ' + N + ' picked';
  pc.classList.toggle('has-picks', X > 0);
}}
const panel = document.getElementById('panel');
document.getElementById('panelBar').addEventListener('click', () => {{
  panel.classList.toggle('collapsed');
  document.getElementById('panelToggle').textContent = panel.classList.contains('collapsed') ? 'expand ↑' : 'collapse ↓';
}});
document.getElementById('btnCopy').addEventListener('click', async () => {{
  const text = document.getElementById('panelPrompt').value;
  try {{ await navigator.clipboard.writeText(text); const btn = document.getElementById('btnCopy');
    btn.textContent = 'Copied'; btn.classList.add('copied');
    setTimeout(() => {{ btn.textContent = 'Copy prompt'; btn.classList.remove('copied'); }}, 1500);
  }} catch (e) {{ console.error(e); }}
}});
updatePanel();

// ========== SLIDESHOW NAVIGATION ==========
const slides = document.querySelectorAll('.slide');
const totalSlides = slides.length;
let currentSlide = 0;

const prevBtn = document.getElementById('prevBtn');
const nextBtn = document.getElementById('nextBtn');
const slideCounter = document.getElementById('slideCounter');
const slideIdEl = document.getElementById('slideId');
const slideTitleEl = document.getElementById('slideTitle');

const SLIDE_META = {json_slide_meta};

function showSlide(idx) {{
  if (idx < 0 || idx >= totalSlides) return;
  slides.forEach((s, i) => {{ s.style.display = i === idx ? 'block' : 'none'; }});
  currentSlide = idx;
  slideCounter.textContent = `Idea ${{idx + 1}} of ${{totalSlides}}`;
  const meta = SLIDE_META[idx];
  if (meta) {{
    slideIdEl.textContent = meta.id;
    slideTitleEl.textContent = meta.title;
  }}
  prevBtn.disabled = idx === 0;
  nextBtn.disabled = idx === totalSlides - 1;
  updateIdeaPicksCounter();
  window.scrollTo({{top: 0, behavior: 'smooth'}});
}}

prevBtn.addEventListener('click', () => showSlide(currentSlide - 1));
nextBtn.addEventListener('click', () => showSlide(currentSlide + 1));

document.addEventListener('keydown', (e) => {{
  if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
  if (e.key === 'ArrowLeft') {{ e.preventDefault(); showSlide(currentSlide - 1); }}
  if (e.key === 'ArrowRight') {{ e.preventDefault(); showSlide(currentSlide + 1); }}
}});

showSlide(0);

</script>
</body>
</html>
'''

with open(OUT, 'w') as f:
    f.write(HTML_PAGE)

print(f"Built: {OUT}")
print(f"Slides with data: {slides_with_data} of {len(SLIDES)}")
print(f"Total scripts: {total_scripts}")
