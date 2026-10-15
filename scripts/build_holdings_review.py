"""Audit the 34 Western Holdings and build an honest local static review index.

Run: python3 -I scripts/build_holdings_review.py [--baseline-only]

Reads local assets only; never submits generation jobs or authorizes rigging,
animation or game integration. References are explicitly distinguished from
validated, visually and historically reviewed mesh candidates. The first run
records baseline.json: the selected package, Git state and SHA-256 of every
protected game-source, catalog and prior Western review file.
"""
import argparse
import datetime
import hashlib
import html
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from holdings_roster import HOLDINGS, HOLDINGS_SET, REVIEW, ROOT, catalog  # noqa: E402

OUT = REVIEW
VIEWS = {'front', 'side', 'rear', 'three-quarter', 'game-camera', 'overhead', 'facade-detail', 'underside-diagnostic'}
PROTECTED_ROOTS = ('game/OldWest/Source', 'game/OldWest/Config', 'game/data', 'game/OldWest/Content/Data',
                   'art/western/crew', 'art/western/native', 'art/western/stampede', 'art/western/drifter',
                   'art/western/history')
EXPANSION = HOLDINGS_SET == 'boomtown'
if EXPANSION:
    # This authorized pass also changes presentation code and packages. Freeze
    # authoritative mechanics and prior art, while permitting that integration.
    PROTECTED_ROOTS = ('game/OldWest/Source/OldWestGame/Private/Core', 'game/data',
                       'game/OldWest/Content/Data', 'art/western/crew', 'art/western/native',
                       'art/western/stampede', 'art/western/drifter', 'art/western/history',
                       'art/western/holdings/review-v001', 'art/western/holdings/review-v002')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def protected_files():
    for base in PROTECTED_ROOTS:
        for path in sorted((ROOT / base).rglob('*')):
            if path.is_file() and not path.is_symlink() and path.suffix != '.zip':
                yield path


def write_baseline():
    paths = list(protected_files())
    with ProcessPoolExecutor() as pool:
        digests = list(pool.map(sha, paths, chunksize=16))
    baseline = {
        'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'git_status': subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True),
        'selected_package': str((ROOT / 'dist/current').resolve()),
        'protected_roots': list(PROTECTED_ROOTS),
        'protected_sha256': {str(p.relative_to(ROOT)): d for p, d in zip(paths, digests)},
        'preservation_note': 'Game rules, AI, catalogs, configuration and every prior approved Western review '
                             'source are protected. Review archives (.zip) are excluded from hashing only because '
                             'they duplicate hashed files.',
    }
    (OUT / 'baseline.json').write_text(json.dumps(baseline, indent=2) + '\n')
    return baseline


