# -*- coding: utf-8 -*-

"""
    Customized Spatial Features.
"""

import collections
import six
import numpy as np

from pysc2.lib import features
from pysc2.lib import stopwatch
from pysc2.lib import static_data
from pysc2.lib import named_array


sw = stopwatch.sw


class SpatialFeatures(collections.namedtuple("SpatialFeatures", [
        "height_map", "visibility_map", "creep", "camera",
        "player_id", "player_relative", "selected", "unit_type"])):
    """
    Set of customized feature layers (currently 8).
    Similar to pysc2.lib.features.MinimapFeatures, but with 'unit_type'.
    """
    __slots__ = ()

    def __new__(cls, **kwargs):
        feats = {}
        for name, (scale, type_, palette) in six.iteritems(kwargs):
            feats[name] = features.Feature(
                index=SpatialFeatures._fields.index(name),
                name=name,
                layer_set="minimap_renders",
                full_name="spatial " + name,
                scale=scale,
                type=type_,
                palette=palette(scale) if callable(palette) else palette,
                clip=False,
            )

        return super(SpatialFeatures, cls).__new__(cls, **feats)  # pytype: disable=missing-parameter


SPATIAL_FEATURES = SpatialFeatures(
    height_map=(256, features.FeatureType.SCALAR, features.colors.winter),
    visibility_map=(4, features.FeatureType.CATEGORICAL, features.colors.VISIBILITY_PALETTE),
    creep=(2, features.FeatureType.CATEGORICAL, features.colors.CREEP_PALETTE),
    camera=(2, features.FeatureType.CATEGORICAL, features.colors.CAMERA_PALETTE),
    player_id=(17, features.FeatureType.CATEGORICAL, features.colors.PLAYER_ABSOLUTE_PALETTE),
    player_relative=(5, features.FeatureType.CATEGORICAL, features.colors.PLAYER_RELATIVE_PALETTE),
    selected=(2, features.FeatureType.CATEGORICAL, features.colors.winter),
    unit_type=(max(static_data.UNIT_TYPES) + 1, features.FeatureType.CATEGORICAL, features.colors.unit_type)
)


