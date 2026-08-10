from math import isfinite


def odd_to_percentage(input_odd: float) -> tuple[float, float]:
    """calculates the probability of a team winning from the bookie odds.

    Args:
        input_odd (float): the bookie odd

    Returns:
        (probability, percentage):
        Probability: The probability in range 0-1
        Percentage: The percentage in %
    """
    if not isfinite(input_odd) or input_odd <= 0:
        raise ValueError(f"input_odd must be a positive finite number, got {input_odd}")
    probability = 1 / input_odd
    percentage = probability * 100

    return probability, percentage
