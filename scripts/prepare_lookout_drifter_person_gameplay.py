"""Find a legal privately inspected person underneath Lookout Ridge exposure."""
import argparse
import hashlib
import json
from pathlib import Path

from prepare_lookout_drifter_gameplay import ROOT, rehearse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bridge', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists()
    rejected = []
    for seed in range(1, 2001):
        try:
            result = rehearse(args.bridge, seed)
        except (AssertionError, StopIteration) as error:
            rejected.append(dict(seed=seed, reason=str(error)))
            continue
        if not result:
            continue
        face = result['private_inspection']['before'][0]['private_peek']
        if face['type'] != 'person':
            rejected.append(dict(seed=seed, reason='Privately inspected face is an event'))
            continue
        result['provenance'][str(Path(__file__).relative_to(ROOT))] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        result['rehearsal_search_failures'] = rejected
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(dict(ok=True, seed=seed, commands=len(result['journal']), punk=result['punk'], face=face['card_id'])))
        return
    raise AssertionError('No complete legal hidden-person rehearsal')


if __name__ == '__main__':
    main()
