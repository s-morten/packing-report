def timestamp_to_time(timestamp):
    """takes a statsbomb timestamp and returns the gametime in milliseconds

    Args:
        timestamp (string): The statsbomb timestamp that will be converted

    Returns:
        int: time in milliseconds
    """
    timestamp = timestamp.split(":")
    hours = int(timestamp[0])
    minutes = int(timestamp[1])
    seconds = int(timestamp[2].split(".")[0])
    mseconds = int(timestamp[2].split(".")[1])

    gametime = (((hours * 60) + minutes) * 60 + seconds) * 1000 + mseconds

    return gametime


def get_mat_pos(width, height):
    """transform statsbomb locations to positions in a matrix where a entry has the size 5x5

    Args:
        width (int): statsbomb pitch width
        height (int): statsbomb pitch height

    Returns:
        int, int: width idx of matrix, height idx of matrix
    """
    width_mat = int(width / 5)
    height_mat = int(height / 5)
    # TODO very unschön! und falsch?
    if height_mat == 16:
        height_mat = 15
    if width_mat == 24:
        width_mat = 23
    return width_mat, height_mat


def get_rolling_avg(a, i, M):
    """calculates rolling average over the last entries

    Args:
        a (list): the list to calculate the rolling average over, if ist a 1D array the value will be used, if the array is 2D the length of the list is used
        i (int): starting index for rolling average calc
        M (int): length of rolling average

    Returns:
        float: rolling average
    """
    # TODO check if list implementation is working
    sum = 0
    if isinstance(a[0], list):
        for x in range(M):
            if i >= x:
                sum += len(a[i - x])
    else:
        for x in range(M):
            if i >= x:
                sum += a[i - x]
    avg = sum / M
    return avg
