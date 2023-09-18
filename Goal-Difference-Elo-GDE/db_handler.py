import sqlite3

class DB_handler:
    def __init__(self, db_path):
        self.db_connection = sqlite3.connect(db_path)

    def get_player_age(self, team_name, kit_number, year):
        sql = f"SELECT date_of_birth FROM birthday_footballsquads WHERE team='{team_name}' AND season='{year}' AND kit_number={kit_number}"
        cur = self.db_connection.cursor()
        cur.execute(sql)
        dob = cur.fetchall()
        print(len(dob))
        print(dob)
        print(team_name, kit_number, year)
        return dob
    
    def player_to_sql(self, line, team, league, season, db_connection):
        sql = ''' INSERT INTO birthday_footballsquads(kit_number,name,nationality,position,height,weight,
                  date_of_birth,place_of_birth,previous_club,team,league,season)
                  VALUES(?,?,?,?,?,?,?,?,?,?,?,?) '''
        cur = db_connection.cursor()
        values = [*line.values, team, league, season]
        cur.execute(sql, values)
        db_connection.commit()
        return line
    
    def update_processed_table(self, processed_file, db_connection):
        sql = ''' Insert into processed_footballsquads(processed)
                  VALUES(?)'''
        cur = db_connection.cursor()
        cur.execute(sql, processed_file)
        db_connection.commit()