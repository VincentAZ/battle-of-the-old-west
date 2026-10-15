"""Import the reviewed yoke/chains with isolated materials and preservation checks."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from import_delivery_wagon import import_pack

if __name__=='__main__':
    import_pack(ROOT/'art/western/delivery/hitch-v005',
                '/Game/Art/ActionProps/Delivery/Hitch',
                'Delivery-Team.blend',ROOT/'research/western-presentation/delivery-oxen.json')
