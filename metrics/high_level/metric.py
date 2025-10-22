from abc import ABC, abstractmethod

class Metric(ABC):
    @abstractmethod
    def predict(self):
        pass
    
    @abstractmethod
    def update(self):
        pass