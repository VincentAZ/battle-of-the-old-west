"""Rewrite visible UI string literals that bypass OldWestDisplay::Text.

Run: python3 -I scripts/apply_western_ui_literals.py [--apply]

Candidates are TEXT("...") literals containing an original-vocabulary term. Lines that are
comparisons, component or asset names, logs, telemetry keys or diagnostics are
excluded; every remaining change is printed for review before --apply.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from western_terms import table, translate  # noqa: E402

PRIVATE = ROOT / 'game/OldWest/Source/OldWestGame/Private'
FILES = ['OldWestBattleOverview.cpp', 'OldWestFieldControls.cpp', 'OldWestMasterActions.cpp',
         'OldWestCardHover.cpp', 'OldWestDamageMarkers.cpp', 'OldWestStaging.cpp', 'OldWestMasterPanel.cpp',
         'OldWestHUD.cpp', 'OldWestBattlefield.cpp', 'OldWestReadiness.h', 'OldWestPreferences.cpp']
LITERAL = re.compile(r'TEXT\("((?:[^"\\]|\\.)*)"\)')
EXCLUDE_LINE = re.compile(r'==\s*TEXT\(|!=\s*TEXT\(|CreateDefaultSubobject|UE_LOG|OLDWEST_|/Game/|Emplace\(TEXT|\.Kind\s*=|Kind==|'
                          r'StartsWith\(TEXT|Contains\(TEXT|Find\(TEXT|\["|Result\[|SetStringField|TestField|Telemetry|LogTemp|Cue\(|Play\w*Cue|Sound')
# Literals whose text is an internal key even when it is a single capitalised word.
EXCLUDE_TEXT = {'Camp', 'Punk', 'Stampede', 'damage', 'restore', 'water', 'junk', 'punk', 'camp', 'person', 'stampede', 'events', 'event'}


# Visible-looking literals that are not game vocabulary or are lookup keys.
SKIP_TEXT = {'Restore panel positions, sizes and expanded state', 'Previous settings restored.',
             'People', 'Camps', 'Events', ' joins the other camp'}
RETURN_CAPTION = re.compile(r'^\s*if \(Beat\.Kind ==.*\breturn\b')


def literal_translate(text, rows):
    # C++ escapes hide word boundaries (\nProtects); match on decoded text.
    decoded = text.replace('\\n', '\n')
    return translate(decoded, rows).replace('\n', '\\n')


def candidates():
    rows, _ = table()
    for name in FILES:
        path = PRIVATE / name
        for number, line in enumerate(path.read_text().splitlines(), 1):
            start = 0
            if RETURN_CAPTION.search(line):
                # Narration captions: keep the compared key, translate what is shown.
                start = line.index('return')
            elif EXCLUDE_LINE.search(line):
                continue
            for match in LITERAL.finditer(line, start):
                text = match.group(1)
                if text in SKIP_TEXT:
                    continue
                if text in EXCLUDE_TEXT or 'OldWest' in text or 'blocked by' in text or 'visual mesh' in text or 'walk route' in text:
                    continue
                new = literal_translate(text, rows)
                if new != text:
                    yield path, number, text, new


def main():
    apply = '--apply' in sys.argv
    changes = list(candidates())
    for path, number, old, new in changes:
        print(f'{path.name}:{number}: {old!r} -> {new!r}')
    print(len(changes), 'literal changes')
    if apply:
        by_file = {}
        for path, number, old, new in changes:
            by_file.setdefault(path, []).append((number, old, new))
        for path, edits in by_file.items():
            lines = path.read_text().splitlines(keepends=True)
            for number, old, new in edits:
                lines[number - 1] = lines[number - 1].replace('TEXT("' + old + '")', 'TEXT("' + new + '")', 1)
            path.write_text(''.join(lines))
        print('applied')


if __name__ == '__main__':
    main()
