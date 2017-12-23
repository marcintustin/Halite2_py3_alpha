import numpy as np
import itertools

# higher numbers make a planet LESS desirable
PLANET_SCORING_WEIGHTS = np.array([[-70], [1000], [100], [-2], [1], [-20]])
# give it a depth of 1
PLANET_SCORING_WEIGHTS.shape = (6,1,1)

def planet_weights(ship, planets):
    for planet in planets:
        distance = ship.calculate_relative_distance(planet)
        is_mine = planet.is_owned() and planet.owner == ship.owner
        is_others = planet.is_owned() and planet.owner != ship.owner

        yield (int(is_mine and not planet.is_full()),
               int(is_mine and planet.is_full()),
               int(is_others),
               (0.5 - int(is_others))*planet.radius,
               distance,
               int(distance < 14))

def planet_features(planet, my_id):
    is_owned = planet.is_owned()
    is_mine = is_owned and planet.owner == my_id
    is_full = planet.is_full()
    is_others = int(is_owned and planet.owner != my_id)
    # NOTE NOT MEANINGFULLY COMBINABLE WITH WEIGHTS
    return np.array(
        [int(is_mine and not is_full), int(is_mine and is_full), is_others, (0.5 - is_others)*planet.radius, planet.x, planet.y ])

# columns containing X and Y for planet features
PLANET_X, PLANET_Y = 4, 5
SIZE_PLANET_FEATURES = 6
PLANET_ATTRACTION_THRESHOLD = 14

def all_planet_features(planets, my_id):
    features = np.concatenate([planet_features(planet, my_id) for planet in planets])
    features.shape = (len(planets), SIZE_PLANET_FEATURES)
    return features

def ship_positions(ships):
    """
    tiles x,y coords in the third dimension
    """
    raw = np.fromiter(itertools.chain.from_iterable((ship.x, ship.y) for ship in ships))
    # tile in the third dimension
    # so, array for all planets can be tiled in third dimension
    raw.shape = (1, 2, len(ships))
    return raw
                     

def score_all_planets_for_all_ships(ships, ship_positions, planets, planet_features, planet_positions,
                                       weights=PLANET_SCORING_WEIGHTS):
    """
    planets should be list like - position will be used to retrieve the least scoring planet
    """
    # repeat positions vertically
    ship_position = np.tile(ship_positions, (len(planets),1,1))

    planet_positions_per_ship = np.tile(planet_positions, (1, 1, len(ships)))
    planet_distances_per_ship = np.linalg.norm((planet_positions_per_ship - ship_position), axis=1, keepdims=True)
 
    planet_closer_than_threshold = (planet_distances_per_ship < PLANET_ATTRACTION_THRESHOLD).astype(int)

    planet_features_no_pos = planet_features[:, 0:4]
    planet_features_per_ship = np.tile(planet_features_no_pos, (1, 1, len(ships)))
    combined_features = np.concatenate((planet_features_per_ship, planet_distances_per_ship, planet_closer_than_threshold), axis=1)

    import pdb; pdb.set_trace()
    # TODO: Is this expanded per ship such that the dot product makes sense?
    weights_per_ship = np.tile(weights, (1, len(ships), 1))
    #combined_features.shape = (len(planets), weights.size)
    scored = np.dot(combined_features, weights_per_ship)
    # TODO: how to get lowest scored planet per ship?
    best_idx = np.argmin(scored)
    return planets[best_idx]
