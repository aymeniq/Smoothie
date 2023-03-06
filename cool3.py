import time
import numpy as np

class path_infos(object):
    def __init__(self, size=10):
        self.index = 0
        self.len = 0
        self.size = size
        self.weights = [None] * size
        self.times = [0] * size
        self.time_elapsed = 0
        self.last_t = self.first_t = 0
    
    def get_len(self):
        return self.len

    def linreg(self):
        """
        return a,b in solution to y = ax + b such that root mean square distance between trend line and original points is minimized
        """
        X = range(self.get_len())
        Y = [x for _, x in sorted(zip(self.times[:len(X)], self.weights[:len(X)]))]
        print(Y)

        N = len(X)
        Sx = Sy = Sxx = Syy = Sxy = 0.0
        for x, y in zip(X, Y):
            Sx = Sx + x
            Sy = Sy + y
            Sxx = Sxx + x*x
            Syy = Syy + y*y
            Sxy = Sxy + x*y
        det = Sxx * N - Sx * Sx
        return (Sxy * N - Sy * Sx)/det, (Sxx * Sy - Sx * Sxy)/det

    def add_weight(self, w, t):
        self.weights[self.index] = w
        self.times[self.index] = t
        self.last_t = t
        if self.len == 0:
            self.first_t = t
        elif self.len == self.size:
            self.first_t = self.times[(self.index+1)%self.size]
        self.index = (self.index + 1)%self.size
        self.len = min([self.len+1, self.size])

p = path_infos(15)

for x in range(7):
    p.add_weight(x, time.time())

print(p.get_len())
print(p.linreg())
print(p.times)
print(p.first_t)
print(p.last_t)
