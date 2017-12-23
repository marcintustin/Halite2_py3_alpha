import weighting
import numpy as np

def test_2_2_score_all_planets_for_all_ships():
    # numpy arrays are k,j,i layout = thickness, rows, columns
    ships = ["ship_a", "ship_b", "ship_c", "ship_d"]
    # ship positions extend leftwards in the columns/j dimension
    ship_positions = np.array([[[1, 2], [3, 4], [2, 3], [4, 5]]])
    # sanity check
    assert ship_positions.shape == (1, 4, 2)
    planets = ["planet_1", "planet_2"]
    # planet positions extend downwards in the rows/i dimension
    planet_positions = np.array([[-10, 0], [5, 4]])
    planet_positions.shape = (len(planets), 2, 1)
    # sanity check
    assert planet_positions.shape == (2, 2, 1)
    # planet features extend downwards in the rows/i dimension
    planet_features =  np.array([[1, 0, 0, -10, -10, 0], [1, 0, 0, -10, 5, 4]])
    planet_features.shape = (len(planets), 6, 1)
    result = weighting.score_all_planets_for_all_ships(
            ships, ship_positions,
            planets, planet_features, planet_positions)
    assert result == ["planet_1", "planet_2"]
