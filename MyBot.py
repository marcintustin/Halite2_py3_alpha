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
import scipy.spatial.distance
from hlt.entity import Position

# GAME START
# Here we define the bot's name as Settler and initialize the game, including communication with the Halite engine.
# this configures # logging to be compatible with halite
game = hlt.Game("Settler")

# higher numbers make a planet LESS desirable
# is_mine and not is_full | is_mine and is_full |  is_others | (0.5 - is_others)*planet.radius | count_in_targets | distance | closer_than_threshold
PLANET_SCORING_WEIGHTS = np.array([[-50], [2000], [100], [-2], [200], [1], [-50]])
PLANET_SCORING_WEIGHTS_EARLY = np.array([[-400], [90000], [100], [-50], [-20], [10], [-50]])

PARALLELTHRESHOLD = 6
TOOMANYSHIPS = 100
EARLYSHIPS = 10

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
    

SHIPTHRESHOLD = 12
class NoShipAvailable(Exception):
    pass

cornershipID = None
def cornershipfinder():
    '''
    :return: 8th ship that isn't docked (not the ID)
    '''
    global cornershipID
    # if you don't do this then cornershipID creates a new local var with the same name
    ships = game_map.get_me().all_ships()
    if len(ships) <= SHIPTHRESHOLD and cornershipID is None:
        raise NoShipAvailable("Not at threshold")
    if cornershipID is None:
        for ship in ships:
            if ship.docking_status != ship.DockingStatus.UNDOCKED:
                continue
            cornershipID = ship.id
            return ship
        # make sure if all ships are docked we don't exist the loop
        raise NoShipAvailable("No undocked ship available")
    else:

        if game_map.get_me().get_ship(cornershipID) is not None:
            return game_map.get_me().get_ship(cornershipID)
        else:
            cornershipID = None
            return cornershipfinder()
    assert False, "We should never be here"

def cornershipmove():
    ship = cornershipfinder()
    shippos = np.array([[ship.x, ship.y]])
    corners = np.array([[0, 0],
                       [game_map.width, game_map.height],
                       [0, game_map.height],
                       [game_map.width, 0]])
    distances = scipy.spatial.distance.cdist(shippos, corners)
    index, distance = min(enumerate(distances[0]), key=lambda distance: distance[1])
    desiredcornerX, desiredcornerY = corners[index]
    #logging.info("X %s Y %s distances %s index %s distance %s", str(desiredcornerX), str(desiredcornerY), str(distances), str(index), str(distance))
    navigate_command = ship.navigate(
        ship.closest_point_to(Position(desiredcornerX, desiredcornerY)),
        game_map,
        speed=int(hlt.constants.MAX_SPEED),
        ignore_ships=False, angular_step=8)
    if navigate_command:
        assert ship.id == cornershipID, "Ship.id ({}) did not equal cornership ID ({})".format(ship.id, cornershipID) 
        command_queue.append(str(navigate_command))

turn_number = 0
while True:
    # TURN START
    turn_number += 1
    # Update the map for the new turn and get the latest version
    game_map = game.update_map()
    # make changes to reflect what we intend to do
    #future_game_map = copy.deepcopy(game_map)


    # maps ships -> targets
    ship_targets = {}

    # maps targets -> moves
    target_moves = collections.defaultdict(list)
    
    # Here we define the set of commands to be sent to the Halite engine at the end of the turn
    command_queue = []
    
    # move the cornership to the corner
    try:
        if len(game_map.all_players()) > 2:
            cornershipmove()
    except NoShipAvailable as e:
        logging.info(str(e))


    # For every ship that I control
    ships = game_map.get_me().all_ships() #[:]

    #assert len(ships) >= 3
    
    # avoid timeouts
    if len(ships) >= TOOMANYSHIPS:
        ships = ships[:-TOOMANYSHIPS]

    # avoid crashing into each other at the start of the game
    if turn_number == 1:
        ships = list(sorted(ships, key=lambda s: (s.y,s.x)))

    weights = PLANET_SCORING_WEIGHTS
    if len(ships) < EARLYSHIPS:
        weights = PLANET_SCORING_WEIGHTS_EARLY
    
    planets = game_map.all_planets()

    all_planet_features_this_round = all_planet_features(planets, game_map.my_id)
    planet_positions = all_planet_features_this_round[:, [PLANET_X, PLANET_Y]]

    try:
        nearby_enemy_ships = enemy_ships.check_enemy_distances(ships, game_map.all_ships())
    except ValueError:
        nearby_enemy_ships = {}

    # half of ships dodge one way, half the other
    ship_angles = (((np.array([ship.id for ship in ships]) % 2) * 2) - 1) * 4
        
    for angle, ship in zip(ship_angles, ships):
        target_object = None
        # TODO: Optimally Allocate ships between planets
        # If the ship is docked
        if ship.docking_status != ship.DockingStatus.UNDOCKED or ship.id == cornershipID:
            # Skip this ship
            continue

        # if an enemy ship is close, target that, else target planets
        if ship in nearby_enemy_ships and len(nearby_enemy_ships[ship]) > 0:
            target_object = nearby_enemy_ships[ship][0]
        else:
            planet = score_all_planets_for_one_ship(
                ship, planets, all_planet_features_this_round, planet_positions, ship_targets, weights=weights)
            # logging.debug("Processing planet {}".format(n))
            # If we can dock, let's (try to) dock. If two ships try to dock at once, neither will be able to.
            if (
                    # distance is good
                    ship.can_dock(planet) and
                    # don't try to dock on a planet someone else owns
                    not (planet.is_owned() and planet.owner != ship.owner) and
                    not (planet.is_owned() and planet.owner == ship.owner and planet.is_full())):  # TODO: Don't have our own ships conflict each other
                # We add the command by appending it to the command_queue
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
        if target_object in target_moves and len(ships) < PARALLELTHRESHOLD:
            navigate_command = target_moves[target_object][0].with_id(ship.id)
        elif target_object:
            navigate_command = ship.navigate(
                ship.closest_point_to(target_object),
                game_map,
                speed=int(hlt.constants.MAX_SPEED),
                ignore_ships=False,
                angle_dodges=None,
                # this way some ships dodge one way, some the other
                # angular_step=4*(-1*ship.id%2))
                angular_step=angle)
            if navigate_command:
                target_moves[target_object].append(navigate_command)
        # If the move is possible, add it to the command_queue (if there are too many obstacles on the way
        # or we are trapped (or we reached our destination!), navigate_command will return null;
        # don't fret though, we can run the command again the next turn)
        if navigate_command:
            command_queue.append(str(navigate_command))
        # logging.debug("Processed all planets for ship {}".format(ship))
    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    # TURN END
# GAME END
