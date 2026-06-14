from database_io.models.legacy import Birthday_Footballsquads, Processed_Footballsquads


class DB_player_age:
    def get_player_age(self, session, team_name, kit_number, year):
        player = (
            session.query(Birthday_Footballsquads.date_of_birth)
            .filter(
                Birthday_Footballsquads.team == str(team_name),
                Birthday_Footballsquads.season == str(year),
                Birthday_Footballsquads.kit_number == int(kit_number),
            )
            .first()
        )
        return player[0] if player else None

    def get_processed_player_age_files(self, session):
        return session.query(Processed_Footballsquads.processed).all()

    def player_age_to_sql(self, session, data: list):
        player = Birthday_Footballsquads(
            kit_number=data[0],
            name=data[1],
            nationality=data[2],
            position=data[3],
            height=data[4],
            weight=data[5],
            date_of_birth=data[6],
            place_of_birth=data[7],
            previous_club=data[8],
            team=data[9],
            league=data[10],
            season=data[11],
        )
        session.add(player)
        session.commit()

    def update_processed_player_age(self, session, processed_file: str):
        session.add(Processed_Footballsquads(processed=processed_file))
        session.commit()
