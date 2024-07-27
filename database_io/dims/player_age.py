from database_io.db_handler_abs import DB_handler_abs
from database_io.faks import Birthday_Footballsquads
from database_io.dims import Processed_Footballsquads

class DB_player_age(DB_handler_abs):
    
    def get_player_age(self, team_name, kit_number, year):
        player = self.session.query(Birthday_Footballsquads.date_of_birth).filter(
            Birthday_Footballsquads.team == str(team_name),
            Birthday_Footballsquads.season == str(year),
            Birthday_Footballsquads.kit_number == int(kit_number)
        )
        player = player.first()
        if player:
            date_of_birth = player[0]
            return date_of_birth
        else:
            return None
            

    def get_processed_player_age_files(self):
        # get all files already written to db:
        processed_files = self.session.query(Processed_Footballsquads.processed).all()
        return processed_files

    def player_age_to_sql(self, data: list):
        player = Birthday_Footballsquads(kit_number = data[0],
                                        name = data[1],
                                        nationality = data[2],
                                        position = data[3],
                                        height = data[4],
                                        weight = data[5],
                                        date_of_birth = data[6],
                                        place_of_birth = data[7],
                                        previous_club = data[8],
                                        team = data[9],
                                        league = data[10],
                                        season = data[11])
        self.session.add(player)
        self.session.commit()

    def update_processed_player_age(self, processed_file: str):
        processed = Processed_Footballsquads(processed=processed_file)
        self.session.add(processed)
        self.session.commit()