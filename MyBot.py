"""
Welcome to your first Halite-II bot!

This bot's name is Settler. It's purpose is simple (don't expect it to win complex games :) ):
1. Initialize game
2. If a ship is not docked and there are unowned planets
2.a. Try to Dock in the planet if close enough
2.b If not, go towards the planet

Note: Please do not place print statements here as they are used to communicate with the Halite engine. If you need
to log anything use the logging module.
"""
# Let's start by importing the Halite Starter Kit so we can interface with the Halite engine
import hlt
# Then let's import the # logging module so we can print out information
import logging
import random
import math
import copy
import sys
import numpy as np
import itertools
import enemy_ships
import collections

# GAME START
# Here we define the bot's name as Settler and initialize the game, including communication with the Halite engine.
# this configures # logging to be compatible with halite
game = hlt.Game("Settler")

# higher numbers make a planet LESS desirable
# is_mine and not is_full | is_mine and is_full |  is_others | (0.5 - is_others)*planet.radius | count_in_targets | distance | closer_than_threshold
PLANET_SCORING_WEIGHTS = np.array([[-50], [2000], [100], [-2], [200], [1], [-50]])

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

def count_in_targets(ship_targets):
    """
    ship_targets maps ships to targets - {ship: target}
    return a count of the number of times each target is a target
    """
    return collections.Counter(ship_targets.values())

def score_all_planets_for_one_ship(ship, planets, planet_features, planet_positions, ship_targets,
                                       weights=PLANET_SCORING_WEIGHTS):
    """
    planets should be list like - position will be used to retrieve the least scoring planet
    """
    ship_position_once = np.array([ship.x, ship.y])
    # repeat positions vertically
    ship_position = np.tile(ship_position_once, (len(planets),1))

    planet_distances = np.linalg.norm((planet_positions - ship_position), axis=1)
    # make a column vector so we can hstack
    planet_distances.shape = (len(planet_distances), 1)
    planet_closer_than_threshold = (planet_distances < PLANET_ATTRACTION_THRESHOLD).astype(int)
    target_counts = count_in_targets(ship_targets)
    planet_target_counts = np.array([target_counts.get(planet, 0) for planet in planets])
    planet_target_counts.shape = (len(planets), 1)
    
    combined_features = np.hstack((planet_features[:, 0:4], planet_target_counts, planet_distances, planet_closer_than_threshold))
    
    #combined_features.shape = (len(planets), weights.size)
    scored = np.dot(combined_features, weights)
    best_idx = np.argmin(scored)
    return planets[best_idx]
    

def monotonic_deflections(seed=0, deflection_range=math.pi/32):
    deflection = seed
    while True:
        deflection += random.uniform(0, deflection_range)
        yield deflection

# maps planets -> ships trying to dock on them
dock_attempts = {}

while True:
    # TURN START
    # Update the map for the new turn and get the latest version
    game_map = game.update_map()
    # make changes to reflect what we intend to do
    #future_game_map = copy.deepcopy(game_map)


    # maps ships -> targets
    ship_targets = {}

    # statefully generate increasing deflections for obstacle avoidance
    deflections = monotonic_deflections()


    # Here we define the set of commands to be sent to the Halite engine at the end of the turn
    command_queue = []
    # For every ship that I control
    ships = game_map.get_me().all_ships() #[:]
    planets = game_map.all_planets()

    all_planet_features_this_round = all_planet_features(planets, game_map.my_id)
    planet_positions = all_planet_features_this_round[:, [PLANET_X, PLANET_Y]]

    try:
        nearby_enemy_ships = enemy_ships.check_enemy_distances(ships, game_map.all_ships())
    except ValueError:
        nearby_enemy_ships = {}
        
    # random.shuffle(ships)
    for ship in ships:
        target_object = None
        # TODO: Optimally Allocate ships between planets
        # If the ship is docked
        if ship.docking_status != ship.DockingStatus.UNDOCKED:
            # Skip this ship
            continue

        # if an enemy ship is close, target that, else target planets
        if ship in nearby_enemy_ships and len(nearby_enemy_ships[ship]) > 0:
            target_object = nearby_enemy_ships[ship][0]
        else:
            planet = score_all_planets_for_one_ship(ship, planets, all_planet_features_this_round, planet_positions, ship_targets)
            # logging.debug("Processing planet {}".format(n))
            # If we can dock, let's (try to) dock. If two ships try to dock at once, neither will be able to.
            if (
                    # distance is good
                    ship.can_dock(planet) and
                    # don't try to dock on a planet someone else owns
                    not (planet.is_owned() and planet.owner != ship.owner) and
                    not (planet.is_owned() and planet.owner == ship.owner and planet.is_full())):  # TODO: Don't have our own ships conflict each other
                # We add the command by appending it to the command_queue
                # dock_attempts[planet] = ship
                command_queue.append(ship.dock(planet))
                target_object = ship
                continue
            else:
                # after recalibrating what planet they are targeted for

                # If we can't dock, we move towards the closest empty point near this planet (by using closest_point_to)
                # with constant speed. Don't worry about pathfinding for now, as the command will do it for you.
                # We run this navigate command each turn until we arrive to get the latest move.
                # Here we move at half our maximum speed to better control the ships
                # In order to execute faster we also choose to ignore ship collision calculations during navigation.
                # This will mean that you have a higher probability of crashing into ships, but it also means you will
                # make move decisions much quicker. As your skill progresses and your moves turn more optimal you may
                # wish to turn that option off.

                target_object = planet
                if planet.is_owned() and planet.owner != ship.owner:
                    # attack the docked ships
                    target_object = planet.all_docked_ships()[0]

        ship_targets[ship] = target_object
        if target_object:
            navigate_command = ship.navigate(
                ship.closest_point_to(target_object),
                game_map,
                speed=int(hlt.constants.MAX_SPEED),
                ignore_ships=False,
                angle_dodges=None,
                angular_step=8)
        # If the move is possible, add it to the command_queue (if there are too many obstacles on the way
        # or we are trapped (or we reached our destination!), navigate_command will return null;
        # don't fret though, we can run the command again the next turn)
        if navigate_command:
            command_queue.append(navigate_command)
        # logging.debug("Processed all planets for ship {}".format(ship))
    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    # TURN END
# GAME END
