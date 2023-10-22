def to_season(date):
    year = int(date.year)
    if int(date.month) < 7:
        return f"{year-1}/{year}"
    else:
        return f"{year}/{year+1}"
        