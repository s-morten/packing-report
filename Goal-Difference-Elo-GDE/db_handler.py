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
    
    def get_processed_age_files(self):
        # get all files already written to db:
        sql = """ SELECT processed from processed_footballsquads """
        cur = self.db_connection.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        already_processed_files = [i[0] for i in rows]
        return already_processed_files

    def playerage_player_to_sql(self, data: list):
        sql = ''' INSERT INTO birthday_footballsquads(kit_number,name,nationality,position,height,weight,
                    date_of_birth,place_of_birth,previous_club,team,league,season)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?) '''
        cur = self.db_connection.cursor()
        print(data)
        cur.execute(sql, data)
        self.db_connection.commit()

    def update_processed_table(self, processed_file: str):
        sql = ''' Insert into processed_footballsquads(processed)
                    VALUES(?)'''
        cur = self.db_connection.cursor()
        cur.execute(sql, [processed_file])
        self.db_connection.commit()