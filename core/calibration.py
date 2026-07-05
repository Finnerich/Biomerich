


from typing import NamedTuple


class Point(NamedTuple):
    
    x: int
    y: int


class Region(NamedTuple):
    
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> "Point":
        return Point(self.x + self.w // 2, self.y + self.h // 2)

    @classmethod
    def from_points(cls, p1, p2) -> "Region":
        return cls(*region_from_points(p1, p2))


def is_point(v) -> bool:
    
    return isinstance(v, (list, tuple)) and len(v) == 2


def is_region(v) -> bool:
    
    return isinstance(v, (list, tuple)) and len(v) == 4


def region_from_points(p1, p2):
    
    x = min(int(p1[0]), int(p2[0]))
    y = min(int(p1[1]), int(p2[1]))
    w = max(1, abs(int(p2[0]) - int(p1[0])))
    h = max(1, abs(int(p2[1]) - int(p1[1])))
    return [x, y, w, h]


def region_center(region):
    
    x, y, w, h = region
    return [x + w // 2, y + h // 2]


def as_point(xy):
    
    if xy is None:
        return None
    return [int(xy[0]), int(xy[1])]
