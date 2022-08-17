class OddToPercentage:
    def odd_to_percentage(self, input_odd):
        divisor = 1

        while input_odd % 1 != 0:
            input_odd *= 10
            divisor *= 10

        probability = divisor / input_odd
        percentage = probability * 100

        return probability, percentage
