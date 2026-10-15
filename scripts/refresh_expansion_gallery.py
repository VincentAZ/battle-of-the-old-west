"""Refresh the existing expansion gallery from reviewed evidence only.

Keeps the established UI and development statuses; does not regenerate the
roster or overwrite its native integration records.
"""
import hashlib
import html
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'art/western/holdings/expansion-review-v001'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    roster = json.loads((OUT/'roster-status.json').read_text())
    gallery=[]; figures=[]; hashes=set(); ruin_scenes=[]
    for slug, asset in roster['assets'].items():
        if not asset['validated_static_mesh']:
            continue
        folder=OUT/slug
        review=ROOT/asset.get('review_directory',str((folder/'review').relative_to(ROOT)))
        manifest=json.loads((review/'manifest.json').read_text())
        validation=json.loads((review/'validation.json').read_text())
        # A later scene checkpoint may add base/ruin review without rewriting
        # the hash-pinned, model-only review that preceded it.
        visual_path=ROOT/asset['visual_review'] if asset.get('visual_review') else review/'visual-review.json'
        visual=json.loads(visual_path.read_text())
        info=json.loads((folder/'holding.json').read_text())
        history=json.loads((folder/'historical-evidence.json').read_text())
        digest=sha(review/manifest['project'])
        assert digest==manifest['project_sha256']==validation['project_sha256']==visual['project_sha256']
        assert validation['status']=='passed'
        source=Path(manifest['source_glb']); source_hash=sha(source)
        assert source_hash==manifest['source_sha256'] and source_hash not in hashes
        hashes.add(source_hash)
        assert asset['mesh_visually_reviewed'] and asset['mesh_historically_reviewed']
        previews=[]
        for item in manifest['previews']:
            p=review/item['file'];assert sha(p)==item['sha256']
            previews.append(dict(view=item['view'],src=str(p.relative_to(OUT))))
        # A separately rendered view must be explicitly inspected and tied to
        # the same saved project before it appears in the review gallery.
        supplemental=review/'right-veranda-render.json'
        if supplemental.exists():
            record=json.loads(supplemental.read_text())
            p=review/'previews/right-veranda.png'
            assert record['project_sha256']==digest
            assert 'right-veranda' in visual['actually_viewed']
            assert sha(p)==record['image_sha256']==visual['view_sha256']['right-veranda']
            previews.append(dict(view='right-veranda',src=str(p.relative_to(OUT))))
        image=next(p['src'] for p in previews if p['view']=='three-quarter')
        base_name=asset.get('base_directory')
        if base_name:
            base=ROOT/base_name
            base_validation=json.loads((base/'validation.json').read_text())
            base_visual=json.loads((base/'visual-review.json').read_text())
            assert base_validation['status']=='passed'
            assert base_validation['source_review_project_sha256']==digest
            assert sha(base/(slug+'-Base.blend'))==base_validation['project_sha256']
            if 'project_sha256' in base_visual:
                assert base_visual['project_sha256']==base_validation['project_sha256']
            else:
                assert base_visual['validation_sha256']==sha(base/'validation.json')
            assert base_visual['status'] in ('passed','reviewed',
                'agent_static_base_visual_and_historical_review_passed',
                'agent_static_visual_and_historical_review_passed',
                'agent_static_visual_and_historical_review_passed_native_pending')
            for view, record in base_validation['views'].items():
                p=base/(view+'.png'); assert sha(p)==record['image_sha256']
                previews.append(dict(view='setting-base-'+view,src=str(p.relative_to(OUT))))
            image=str((base/'three-quarter.png').relative_to(OUT))
        # Include only explicitly selected, reviewed authored ruins. Keep their
        # saved images and provenance; never infer readiness from a filename.
        ruin_review=asset.get('ruin_review')
        if ruin_review:
            ruin_visual_path=ROOT/ruin_review
            ruin=ruin_visual_path.parent
            ruin_visual=json.loads(ruin_visual_path.read_text())
            ruin_validation=json.loads((ruin/'validation.json').read_text())
            ruin_authoring=json.loads((ruin/'authoring.json').read_text())
            assert ruin_visual['status']=='agent_static_visual_review_passed_native_pending'
            assert ruin_validation['status']=='passed'
            project=next(ruin.glob('*-Ruin.blend'))
            assert sha(project)==ruin_visual['project_sha256']==ruin_validation['project_sha256']==ruin_authoring['project_sha256']
            assert set(ruin_validation['views'])=={'front','rear','right','overhead'}
            for view,digest in ruin_validation['views'].items():
                p=ruin/(view+'.png'); assert sha(p)==digest==ruin_authoring['views'][view]
                previews.append(dict(view='burned-out-'+view,src=str(p.relative_to(OUT))))
            ruin_scenes.append(slug)
        hpath=folder/'historical-review.json'
        historical=json.loads(hpath.read_text()) if hpath.exists() else dict(
            matches=visual.get('historical_basis',[]),
            differences=[],remaining_uncertainties=visual.get('reconstruction_disclosed',[]))
        label='Static scene reviewed · final approval pending'
        notes=asset.get('review_notes',[])+visual.get('notes',visual.get('visual_findings',[]))
        row=dict(slug=slug,name=info['display_name'],canonical=info['canonical_name'],
                 setting=info['setting'],label=label,ability=info['ability_summary'],
                 rationale=info['rationale'],verify=info['verify_row'],history=history,
                 historyReview=historical,image=image,mesh_image=next(p['src'] for p in previews if p['view']=='three-quarter'),
                 notes=list(dict.fromkeys(notes)),previews=previews,
                 project=str((review/manifest['project']).relative_to(OUT)))
        gallery.append(row)
        e=lambda s:html.escape(s,quote=True)
        figures.append(f'<figure><a href="{e(image)}"><img src="{e(image)}" alt="{e(row["name"])}" loading="lazy"></a>'
                       f'<figcaption><strong>{e(row["name"])}</strong><span>{e(row["canonical"])} · {e(row["setting"])}</span>'
                       f'<span>{e(label)}</span></figcaption></figure>')
    assert len(gallery)==roster['counts']['validated_meshes']
    path=OUT/'index.html'; page=path.read_text()
    # Preserve the exact previous index each time its contents change.
    archive=OUT/'gallery-history'/('index-'+sha(path)+'.html')
    archive.parent.mkdir(exist_ok=True)
    if not archive.exists(): archive.write_text(page)
    payload=json.dumps(gallery,ensure_ascii=False).replace('</',r'<\/')
    page,count=re.subn(r'<script>const data=.*?;\nconst g=',lambda _: '<script>const data='+payload+';\nconst g=',page,count=1,flags=re.S)
    assert count==1
    page,count=re.subn(r'<main id="gallery">.*?</main>',lambda _: '<main id="gallery">'+''.join(figures)+'</main>',page,count=1,flags=re.S)
    assert count==1
    summary=(f'<p>{roster["counts"]["evidence_documented"]} of 32 historical briefs prepared; '
             f'{len(gallery)} distinct static scenes reviewed. Development gameplay coverage varies by scene; '
             'the inspection notes record it. This is not the complete approval set.</p>')
    page,count=re.subn(r'<p>[^<]*?(?:evidence files validated|historical briefs prepared);.*?</p>',lambda _:summary,page,count=1)
    assert count==1
    path.write_text(page)
    result=dict(ok=True,scenes=len(gallery),distinct_sources=len(hashes),
                reviewed_ruin_scenes=ruin_scenes,
                scene_slugs=[x['slug'] for x in gallery],roster_sha256=sha(OUT/'roster-status.json'),
                index_sha256=sha(path),source_script_sha256=sha(Path(__file__)),
                scope='Gallery data and link/hash validation; layout and interaction code unchanged.')
    (OUT/'gallery-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print('EXPANSION_GALLERY_REFRESHED',len(gallery))


if __name__=='__main__':
    main()
