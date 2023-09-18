# import unittest
# import numpy as np
# import pandas as pd
# import sys

# sys.path.append("../")
# from elo import update_player_elo


# class TestEloGameCalc(unittest.TestCase):
#     def setUp(self):
#         self.game_time_table = pd.DataFrame(
#             [
#                 [0, 0, -2, 100, 100, 100, 100, 100],
#                 [1, 0, -1, 150, 150, 150, 150, np.NaN],
#                 [2, 0, 0, 90, 90, 90, np.NaN, np.NaN],
#                 [3, 1, 2, np.NaN, 200, 200, 200, 200],
#                 [4, 1, 1, 300, 300, 300, 300, 300],
#             ],
#             columns=["id", "team_id", "gd", "0", "1", "2", "3", "4"],
#         )

#     def test_integration(self):
#         updated_elo_values = []
#         for player in self.game_time_table.id:
#             updated_elo_values.append(update_player_elo(player, self.game_time_table))

#         self.assertEqual(
#             updated_elo_values,
#             [
#                 99.288131877623,
#                 149.31293977704317,
#                 90.35157444540928,
#                 200.75447420155712,
#                 300.63544197912375,
#             ],
#         )
