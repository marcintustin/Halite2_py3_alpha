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
# GAME START
# Here we define the bot's name as Settler and initialize the game, including communication with the Halite engine.
# this configures # logging to be compatible with halite
game = hlt.Game("Settler")

# higher numbers make a planet LESS desirable
PLANET_SCORING_WEIGHTS = np.array([[-70], [1000], [100], [-2], [1], [-20]])

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

def score_all_planets_for_one_ship(ship, planets, weights=PLANET_SCORING_WEIGHTS):
    """
    planets should be list like - position will be used to retrieve the least scoring planet
    """
    #totalelems = len(planets) * weights.size
    all_planet_features = np.concatenate([planet_features(planet, ship.owner) for planet in planets])
    all_planet_features.shape = (len(planets), SIZE_PLANET_FEATURES)
    planet_positions = all_planet_features[:, [PLANET_X, PLANET_Y]]

    ship_position_once = np.array([ship.x, ship.y])
    # repeat positions vertically
    ship_position = np.tile(ship_position_once, (len(planets),1))

    planet_distances = np.linalg.norm((planet_positions - ship_position), axis=1)
    # make a column vector so we can hstack
    planet_distances.shape = (len(planet_distances), 1)
    planet_closer_than_threshold = (planet_distances < PLANET_ATTRACTION_THRESHOLD).astype(int)
    
    combined_features = np.hstack((all_planet_features[:, 0:4], planet_distances, planet_closer_than_threshold))
    
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
    
    # random.shuffle(ships)
    for ship in ships:
        # TODO: Optimally Allocate ships between planets
        # If the ship is docked
        if ship.docking_status != ship.DockingStatus.UNDOCKED:
            # Skip this ship
            continue

        # TODO: Most basic enhancement is to consider planets in order of proximity to ship;
        # TODO: and to have ships target different planets from each other
        # For each planet in the game (only non-destroyed planets are included)

        # logging.debug("About to score planets")
        # scored_planets = sorted(game_map.all_planets(), key=lambda planet: planetscore(ship, planet, ship_targets, dock_attempts))
        # # logging.debug("Scored planets for ship {ship}: {scored_planets}".format(ship=ship, scored_planets=scored_planets))
        # logging.debug("Scored planets")
        planet = score_all_planets_for_one_ship(ship, planets)
        # logging.debug("Processing planet {}".format(n))
        # TODO: Identify planets that are vulnerable to re-capture
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
            ## logging.debug("making a dock attempt right now for {ship} to {planet}".format(ship=ship, planet=planet))
        else:
            # TODO: What is this? Probably should be allocating ships to planets, and sending those ships to planets
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

            # unused
            #ship_targets[ship] = target_object
            navigate_command = ship.navigate(
                ship.closest_point_to(target_object),
                game_map,
                speed=int(hlt.constants.MAX_SPEED),
                ignore_ships=False,
                angle_dodges=None)
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
