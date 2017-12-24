import numpy
import enemy_ships
from hlt.entity import Ship

def test_enemy_ship_distances():
    myships = [Ship(0, n, x, y, 0, 0, 0, Ship.DockingStatus.UNDOCKED, 0, 0, 0) for (n, (x, y)) in enumerate((
        (0,0),
        (1,1)))]
    theirships = [Ship(1, n*10, x, y, 0, 0, 0, 0, 0, 0, 0) for (n, (x, y)) in enumerate((
        (0,-1),
        (2,2)))]

    # execute test
    result = enemy_ships.check_enemy_distances(myships, theirships, threshold=1)

    # verify
    
    expectation = {
        myships[0]: [theirships[0]],
        myships[1]: []
        }

    assert result == expectation
