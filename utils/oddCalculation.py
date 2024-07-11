class OddToPercentage:
    def odd_to_percentage(self, input_odd):
        """calculates the probability of a team winning from the bookie odds.

        Args:
            input_odd (float): the bookie odd

        Returns:
            (probability, precentage): 
            Probability: The probability in range 0-1
            Percentage: The percentage in %
        """
        divisor = 1

        while input_odd % 1 != 0:
            input_odd *= 10
            divisor *= 10

        probability = divisor / input_odd
        percentage = probability * 100

        return probability, percentage
