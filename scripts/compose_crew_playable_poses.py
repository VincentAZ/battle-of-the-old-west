"""Make a labeled contact sheet from actual Unreal pose captures, without modifying them."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw
from crew_unreal_contract import BASE
from crew_capture_reuse import audit_reuse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('slug')
    parser.add_argument('--candidate', action='store_true')
    args = parser.parse_args()
    out = BASE / args.slug
    assert out.resolve().parent == BASE.resolve(), 'Invalid slug'
    report = json.loads((out/('attack-candidate-captures.json' if args.candidate else 'unreal-pose-captures.json')).read_text())
    assert report['ok'] and report['existing_content_unchanged'] and report['component_pose_verified']
    for key, filename in [('rig_validation_sha256','rig-validation.json'), ('unreal_assets_sha256','unreal-assets.json')]:
        assert report[key] == hashlib.sha256((out/filename).read_bytes()).hexdigest(), 'Capture evidence is stale: '+filename
    rig = json.loads((out/'rig-validation.json').read_text())
    assets = json.loads((out/'unreal-assets.json').read_text())
    assert rig['project_sha256'] == report['rig_project_sha256'] == assets['rig_project_sha256'], 'Captured rig is stale'
    assert assets['rig_validation_sha256'] == report['rig_validation_sha256'], 'Constraints changed after import'
    captures = report['captures']
    audit_reuse(out, report)
    # Keep visual row order stable when only an updated attack was recaptured.
    def order(record):
        clip = ['MF_Unarmed_Walk_Fwd', 'MM_Idle', 'MM_Attack_01', 'MM_HitReact_Front_Lgt_01'].index(record['clip'])
        view = next((index for index, name in enumerate(('front', 'side', 'rear')) if 'walk-'+name in record['file']), 0)
        return clip, view, record['file']
    captures = sorted(captures, key=order)
    columns, width, height, label = 4, 480, 270, 28
    sheet = Image.new('RGB', (columns*width, ((len(captures)+columns-1)//columns)*(height+label)), '#20242a')
    draw = ImageDraw.Draw(sheet)
    for i, record in enumerate(captures):
        assert record['component_pose_sha256'] == hashlib.sha256(json.dumps(record['component_local_pose'],sort_keys=True).encode()).hexdigest(), 'Component pose evidence changed'
        assert record['pose_error']['translation_cm'] < .025 and record['pose_error']['quaternion_error'] < .002 and record['pose_error']['time_seconds'] < .0001
        path = out/record['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record['sha256'], 'Capture changed'
        image = Image.open(path).convert('RGB')
        assert list(image.size) == record['size']
        image.thumbnail((width,height))
        x,y = (i%columns)*width, (i//columns)*(height+label)
        sheet.paste(image, (x+(width-image.width)//2,y))
        draw.text((x+8,y+height+7), path.stem.removeprefix('Unreal-'), fill='white')
    target = out/('attack-candidate-contact.jpg' if args.candidate else 'unreal-pose-contact.jpg')
    sheet.save(target, quality=93)
    print(target)


if __name__ == '__main__':
    main()
