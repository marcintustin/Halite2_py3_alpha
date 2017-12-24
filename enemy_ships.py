import numpy as np
import scipy.spatial.distance

def extract_positions(ships):
    """
    convert a list of ships into a numpy array of their positions
    """
    my_positions = np.concatenate([np.array([ship.x, ship.y]) for ship in ships])
    my_positions.shape = (len(ships), 2)
    return my_positions

def check_enemy_distances(myships, all_ships, threshold=6):
    """
    Find out if any enemy ships are in range of my ships
    return dict of my ships to list of enemy ships in threshold range
    """

    if len(myships) <= 0 or len(all_ships) <= 0:
        raise ValueError("Sets of ships may not be empty")
    
    my_id = myships[0].owner
    not_docked = [ship for ship in myships if ship.docking_status == ship.DockingStatus.UNDOCKED]
    not_mine = [ship for ship in all_ships if ship.owner != my_id]

    my_positions = extract_positions(not_docked)
    their_positions = extract_positions(not_mine)

    #import pdb; pdb.set_trace()
    #print("** their_positions:", their_positions)
    #print("** my_positions:", my_positions)

    distances = scipy.spatial.distance.cdist(my_positions, their_positions)

    results = {}
    for (row, ship) in enumerate(not_docked):
        theirs_in_range = [
            not_mine[col]
            for col in range(len(not_mine))
            if distances[row, col] <= threshold]
        results[ship] = theirs_in_range

    return results