class CustomFeatures(features.Features):
    """
    Render feature layer from SC2 Observation protos into numpy arrays.
    Check the documentation under 'pysc2.lib.features.Features'.
    """
    def __init__(self, agent_interface_format=None, map_size=None):
        super(CustomFeatures, self).__init__(agent_interface_format, map_size)

        if self._agent_interface_format.feature_dimensions:
            pass
        if self._agent_interface_format.rgb_dimensions:
            raise NotImplementedError

    def observation_spec(self):
        """Customized observation spec for SC2 environment."""
        obs_spec = named_array.NamedDict(
            {
                "action_result": (0, ),
                "alerts": (0, ),
                "available_actions": (0, ),
                "build_queue": (0, len(features.UnitLayer)),
                "cargo": (0, len(features.UnitLayer)),
                "cargo_slots_available": (1, ),
                "control_groups": (10, 2),
                "game_loop": (1, ),
                "last_actions": (0, ),
                "multi_select": (0, len(features.UnitLayer)),
                "player": (len(features.Player), ),
                "score_cumulative": (len(features.ScoreCumulative), ),
                "score_by_category": (len(features.ScoreByCategory), len(features.ScoreCategories)),
                "score_by_vital": (len(features.ScoreByVital), len(features.ScoreVitals)),
                "single_select": (0, len(features.UnitLayer)),
            }
        )

        aif = self._agent_interface_format
        if aif.feature_dimensions:
            obs_spec['feature_screen'] = (
                len(features.SCREEN_FEATURES),
                aif.feature_dimensions.screen.y,
                aif.feature_dimensions.screen.x
                )
            obs_spec['feature_minimap'] = (
                len(features.MINIMAP_FEATURES),
                aif.feature_dimensions.minimap.y,
                aif.feature_dimensions.minimap.x
            )
            obs_spec['feature_spatial'] = (
                len(SPATIAL_FEATURES),
                aif.feature_dimensions.minimap.y,  # FIXME
                aif.feature_dimensions.minimap.x   # FIXME
            )

        if aif.rgb_dimensions:
            raise NotImplementedError

        if aif.use_feature_units:
            obs_spec['feature_units'] = (0, len(features.FeatureUnit))

        if aif.use_raw_units:
            obs_spec['raw_units'] = (0, len(features.FeatureUnit))

        if aif.use_unit_counts:
            obs_spec['unit_counts'] = (0, len(features.UnitCounts))

        if aif.use_camera_position:
            obs_spec['camera_position'] = (2, )

        return obs_spec

    @sw.decorate
    def transform_obs(self, obs):
        """Customized rendering of SC2 observations into something an agent can handle."""
        empty = np.array([], dtype=np.int32).reshape((0, len(features.UnitLayer)))
        out = named_array.NamedDict(
            {
                "single_select": empty,
                "multi_select": empty,
                "build_queue": empty,
                "cargo": empty,
                "cargo_slots_available": np.array([0], dtype=np.int32),
            }
        )

        def or_zeros(layer, size):
            if layer is not None:
                return layer.astype(np.int32, copy=False)
            else:
                return np.zeros((size.y, size.x), dtype=np.int32)

        aif = self._agent_interface_format

        if aif.feature_dimensions:
            out['feature_screen'] = named_array.NamedNumpyArray(
                np.stack(or_zeros(f.unpack(obs.observation), aif.feature_dimensions.screen) for f in features.SCREEN_FEATURES),
                names=[features.ScreenFeatures, None, None]
            )
            out['feature_minimap'] = named_array.NamedNumpyArray(
                np.stack(or_zeros(f.unpack(obs.observation), aif.feature_dimensions.minimap) for f in features.MINIMAP_FEATURES),
                names=[features.MinimapFeatures, None, None]
            )
            out['feature_spatial'] = named_array.NamedNumpyArray(
                np.stack(or_zeros(f.unpack(obs.observation), aif.feature_dimensions.minimap) for f in SPATIAL_FEATURES),
                names=[SpatialFeatures, None, None]
            )

        if aif.rgb_dimensions:
            raise NotImplementedError

        out['last_actions'] = None   # FIXME
        out['action_result'] = None  # FIXME
        out['alerts'] = None         # FIXME
        out['game_loop'] = None      # FIXME

        score_details = obs.observation.score.score_details
        out['score_cumulative'] = None  # FIXME

        def get_score_details(key, details, categories):
            raise NotImplementedError

        out['score_by_category'] = None  # FIXME
        out['score_by_vital'] = None     # FIXME

        player = obs.observation.player_common
        out['player'] = None  # FIXME

        return out


def custom_features_from_game_info(
        game_info,
        use_feature_units=False,
        use_raw_units=False,
        action_space=False,
        hide_specific_actions=True,
        use_unit_counts=False,
        use_camera_position=False):
    """
    Construct a 'CustomFeatures' object using data extracted from game info.
    Customized version of 'pysc2.lib.features.features_from_game_info'.
    """

    if game_info.options.HasField('feature_layer'):
        fl_opts = game_info.options.feature_layer
        feature_dimensions = features.Dimensions(
            screen=(fl_opts.resolution.x, fl_opts.resolution.y),
            minimap=(fl_opts.minimap_resolution.x, fl_opts.minimap_resolution.y)
        )
    else:
        feature_dimensions = None

    if game_info.options.HasField('render'):
        raise NotImplementedError
    else:
        rgb_dimensions = None

    map_size = game_info.start_raw.map_size
    camera_width_world_units = game_info.options.feature_layer.width

    return CustomFeatures(
        agent_interface_format=features.AgentInterfaceFormat(
            feature_dimensions=feature_dimensions,
            rgb_dimensions=rgb_dimensions,
            use_feature_units=use_feature_units,
            use_raw_units=use_raw_units,
            use_unit_counts=use_unit_counts,
            use_camera_position=use_camera_position,
            camera_width_world_units=camera_width_world_units,
            action_space=action_space,
            hide_specific_actions=hide_specific_actions,
        ),
        map_size=map_size
    )