def contact_sheets(gallery):
    from PIL import Image, ImageDraw
    sheets = []
    items = [g for g in gallery if g.get('mesh_image')]
    if not items:
        return sheets
    per_sheet, columns, cell = 12, 4, (420, 340)
    for index in range(0, len(items), per_sheet):
        chunk = items[index:index + per_sheet]
        rows = (len(chunk) + columns - 1) // columns
        sheet = Image.new('RGB', (columns * cell[0], rows * cell[1]), (25, 28, 32))
        draw = ImageDraw.Draw(sheet)
        for n, item in enumerate(chunk):
            image = Image.open(OUT / item['mesh_image']).convert('RGB')
            image.thumbnail((cell[0] - 20, cell[1] - 50))
            x, y = (n % columns) * cell[0] + 10, (n // columns) * cell[1] + 10
            sheet.paste(image, (x, y))
            draw.text((x, y + cell[1] - 36), f"{item['name']}  ·  {item['canonical']}", fill=(231, 227, 218))
        name = f'Holdings-Static-Contact-{index // per_sheet + 1:02d}.jpg'
        sheet.save(OUT / name, quality=88)
        sheets.append(name)
    return sheets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-only', action='store_true')
    args = parser.parse_args()
    camps = catalog()
    baseline_path = OUT / 'baseline.json'
    baseline = json.loads(baseline_path.read_text()) if baseline_path.exists() else write_baseline()
    if args.baseline_only:
        print('HOLDINGS_BASELINE', len(baseline['protected_sha256']), 'protected files')
        return
    changed = [p for p, digest in baseline['protected_sha256'].items()
               if not (ROOT / p).is_file() or sha(ROOT / p) != digest]
    assert not changed, changed[:20]
    if not EXPANSION:
        assert str((ROOT / 'dist/current').resolve()) == baseline['selected_package']
    history_validation_path = OUT / 'history-validation.json'
    history_validation = json.loads(history_validation_path.read_text()) if history_validation_path.exists() else None
    approval_path = OUT / 'appearance-approval.json'
    approval = json.loads(approval_path.read_text()) if approval_path.exists() else None
    assets, gallery, figures = {}, [], []
    uniqueness = {'source_files': {}, 'references': {}}
    for card_id, (slug, name, setting, footprint, rationale) in HOLDINGS.items():
        directory = OUT / slug
        info = json.loads((directory / 'holding.json').read_text())
        assert info['canonical_card_id'] == card_id and info['display_name'] == name
        evidence_path = directory / 'historical-evidence.json'
        evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else None
        history_check = history_validation['holdings'].get(slug, {}) if history_validation else {}
        evidence_ok = bool(evidence and history_check and not history_check.get('issues', ['missing'])
                           and (not EXPANSION or history_check.get('evidence_sha256') == sha(evidence_path)))
        reference = directory / 'reference.png'
        reference_review_path = directory / 'reference-review.json'
        reference_review = json.loads(reference_review_path.read_text()) if reference_review_path.exists() else None
        reference_accepted = bool(reference.exists() and reference_review
                                  and reference_review.get('status') == 'accepted_for_static_mesh_generation'
                                  and reference_review.get('reference_sha256') == sha(reference))
        if reference.exists():
            digest = sha(reference)
            assert digest not in uniqueness['references'], ('duplicate reference', slug)
            uniqueness['references'][digest] = slug
        for request_name in ('reference-request.json', 'model-request.json'):
            if (directory / request_name).exists():
                request = json.loads((directory / request_name).read_text())
                assert request['service'] in {'image_gen', 'model_3d'}
                assert request['historical_evidence'] == 'historical-evidence.json'
        manifest_path = directory / 'review/manifest.json'
        validation_path = directory / 'review/validation.json'
        complete, visually_reviewed, historically_reviewed = False, False, False
        previews, review_notes, manifest = [], [], None
        visual, historical = None, None
        if manifest_path.exists() and validation_path.exists():
            manifest = json.loads(manifest_path.read_text())
            validation = json.loads(validation_path.read_text())
            assert validation['status'] == 'passed'
            assert sha(directory / 'review' / manifest['project']) == manifest['project_sha256']
            assert validation['project_sha256'] == manifest['project_sha256']
            assert manifest['holding']['canonical_card_id'] == card_id
            assert manifest['rigged'] is False and manifest['animations'] == []
            source = Path(manifest['source_glb'])
            assert sha(source) == manifest['source_sha256']
            assert manifest['source_sha256'] not in uniqueness['source_files'], ('duplicate source', slug)
            uniqueness['source_files'][manifest['source_sha256']] = slug
            assert {p['view'] for p in manifest['previews']} == VIEWS
            for item in manifest['textures'] + manifest['previews']:
                assert sha(directory / 'review' / item['file']) == item['sha256']
            complete = True
            previews = [{'view': p['view'], 'src': os.path.relpath(directory / 'review' / p['file'], OUT)}
                        for p in manifest['previews']]
            visual_path = directory / 'review/visual-review.json'
            if visual_path.exists():
                visual = json.loads(visual_path.read_text())
                review_notes = visual.get('notes', [])
                visually_reviewed = (visual.get('status') == 'passed'
                                     and visual.get('project_sha256') == manifest['project_sha256']
                                     and set(visual.get('views_reviewed', [])) == VIEWS)
            historical_path = directory / 'historical-review.json'
            if historical_path.exists():
                historical = json.loads(historical_path.read_text())
                historically_reviewed = (historical.get('status') == 'reviewed'
                                         and historical.get('project_sha256') == manifest['project_sha256'])
        status = ('mesh_ready_for_user_review' if complete and visually_reviewed and historically_reviewed else
                  'mesh_awaiting_visual_and_historical_qa' if complete else
                  'reference_accepted_awaiting_mesh' if reference_accepted else
                  'reference_awaiting_review' if reference.exists() else
                  'evidence_documented' if evidence_ok else 'brief_only')
        if approval:
            approved = approval['projects'][slug]
            assert complete and manifest['project_sha256'] == approved['sha256'], 'Approved project changed: ' + slug
            status = 'appearance_approved'
        assets[slug] = {'display_name': name, 'canonical_card_id': card_id, 'canonical_name': camps[card_id]['name'],
                        'setting': setting, 'footprint_m': footprint, 'directory': str(directory.relative_to(ROOT)),
                        'status': status, 'evidence_documented': evidence_ok,
                        'reference_downloaded': reference.exists(), 'reference_accepted': reference_accepted,
                        'validated_static_mesh': complete, 'mesh_visually_reviewed': visually_reviewed,
                        'mesh_historically_reviewed': historically_reviewed,
                        'verify_row': info['verify_row'], 'ability_summary': info['ability_summary'],
                        'review_notes': review_notes,
                        'rigging_or_animation_authorized': False, 'game_integration_authorized': EXPANSION}
        preview = directory / 'review/previews/three-quarter.png' if complete else reference
        if preview.exists():
            src = html.escape(os.path.relpath(preview, OUT), quote=True)
            title = html.escape(name)
            label = ('Static mesh · inspected · ready for your review' if complete and visually_reviewed and historically_reviewed else
                     'Static mesh · inspection pending' if complete else
                     'Reference accepted · mesh pending' if reference_accepted else
                     'Reference only · awaiting inspection')
            if approval:
                label = 'Approved appearance · still static, unrigged, not in game'
            mapping = f"Original: {camps[card_id]['name']} · {setting}"
            figures.append(f'<figure><a href="{src}"><img src="{src}" alt="{title}" loading="lazy"></a>'
                           f'<figcaption><strong>{title}</strong><span>{html.escape(mapping)}</span>'
                           f'<span>{label}</span></figcaption></figure>')
            gallery.append({'slug': slug, 'name': name, 'canonical': camps[card_id]['name'], 'setting': setting,
                            'label': label, 'ability': info['ability_summary'], 'rationale': rationale,
                            'verify': info['verify_row'],
                            'history': evidence, 'historyReview': historical,
                            'image': os.path.relpath(preview, OUT),
                            'mesh_image': os.path.relpath(preview, OUT) if complete else None,
                            'notes': review_notes,
                            'previews': previews or [{'view': 'reference', 'src': os.path.relpath(preview, OUT)}],
                            'project': os.path.relpath(directory / 'review' / manifest['project'], OUT) if complete else None})
    count = len(HOLDINGS)
    counts = {'holdings': count,
              'evidence_documented': sum(a['evidence_documented'] for a in assets.values()),
              'references': sum(a['reference_downloaded'] for a in assets.values()),
              'references_accepted': sum(a['reference_accepted'] for a in assets.values()),
              'validated_meshes': sum(a['validated_static_mesh'] for a in assets.values()),
              'meshes_visually_reviewed': sum(a['mesh_visually_reviewed'] for a in assets.values()),
              'meshes_historically_reviewed': sum(a['mesh_historically_reviewed'] for a in assets.values()),
              'protected_files_unchanged': len(baseline['protected_sha256'])}
    ready = counts['evidence_documented'] == counts['validated_meshes'] == counts['meshes_visually_reviewed'] == counts['meshes_historically_reviewed'] == count
    sheets = contact_sheets(gallery)
    report = {'counts': counts, 'assets': assets,
              'selected_package_at_baseline': baseline['selected_package'],
              'selected_package_unchanged': str((ROOT / 'dist/current').resolve()) == baseline['selected_package'],
              'contact_sheets': sheets,
              'uniqueness': {category: len(entries) for category, entries in uniqueness.items()},
              f'all_{count}_user_approved': bool(approval),
              'rigging_or_animation_authorized': False, 'game_integration_authorized': EXPANSION,
              'completion': 'appearance_approved' if approval else
                            f'ready_for_all_{count}_appearance_review' if ready else 'incomplete'}
    (OUT / 'roster-status.json').write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Western Holdings — base camps, static review</title><style>
body{margin:0;background:#191c20;color:#e7e3da;font:16px system-ui}header,main{max-width:1500px;margin:auto;padding:28px}
h1{font-size:28px;margin:0 0 12px}p{max-width:850px;line-height:1.6}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px}
figure{margin:0}img{width:100%;height:300px;object-fit:contain;background:#303237}figcaption{padding:12px 0;line-height:1.5}
strong,span{display:block}span{font-size:14px;color:#c8c3b8}a{color:inherit}footer{padding:28px}
</style><header><h1>Western Holdings · 34 base camps · static skins</h1>
<p>Each of the 34 revised base camps is matched to the Western holding named in the rebrand list. Canonical card IDs,
text, costs and mechanics are unchanged. Everything here is a static mesh skin: no rig, animation, Unreal import or
package change is authorized until you approve all 34 appearances.</p>'''
    if EXPANSION:
        page = page.replace('base camps', 'expansion camps').replace('34', str(count))
        page = page.replace('Each of the 32 revised expansion camps', 'Each of the 32 Boomtown holdings')
        page = page.replace('Everything here is a static mesh skin: no rig, animation, Unreal import or\npackage change is authorized until you approve all 32 appearances.',
                            'These are static skins. Playable review integration is authorized; final appearance approval remains yours.')
    page += (f'<p>All {count} models passed saved-source validation, eight-view visual inspection and a historical comparison '
             f'against their sourced evidence. All {count} holdings are ready for your appearance review.' if ready else
             f"<p>{counts['evidence_documented']} of {count} evidence files validated; {counts['references']} references downloaded "
             f"({counts['references_accepted']} accepted); {counts['validated_meshes']} meshes validated; "
             f"{counts['meshes_visually_reviewed']} visually inspected; {counts['meshes_historically_reviewed']} historically compared. "
             'This is not yet the complete approval set.')
    page += ('</p><p>Open History on each holding for the dated, sourced building facts and the reconstruction limits. '
             'Rows the rebrand list marked “verify” show the actual catalog ability so you can judge the name.</p>'
             '<label>Find <input id="query" type="search" placeholder="Holding, original camp or setting"></label><p id="shown"></p></header><main id="gallery">')
    page += ''.join(figures) + '</main><footer>Local Mixar assets. Buildings are documented period types, not surveyed replicas of a specific surviving structure unless the History says so.</footer>'
    page += '''<dialog id="detail"><button id="close" type="button">Close</button><nav class="nav" aria-label="Holding navigation"><button id="previous" type="button">← Previous</button><span id="position" aria-live="polite"></span><button id="next" type="button">Next →</button></nav><h2 id="detailName"></h2><p id="detailLabel"></p><p id="detailAbility"></p><label>View <select id="view"></select></label><img id="detailImage" alt=""><details id="history"><summary>History and historical accuracy</summary><p id="historyType"></p><p id="historyLesson"></p><ul id="historyFeatures"></ul><ul id="historyIssues"></ul><ul id="historySources"></ul></details><details id="reviewNotes"><summary>Inspection notes</summary><ul id="noteList"></ul></details><p><a id="project">Open editable Mixar source</a></p></dialog>
<style>input,select,button{font:inherit;padding:8px;background:#303237;color:#eee;border:1px solid #737373}figure button{border:0;padding:0;width:100%;cursor:pointer}dialog{width:min(1100px,92vw);max-height:94vh;background:#202429;color:#eee;border:1px solid #999}dialog::backdrop{background:#000b}#detailImage{display:block;width:100%;height:min(65vh,760px);object-fit:contain}#close{float:right}.nav{display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding-right:80px}.nav button:disabled{opacity:.4}</style>
<script>const data=GALLERY_DATA;
const g=document.getElementById('gallery'),query=document.getElementById('query'),d=document.getElementById('detail');
let visible=[],activeIndex=-1;
function render(){g.replaceChildren();visible=[];const q=query.value.toLowerCase();
for(const a of data){const mapping='Original: '+a.canonical+' · '+a.setting;if(!(a.name+' '+mapping).toLowerCase().includes(q))continue;
const f=document.createElement('figure'),b=document.createElement('button'),im=document.createElement('img'),cap=document.createElement('figcaption');im.src=a.image;im.alt=a.name;im.loading='lazy';b.append(im);const index=visible.length;visible.push({a,mapping});b.onclick=()=>openHolding(index);
for(const [tag,value] of [['strong',a.name],['span',mapping],['span',a.label]]){const e=document.createElement(tag);e.textContent=value;cap.append(e);}f.append(b,cap);g.append(f);}
document.getElementById('shown').textContent=visible.length+' holdings';}
function openHolding(index,keepView=false){if(!visible.length)return;const v=document.getElementById('view');const selected=keepView?v.selectedOptions[0]?.textContent:null;activeIndex=(index+visible.length)%visible.length;const {a,mapping}=visible[activeIndex];inspect(a,mapping,selected);document.getElementById('position').textContent=(activeIndex+1)+' / '+visible.length;document.getElementById('previous').disabled=document.getElementById('next').disabled=visible.length<2;}
function inspect(a,mapping,selected){document.getElementById('detailName').textContent=a.name;document.getElementById('detailLabel').textContent=mapping+' · '+a.label;document.getElementById('detailAbility').textContent=(a.verify?'Rebrand list said “verify”. Actual ability: ':'Ability: ')+a.ability+' — '+a.rationale;const v=document.getElementById('view');v.replaceChildren();for(const p of a.previews){const o=document.createElement('option');o.value=p.src;o.textContent=p.view;v.append(o);}v.value=(a.previews.find(p=>p.view===selected)?.src)||a.image;if(!v.value)v.selectedIndex=0;const im=document.getElementById('detailImage');im.alt=a.name+' review';v.onchange=()=>im.src=v.value;v.onchange();const link=document.getElementById('project');link.hidden=!a.project;if(a.project)link.href=a.project;const ns=document.getElementById('noteList'),details=document.getElementById('reviewNotes');ns.replaceChildren();details.hidden=!a.notes.length;details.open=false;for(const note of a.notes){const li=document.createElement('li');li.textContent=note;ns.append(li);}showHistory(a.history,a.historyReview);if(!d.open)d.showModal();}
function showHistory(h,review){
 document.getElementById('historyType').textContent=h?('Documented building type · '+(h.date_scope||'')+' · '+(h.location_scope||'')+' · '+(review?'Mesh compared with the evidence; differences recorded below':'Evidence recorded before rendering')):'Historical evidence pending';
 document.getElementById('historyLesson').textContent=h?.history_lesson||'A sourced history note is being prepared.';
 const feats=document.getElementById('historyFeatures'),issues=document.getElementById('historyIssues'),sources=document.getElementById('historySources');feats.replaceChildren();issues.replaceChildren();sources.replaceChildren();
 for(const f of h?.documented_features||[]){const li=document.createElement('li');li.textContent='Documented: '+f;feats.append(li);}
 for(const value of (review?[...(review.matches||[]).map(x=>'Matches evidence: '+x),...(review.differences||[]).map(x=>'Difference: '+x),...(review.remaining_uncertainties||[]).map(x=>'Reconstruction: '+x)]:(h?.uncertainties||[]).map(x=>'Reconstruction: '+x))){const li=document.createElement('li');li.textContent=value;issues.append(li);}
 for(const source of h?.sources||[]){const li=document.createElement('li'),a=document.createElement('a');a.textContent=source.title;a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';li.append(a,document.createTextNode(' — '+source.supports));sources.append(li);}
}
document.getElementById('previous').onclick=()=>openHolding(activeIndex-1,true);document.getElementById('next').onclick=()=>openHolding(activeIndex+1,true);
d.addEventListener('keydown',event=>{if(event.target.closest('select,input,textarea')||event.altKey||event.ctrlKey||event.metaKey)return;if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();openHolding(activeIndex+(event.key==='ArrowRight'?1:-1),true);}});
document.getElementById('close').onclick=()=>d.close();query.oninput=render;render();</script></html>'''.replace('GALLERY_DATA', json.dumps(gallery, ensure_ascii=False).replace('<', '\\u003c'))
    (OUT / 'index.html').write_text(page)
    print(json.dumps(counts, indent=2))
    print('HOLDINGS_REVIEW_INDEX', report['completion'], flush=True)


if __name__ == '__main__':
    main()
