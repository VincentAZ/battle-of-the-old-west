"""Audit all 46 Western Crew copies and build an honest local static review index.

Reads local assets only; never submits generation jobs or authorizes animation.
References are explicitly distinguished from completed, validated mesh reviews.
"""
import hashlib
import html
import json
import os
from pathlib import Path
from crew_geometry import geometry_fingerprint

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art/western/crew/review-v002'
ROSTER = {
    'bounty_hunter': ['bounty-hunter', 'tom-horn'],
    'hellfire_preacher': ['hellfire-preacher', 'revival-sister'],
    'pinkerton_agent': ['pinkerton-agent', 'lozen'],
    'regulator': ['regulator', 'billy-the-kid'],
    'gatling_gunner': ['gatling-gunner', 'coach-guard'],
    'widow_with_a_shotgun': ['widow-with-a-shotgun', 'homestead-defender'],
    'claim_jumper': ['claim-jumper', 'jesse-james'],
    'con_man': ['con-man', 'bass-reeves'],
    'bartender': ['bartender', 'piano-player'],
    'doc_holliday': ['doc-holliday', 'laudanum-doctor'],
    'barn_burner': ['barn-burner', 'railroad-saboteur'],
    'ringleader': ['ringleader', 'trail-organizer'],
    'blacksmith': ['blacksmith', 'carpenter'],
    'sarah_winnemucca': ['sarah-winnemucca', 'getaway-rider'],
    'prospector': ['prospector', 'assayer'],
    'rustler': ['rustler', 'drover'],
    'annie_oakley': ['annie-oakley', 'sharpshooter'],
    'duelist': ['duelist', 'wild-bill-hickok'],
    'vigilante': ['vigilante', 'town-avenger'],
    'civil_war_veteran': ['civil-war-veteran', 'buffalo-soldier-veteran'],
    'wyatt_earp': ['wyatt-earp'],
    'quanah_parker': ['quanah-parker'],
    'augustus_powder_pike': ['augustus-powder-pike'],
    'cornelius_ashby_railroad_baron': ['cornelius-ashby'],
    'charles_goodnight': ['charles-goodnight'],
    'poker_alice': ['poker-alice'],
}
EXISTING = {'quanah-parker', 'lozen', 'sarah-winnemucca'}
REVISE = {'pinkerton-agent', 'billy-the-kid', 'barn-burner'}
VIEWS = {'front', 'side', 'rear', 'three-quarter', 'game-camera',
         'face-detail', 'hands-detail', 'underside-diagnostic'}


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    cards = {c['id']: c for c in json.loads((ROOT / 'game/data/cards.json').read_text())['cards']
             if c['type'] == 'person'}
    assert set(cards) == set(ROSTER), 'Crew roster differs from canonical person catalog'
    assert all(len(slugs) == cards[cid]['copies'] for cid, slugs in ROSTER.items())
    assert sum(map(len, ROSTER.values())) == 46
    slugs = set(sum(ROSTER.values(), []))
    assert len(slugs) == 46 and len(slugs - EXISTING) == 43, 'Each copy requires its own character'
    assets = {}
    history = {}
    for audit_file in sorted((ROOT / 'research/crew-history-audit').glob('audit-*.json')):
        for entry in json.loads(audit_file.read_text()):
            assert entry['slug'] not in history, 'Duplicate historical audit entry'
            history[entry['slug']] = entry
    figures = []
    gallery = []
    uniqueness = {'source_files': {}, 'geometry': {}, 'basecolor_textures': {}}
    display_names = set()
    approval = json.loads((ROOT / 'art/western/native/review-v001/appearance-approval.json').read_text())
    crew_approval_path = ROOT / 'art/western/crew/review-v003/appearance-approval.json'
    crew_approval = json.loads(crew_approval_path.read_text()) if crew_approval_path.exists() else None
    if crew_approval:
        assert set(crew_approval['projects']) == slugs
        assert crew_approval['rigging_authorized'] and crew_approval['animation_and_game_integration_authorized']
    revision_file = OUT / 'historical-revisions.json'
    revisions = json.loads(revision_file.read_text()) if revision_file.exists() else {}
    assert not (set(revisions) & EXISTING), 'Preserve approved Native sources'
    for slug in sorted(slugs):
        old = slug in EXISTING
        directory = ROOT / 'art/western/native/review-v001' / slug if old else OUT / slug
        if slug in revisions:
            directory = (ROOT / revisions[slug]).resolve()
            assert directory.is_relative_to(ROOT / 'art/western/crew'), 'Revision must stay in Crew assets'
        info = json.loads((directory / 'character.json').read_text())
        request_directory = directory
        derivative_path = directory / 'orientation-correction-provenance.json'
        if derivative_path.exists():
            derivative = json.loads(derivative_path.read_text())
            original_project = (ROOT / derivative['source_project']).resolve()
            assert original_project.is_relative_to(ROOT / 'art/western/crew')
            assert sha(original_project) == derivative['source_project_sha256']
            request_directory = original_project.parent.parent
        assert info['display_name'].casefold() not in display_names, 'Repeated character name'
        display_names.add(info['display_name'].casefold())
        copies = [{'canonical_card_id': cid, 'copy': n}
                  for cid, names in ROSTER.items() for n, name in enumerate(names, 1) if name == slug]
        assert len(copies) == 1 and all(c['canonical_card_id'] == info['canonical_card_id'] for c in copies)
        if not old:
            assert sorted(info['copies']) == [c['copy'] for c in copies]
            for name in ('reference-request.json', 'model-request.json'):
                request = json.loads((request_directory / name).read_text())
                assert request['service'] in {'image_gen', 'model_3d'}
        mesh_review = directory / 'review/manifest.json'
        complete = False
        visually_reviewed = old
        previews = []
        review_notes = []
        if mesh_review.exists() and (directory / 'review/validation.json').is_file():
            manifest = json.loads(mesh_review.read_text())
            validation = json.loads((directory / 'review/validation.json').read_text())
            assert validation['status'] == 'passed'
            assert sha(directory / 'review' / manifest['project']) == manifest['project_sha256']
            assert validation['project_sha256'] == manifest['project_sha256']
            if old:
                assert manifest['project_sha256'] == approval['projects'][slug]['sha256']
            else:
                assert manifest['character']['canonical_card_id'] == info['canonical_card_id']
                assert manifest['character']['copies'] == info['copies']
            assert manifest['rigged'] is False and manifest['animations'] == []
            source = Path(manifest['source_glb'])
            assert sha(source) == manifest['source_sha256']
            geometry = geometry_fingerprint(source)
            basecolor = next(t for t in manifest['textures'] if t['channel'] == 'BaseColor')
            for category, digest in [('source_files', manifest['source_sha256']),
                                     ('geometry', geometry['sha256']),
                                     ('basecolor_textures', basecolor['sha256'])]:
                assert digest not in uniqueness[category], (category, slug, uniqueness[category].get(digest))
                uniqueness[category][digest] = slug
            assert len(manifest['previews']) == 8 and {p['view'] for p in manifest['previews']} == VIEWS
            for item in manifest['textures'] + manifest['previews']:
                assert sha(directory / 'review' / item['file']) == item['sha256']
            complete = True
            previews = [{'view': p['view'], 'src': os.path.relpath(directory / 'review' / p['file'], OUT)}
                        for p in manifest['previews']]
            visual_path = directory / 'review/visual-review.json'
            if not old and visual_path.exists():
                visual = json.loads(visual_path.read_text())
                review_notes = visual.get('notes', [])
                visually_reviewed = (visual.get('status') == 'passed'
                                     and visual.get('project_sha256') == manifest['project_sha256']
                                     and set(visual.get('views_reviewed', [])) == VIEWS)
        reference = request_directory / 'reference.png'
        if not old:
            current_request = json.loads((request_directory / 'model-request.json').read_text())
            if current_request.get('image'):
                reference = (request_directory / current_request['image']).resolve()
        history_review_path = directory / 'historical-review.json'
        history_review = json.loads(history_review_path.read_text()) if history_review_path.exists() else None
        entry_history = dict(history[slug]) if slug in history else None
        if history_review:
            assert complete and history_review['project_sha256'] == manifest['project_sha256'], 'Historical review must identify current saved model'
            assert history_review['status'] == 'reviewed'
            request = json.loads((request_directory / 'model-request.json').read_text())
            evidence = json.loads((request_directory / request['historical_evidence']).read_text())
            if entry_history:
                for key in ('date_scope', 'location_scope', 'history_lesson'):
                    entry_history[key] = history_review.get(key) or evidence.get(key) or entry_history.get(key)
                entry_history['historical_basis'] = 'Revised using the historical evidence below. Changes and remaining reconstruction details are recorded for your review.'
                entry_history['sources'] = list({s['url']: s for s in entry_history['sources'] + evidence['sources'] + history_review.get('sources', [])}.values())
        status = ('previously_approved_static_appearance' if old else
                  'mesh_ready_for_user_review' if complete and visually_reviewed else
                  'mesh_awaiting_visual_qa' if complete else
                  'reference_needs_revision' if slug in REVISE and reference.exists() else
                  'reference_only' if reference.exists() else 'brief_only')
        if crew_approval:
            approved = crew_approval['projects'][slug]
            assert complete and manifest['project_sha256'] == approved['sha256'], 'Approved project changed: ' + slug
            status = 'appearance_approved_integration_authorized'
        assets[slug] = {'display_name': info['display_name'], 'copies': copies,
                        'directory': str(directory.relative_to(ROOT)), 'status': status,
                        'reference_downloaded': reference.exists(),
                        'validated_static_mesh': complete, 'mesh_visually_reviewed': visually_reviewed,
                        'review_notes': review_notes,
                        'historical_revision_review': history_review,
                        'new_animation_authorized': bool(crew_approval)}
        preview = directory / 'review/previews/three-quarter.png' if complete else reference
        if preview.exists():
            src = html.escape(os.path.relpath(preview, OUT), quote=True)
            title = html.escape(info['display_name'])
            label = ('Previously approved mesh' if old else 'Static mesh review' if complete and visually_reviewed else
                     'Static mesh — revision or inspection pending' if complete else
                     'Reference needs correction' if slug in REVISE else 'Reference only — no mesh yet')
            if history_review:
                label = 'Historical revision · awaiting your review'
            elif history.get(slug, {}).get('decision') == 'revise':
                label = 'Historical correction in progress · previous mesh'
            if crew_approval:
                label = 'Approved appearance · rigging and game integration authorized'
            mapping = ', '.join(f"{cards[c['canonical_card_id']]['name']} #{c['copy']}" for c in copies)
            figures.append(f'<figure><a href="{src}"><img src="{src}" alt="{title}" loading="lazy"></a>'
                           f'<figcaption><strong>{title}</strong><span>{html.escape(mapping)}</span>'
                           f'<span>{label}</span></figcaption></figure>')
            gallery.append({'slug': slug, 'name': info['display_name'], 'label': label,
                            'history': entry_history,
                            'historyReview': history_review,
                            'copies': [{'name': cards[c['canonical_card_id']]['name'], **c} for c in copies],
                            'image': os.path.relpath(preview, OUT),
                            'notes': review_notes,
                            'previews': previews or [{'view': 'reference', 'src': os.path.relpath(preview, OUT)}],
                            'project': os.path.relpath(directory / 'review' / manifest['project'], OUT) if complete else None})
    baseline_path = ROOT / 'art/western/crew/review-v003/baseline.json' if revisions else OUT / 'baseline.json'
    if any('/review-v004/' in value for value in revisions.values()):
        baseline_path = ROOT / 'art/western/crew/review-v004/baseline.json'
    baseline = json.loads(baseline_path.read_text())
    protected = {p: digest for p, digest in baseline['protected_sha256'].items()
                 if not crew_approval or p.startswith('art/')}
    changed = [p for p, digest in protected.items()
               if not (ROOT / p).is_file() or sha(ROOT / p) != digest]
    assert not changed, changed
    if not crew_approval:
        assert str((ROOT / 'dist/current').resolve()) == baseline['selected_package']
    counts = {'card_copies': 46, 'distinct_appearances': 46, 'previously_approved': 3,
              'new_briefs': 43, 'new_references': sum(a['reference_downloaded'] for s, a in assets.items() if s not in EXISTING),
              'new_validated_meshes': sum(a['validated_static_mesh'] for s, a in assets.items() if s not in EXISTING),
              'new_meshes_visually_reviewed': sum(a['mesh_visually_reviewed'] for s, a in assets.items() if s not in EXISTING),
              'protected_files_unchanged': len(protected)}
    ready = (counts['new_validated_meshes'] == counts['new_meshes_visually_reviewed'] == 43
             and all(a['validated_static_mesh'] for a in assets.values()))
    pending_history = [slug for slug, entry in history.items()
                       if entry['decision'] == 'revise' and not assets[slug]['historical_revision_review']]
    service_path = OUT / 'service-state.json'
    service = json.loads(service_path.read_text()) if service_path.exists() else {'status': 'not_checked'}
    report = {'counts': counts, 'assets': assets, 'selected_package_unchanged': baseline['selected_package'],
              'historical_audit': {'documented_entries': len(history),
                  'revision_required': [slug for slug, entry in history.items() if entry['decision'] == 'revise'],
                  'pending_revisions': pending_history,
                  'completed_revisions': [slug for slug, asset in assets.items() if asset['historical_revision_review']],
                  'all_46_historically_approved': False},
              'uniqueness': {category: len(entries) for category, entries in uniqueness.items()},
              'all_46_user_approved': bool(crew_approval), 'new_animation_authorized': bool(crew_approval),
              'completion': ('historical_revisions_in_progress' if pending_history else 'ready_for_all_46_appearance_review') if ready else 'incomplete',
              'service': service}
    if crew_approval:
        report['completion'] = 'appearance_approved_integration_authorized'
        report['selected_package_unchanged'] = str((ROOT / 'dist/current').resolve()) == baseline['selected_package']
    (OUT / 'roster-status.json').write_text(json.dumps(report, indent=2) + '\n')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Western Crew — static work in progress</title><style>
