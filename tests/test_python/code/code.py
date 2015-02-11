from collections import namedtuple


Point = namedtuple('Point', 'x y')


class Graph(object):
    def __init__(self, width, height):
        self.width = width
        self.height = height
        self.points = []

    def add_point(self, x, y):
        self.points.append(Point(x, y))

    def bbox(self):
        top, bottom, left, right = [0] * 4
        for point in self.points:
            top = max(top, point.y)
            bottom = min(bottom, point.y)
            left = min(left, point.x)
            right = max(right, point.x)
        return (Point(left, top), Point(right, bottom))


def main():
    graph = Graph(100, 100)
    user_input = raw_input('Enter an X,Y pair, or nothing to finish: ')
    while user_input != '':
        try:
            x, y = user_input.split(',')
            graph.add_point(int(x), int(y))
        except Exception:
            print 'TRY AGAIN BUDDY'
        user_input = raw_input('X,Y or nothing: ')
    bbox = graph.bbox()
    print 'Bounding box: ({0}, {1}), ({2}, {3})'.format(bbox[0].x, bbox[0].y, bbox[1].x, bbox[1].y)


if __name__ == '__main__':
    main()
