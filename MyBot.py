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
# Then let's import the logging module so we can print out information
import logging

# GAME START
# Here we define the bot's name as Settler and initialize the game, including communication with the Halite engine.
game = hlt.Game("Settler")
# Then we print our start message to the logs
logging.info("Starting my Settler bot!")

def planetscore(ship, planet, ship_targets):
    """
    ship_targets is a map ship -> target_object
    """
    count_in_targets = len([target for target in ship_targets.values() if target == planet])
    # higher numbers make a planet LESS desirable
    return (
        1000*int(planet.is_owned())
        + 200*count_in_targets
        + ship.calculate_distance_between(planet)
        - 0.5*planet.radius)

while True:
    # TURN START
    # Update the map for the new turn and get the latest version
    game_map = game.update_map()

    # maps planets -> ships trying to dock on them
    dock_attempts = {}
    ship_targets = {}

    # Here we define the set of commands to be sent to the Halite engine at the end of the turn
    command_queue = []
    # For every ship that I control
    for ship in game_map.get_me().all_ships():
        # TODO: Optimally Allocate ships between planets
        # If the ship is docked
        if ship.docking_status != ship.DockingStatus.UNDOCKED:
            # Skip this ship
            continue

        # TODO: Most basic enhancement is to consider planets in order of proximity to ship;
        # TODO: and to have ships target different planets from each other
        # For each planet in the game (only non-destroyed planets are included)
        for planet in sorted(game_map.all_planets(), key=lambda planet: planetscore(ship, planet, ship_targets)):
            # TODO: Identify planets that are vulnerable to re-capture
            # If the planet is owned
            if (planet.is_owned() and planet.owner == ship.owner) or planet in dock_attempts:
                # Skip this planet
                continue

            # If we can dock, let's (try to) dock. If two ships try to dock at once, neither will be able to.
            if (
                    # distance is good
                    ship.can_dock(planet) and
                    # don't try to dock on a planet someone else owns
                    not (planet.is_owned() and planet.owner != ship.owner) and
                    not planet in dock_attempts): #TODO: Don't have our own ships conflict each other
                # We add the command by appending it to the command_queue
                dock_attempts[planet] = ship
                command_queue.append(ship.dock(planet))
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

                ship_targets[ship] = target_object
                navigate_command = ship.navigate(
                    ship.closest_point_to(target_object),
                    game_map,
                    speed=int(hlt.constants.MAX_SPEED),
                    ignore_ships=True)
                # If the move is possible, add it to the command_queue (if there are too many obstacles on the way
                # or we are trapped (or we reached our destination!), navigate_command will return null;
                # don't fret though, we can run the command again the next turn)
                if navigate_command:
                    command_queue.append(navigate_command)
            break

    # Send our set of commands to the Halite engine for this turn
    game.send_command_queue(command_queue)
    # TURN END
# GAME END