body{margin:0;background:#191c20;color:#e7e3da;font:16px system-ui}header,main{max-width:1500px;margin:auto;padding:28px}
h1{font-size:28px;margin:0 0 12px}p{max-width:850px;line-height:1.6}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px}
figure{margin:0}img{width:100%;height:400px;object-fit:contain;background:#303237}figcaption{padding:12px 0;line-height:1.5}
strong,span{display:block}span{font-size:14px;color:#c8c3b8}a{color:inherit}footer{padding:28px}
</style><header><h1>Western Crew · Static work in progress</h1>
<p>46 card copies, 46 distinct people. No character is reused. Three approved Native appearances are preserved.
The new images below are generation references unless explicitly labeled as mesh reviews.
No new animation is authorized until the user approves all 46 copies.</p>'''
    page += (f'<p>Existing models passed technical inspection. {len(pending_history)} historical corrections are being prepared; the replacement set is not yet ready for approval.' if pending_history else
             '<p>All 43 new models passed saved-source validation and eight-view visual inspection. '
             'All 46 copies are ready for your appearance review.' if ready else
             f"<p>{counts['new_references']} of 43 new references downloaded; {counts['new_validated_meshes']} of 43 new meshes validated; {counts['new_meshes_visually_reviewed']} visually inspected. This is not yet the complete approval set.")
    page += f'</p><p>{len(history)} of 46 historical notes documented. Appearance inspection is not historical approval. Open History on each character for facts, sources, and corrections.</p><label>Find <input id="query" type="search" placeholder="Name or original card"></label><p id="shown"></p></header><main id="gallery">'
    page += ''.join(figures) + '</main><footer>Local Mixar assets. Historical likenesses and costume details remain artistic interpretations; Native tribal review remains separate.</footer>'
    page += '''<dialog id="detail"><button id="close" type="button">Close</button><nav class="character-nav" aria-label="Character navigation"><button id="previous" type="button" aria-label="Previous character">← Previous</button><span id="position" aria-live="polite"></span><button id="next" type="button" aria-label="Next character">Next →</button></nav><h2 id="detailName"></h2><p id="detailLabel"></p><label>View <select id="view"></select></label><img id="detailImage" alt=""><details id="history"><summary>History and historical accuracy</summary><p id="historyType"></p><p id="historyLesson"></p><p id="historyBasis"></p><ul id="historyIssues"></ul><ul id="historySources"></ul></details><details id="reviewNotes"><summary>Inspection notes</summary><ul id="noteList"></ul></details><p><a id="project">Open editable Mixar source</a></p></dialog>
<style>input,select,button{font:inherit;padding:8px;background:#303237;color:#eee;border:1px solid #737373}figure button{border:0;padding:0;width:100%;cursor:pointer}dialog{width:min(1100px,92vw);max-height:94vh;background:#202429;color:#eee;border:1px solid #999}dialog::backdrop{background:#000b}#detailImage{display:block;width:100%;height:min(65vh,760px);object-fit:contain}#close{float:right}.character-nav{display:flex;align-items:center;gap:16px;flex-wrap:wrap;padding-right:80px}.character-nav button:disabled{opacity:.4;cursor:default}</style>
<script>const data=GALLERY_DATA;
const g=document.getElementById('gallery'), query=document.getElementById('query'), d=document.getElementById('detail');
let visible=[],activeIndex=-1;
function render(){g.replaceChildren();visible=[];const q=query.value.toLowerCase();let count=0;
for(const a of data){const groups=a.copies.map(c=>[c]);
for(const cs of groups){const mapping=cs.map(c=>'Original: '+c.name+' · copy '+c.copy).join(', ');if(!(a.name+' '+mapping).toLowerCase().includes(q))continue;
const f=document.createElement('figure'),b=document.createElement('button'),im=document.createElement('img'),cap=document.createElement('figcaption');im.src=a.image;im.alt=a.name;im.loading='lazy';b.append(im);const index=visible.length;visible.push({a,mapping});b.onclick=()=>openCharacter(index);
for(const [tag,value] of [['strong',a.name],['span',mapping],['span',a.label]]){const e=document.createElement(tag);e.textContent=value;cap.append(e);}f.append(b,cap);g.append(f);count++;}}
document.getElementById('shown').textContent=count+' distinct characters';}
function openCharacter(index,keepView=false){if(!visible.length)return;const v=document.getElementById('view');const selected=keepView?v.selectedOptions[0]?.textContent:null;activeIndex=(index+visible.length)%visible.length;const {a,mapping}=visible[activeIndex];inspect(a,mapping,selected);document.getElementById('position').textContent=(activeIndex+1)+' / '+visible.length;document.getElementById('previous').disabled=document.getElementById('next').disabled=visible.length<2;}
function inspect(a,mapping,selected){document.getElementById('detailName').textContent=a.name;document.getElementById('detailLabel').textContent=mapping+' · '+a.label;const v=document.getElementById('view');v.replaceChildren();for(const p of a.previews){const o=document.createElement('option');o.value=p.src;o.textContent=p.view;v.append(o);}v.value=(a.previews.find(p=>p.view===selected)?.src)||a.image; if(!v.value)v.selectedIndex=0;const im=document.getElementById('detailImage');im.alt=a.name+' review';v.onchange=()=>im.src=v.value;v.onchange();const link=document.getElementById('project');link.hidden=!a.project;if(a.project)link.href=a.project;const ns=document.getElementById('noteList'),details=document.getElementById('reviewNotes');ns.replaceChildren();details.hidden=!a.notes.length;details.open=false;for(const note of a.notes){const li=document.createElement('li');li.textContent=note;ns.append(li);}showHistory(a.history,a.historyReview);if(!d.open)d.showModal();}
function showHistory(h,review){
 document.getElementById('historyType').textContent=h?(h.identity_type.replaceAll('_',' ')+' · '+(h.date_scope||'')+' · '+(h.location_scope||'')+' · '+(review?'Revision inspected; awaiting your approval':h.decision==='revise'?'Revision required':'Evidence recorded; reconstruction details disclosed below')):'Historical audit pending';
 document.getElementById('historyLesson').textContent=h?.history_lesson||'A sourced history note is being prepared.';
 document.getElementById('historyBasis').textContent=h?.historical_basis||'';
 const issues=document.getElementById('historyIssues'),sources=document.getElementById('historySources');issues.replaceChildren();sources.replaceChildren();
 for(const value of (review?[...(review.changes||[]).map(x=>'Changed: '+x),...(review.remaining_uncertainties||[]).map(x=>'Reconstruction: '+x)]:(h?.issues||[]))){const li=document.createElement('li');li.textContent=value;issues.append(li);}
 for(const source of h?.sources||[]){const li=document.createElement('li'),a=document.createElement('a');a.textContent=source.title;a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';li.append(a,document.createTextNode(' — '+source.supports));sources.append(li);}
}
document.getElementById('previous').onclick=()=>openCharacter(activeIndex-1,true);document.getElementById('next').onclick=()=>openCharacter(activeIndex+1,true);
d.addEventListener('keydown',event=>{if(event.target.closest('select,input,textarea')||event.altKey||event.ctrlKey||event.metaKey)return;if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();openCharacter(activeIndex+(event.key==='ArrowRight'?1:-1),true);}});
document.getElementById('close').onclick=()=>d.close();query.oninput=render;render();</script></html>'''.replace('GALLERY_DATA', json.dumps(gallery).replace('<', '\\u003c'))
    if ready:
        page = page.replace('Western Crew — static work in progress', 'Western Crew — 46 distinct characters')
        page = page.replace('Western Crew · Static work in progress', 'Western Crew · 46 distinct characters')
        page = page.replace('The new images below are generation references unless explicitly labeled as mesh reviews.',
                            'Every image below is a render of the saved 3D model. Click a figure to inspect all eight views.')
    if crew_approval:
        page = page.replace('No new animation is authorized until the user approves all 46 copies.',
                            'All 46 appearances approved. Rigging, animation and game integration are authorized.')
        page = page.replace('All 46 copies are ready for your appearance review.', 'All 46 appearances have user approval.')
        page = page.replace('Revision inspected; awaiting your approval', 'Appearance approved; reconstruction limits documented')
    (OUT / 'index.html').write_text(page)
    print(json.dumps(counts, indent=2))


if __name__ == '__main__':
    main()
