"""Inspect the persisted identity hair opacity graph using Unreal's editor API."""
import unreal


def hair_root_nodes(material):
    library = unreal.MaterialEditingLibrary
    def connected(node):
        return [item for item in library.get_inputs_for_material_expression(material,node) if item]
    opacity = library.get_material_property_input_node(material, unreal.MaterialProperty.MP_OPACITY_MASK)
    assert isinstance(opacity, unreal.MaterialExpressionMultiply)
    inputs = connected(opacity)
    fades = [node for node in inputs if isinstance(node, unreal.MaterialExpressionSaturate)]
    assert len(fades) == 1
    scales = connected(fades[0])
    assert len(scales) == 1 and isinstance(scales[0], unreal.MaterialExpressionMultiply)
    scale = scales[0]
    coordinates = connected(scale)
    assert len(coordinates) == 1
    coordinate = coordinates[0]
    inverse = coordinate if isinstance(coordinate, unreal.MaterialExpressionOneMinus) else None
    if inverse:
        coordinates = connected(inverse)
        assert len(coordinates) == 1
        coordinate = coordinates[0]
    assert isinstance(coordinate, unreal.MaterialExpressionComponentMask)
    assert coordinate.get_editor_property('g') and not any(
        coordinate.get_editor_property(channel) for channel in ('r','b','a'))
    inputs = connected(coordinate)
    assert len(inputs) == 1 and isinstance(inputs[0], unreal.MaterialExpressionTextureCoordinate)
    assert inputs[0].get_editor_property('coordinate_index') == 0
    scale_inputs = dict(zip(library.get_material_expression_input_names(scale),
                           library.get_inputs_for_material_expression(material,scale)))
    assert scale_inputs['A'] == (inverse or coordinate) and scale_inputs['B'] is None
    return scale, coordinate, inverse


def verify_hair_root_fade(material, source_start):
    scale, coordinate, inverse = hair_root_nodes(material)
    assert inverse is None, 'Native root fade still inverts the already-flipped FBX V coordinate'
    multiplier = float(scale.get_editor_property('const_b'))
    assert abs(multiplier-1/(1-source_start)) < 1e-4
    return {'material':material.get_path_name(), 'native_coordinate':'V',
            'multiplier':multiplier, 'root_value_at_native_v0':0.,
            'full_value_at_native_v':1/multiplier,
            'source_root_fade_start':source_start,
            'basis':'Legacy skeletal FBX importer stores native V = 1 - source V'}
