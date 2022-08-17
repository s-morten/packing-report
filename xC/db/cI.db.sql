BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "corner_impact" (
	"player_id"	INTEGER,
	"cI"	REAL,
	"cIA"	REAL,
	"sub_cI"	REAL,
	"sub_cIA"	REAL,
	PRIMARY KEY("player_id")
);
CREATE TABLE IF NOT EXISTS "lineup" (
	"game_id"	INTEGER,
	"player_id"	INTEGER,
	"home"	INTEGER,
	"min_on"	INTEGER,
	"min_off"	INTEGER,
	"team_id"	INTEGER,
	PRIMARY KEY("game_id","player_id")
);
CREATE TABLE IF NOT EXISTS "game" (
	"corner_id"	INTEGER,
	"game_id"	INTEGER,
	"corner_min"	INTEGER,
	"team_id"	INTEGER,
	"date"	INTEGER,
	PRIMARY KEY("corner_id")
);
COMMIT;
