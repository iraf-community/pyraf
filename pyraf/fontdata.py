"""fontdata.py
"""


from numpy import int8, array

font1 = [
    ([], []),
    ([array([10, 10], dtype=int8),
      array([9, 9, 11, 11, 9, 11], dtype=int8)],
     [array([35, 16], dtype=int8),
      array([9, 7, 7, 9, 9, 7], dtype=int8)]),
    ([
        array([5, 5], dtype=int8),
        array([5, 5], dtype=int8),
        array([14, 14], dtype=int8),
        array([14, 14], dtype=int8)
    ], [
        array([35, 31], dtype=int8),
        array([31, 35], dtype=int8),
        array([35, 31], dtype=int8),
        array([31, 35], dtype=int8)
    ]),
    ([
        array([9, 6], dtype=int8),
        array([13, 16], dtype=int8),
        array([20, 3], dtype=int8),
        array([2, 18], dtype=int8)
    ], [
        array([27, 10], dtype=int8),
        array([10, 27], dtype=int8),
        array([22, 22], dtype=int8),
        array([15, 15], dtype=int8)
    ]),
    ([
        array([9, 9], dtype=int8),
        array([1, 5, 13, 17, 17, 13, 5, 1, 1, 5, 13, 17], dtype=int8)
    ], [
        array([35, 8], dtype=int8),
        array([14, 10, 10, 13, 18, 22, 22, 25, 29, 33, 33, 29], dtype=int8)
    ]),
    ([
        array([6, 3, 1, 1, 3, 6, 8, 8, 6], dtype=int8),
        array([18, 1], dtype=int8),
        array([11, 11, 13, 16, 18, 18, 16, 13, 11], dtype=int8)
    ], [
        array([35, 35, 33, 30, 28, 28, 30, 33, 35], dtype=int8),
        array([35, 8], dtype=int8),
        array([13, 10, 8, 8, 10, 13, 15, 15, 13], dtype=int8)
    ]),
    ([array([18, 3, 3, 5, 8, 10, 10, 1, 1, 4, 11, 18], dtype=int8)],
     [array([8, 28, 32, 35, 35, 32, 29, 17, 12, 8, 8, 17], dtype=int8)]),
    ([array([9, 8, 9, 10, 9],
            dtype=int8)], [array([35, 31, 31, 35, 35], dtype=int8)]),
    ([array([11, 9, 8, 8, 9, 11],
            dtype=int8)], [array([35, 31, 26, 17, 12, 8], dtype=int8)]),
    ([array([8, 10, 11, 11, 10, 8],
            dtype=int8)], [array([35, 31, 26, 17, 12, 8], dtype=int8)]),
    ([
        array([1, 17], dtype=int8),
        array([9, 9], dtype=int8),
        array([1, 17], dtype=int8)
    ], [
        array([29, 14], dtype=int8),
        array([32, 11], dtype=int8),
        array([14, 29], dtype=int8)
    ]),
    ([array([9, 9], dtype=int8),
      array([1, 17], dtype=int8)],
     [array([28, 12], dtype=int8),
      array([20, 20], dtype=int8)]),
    ([array([8, 9, 9, 8, 8, 9],
            dtype=int8)], [array([4, 6, 9, 9, 8, 8], dtype=int8)]),
    ([array([1, 17], dtype=int8)], [array([20, 20], dtype=int8)]),
    ([array([9, 9, 11, 11, 9, 11],
            dtype=int8)], [array([9, 7, 7, 9, 9, 7], dtype=int8)]),
    ([array([1, 18], dtype=int8)], [array([8, 35], dtype=int8)]),
    ([array([6, 1, 1, 6, 13, 18, 18, 13, 6], dtype=int8)],
     [array([35, 29, 14, 8, 8, 14, 29, 35, 35], dtype=int8)]),
    ([array([3, 10, 10], dtype=int8)], [array([29, 35, 8], dtype=int8)]),
    ([array([1, 5, 14, 18, 18, 1, 1, 18],
            dtype=int8)], [array([31, 35, 35, 31, 23, 12, 8, 8], dtype=int8)]),
    ([
        array([1, 6, 13, 18, 18, 13, 9], dtype=int8),
        array([13, 18, 18, 13, 6, 1], dtype=int8)
    ], [
        array([31, 35, 35, 31, 26, 22, 22], dtype=int8),
        array([22, 18, 12, 8, 8, 13], dtype=int8)
    ]),
    ([array([14, 14, 12, 1, 1, 14], dtype=int8),
      array([14, 18], dtype=int8)],
     [array([8, 35, 35, 17, 15, 15], dtype=int8),
      array([15, 15], dtype=int8)]),
    ([array([2, 13, 18, 18, 13, 6, 1, 1, 18], dtype=int8)],
     [array([8, 8, 13, 20, 25, 25, 21, 35, 35], dtype=int8)]),
    ([array([1, 6, 13, 18, 18, 13, 6, 1, 1, 2, 10], dtype=int8)],
     [array([19, 24, 24, 19, 13, 8, 8, 13, 19, 27, 35], dtype=int8)]),
    ([array([1, 18, 6], dtype=int8)], [array([35, 35, 8], dtype=int8)]),
    ([
        array([5, 1, 1, 5, 1, 1, 5, 14, 18, 18, 14, 5], dtype=int8),
        array([14, 18, 18, 14, 5], dtype=int8)
    ], [
        array([35, 31, 26, 22, 18, 12, 8, 8, 12, 18, 22, 22], dtype=int8),
        array([22, 26, 31, 35, 35], dtype=int8)
    ]),
    ([array([10, 17, 18, 18, 13, 6, 1, 1, 6, 13, 18], dtype=int8)],
     [array([8, 16, 24, 30, 35, 35, 30, 24, 19, 19, 24], dtype=int8)]),
    ([
        array([9, 11, 11, 9, 9, 11], dtype=int8),
        array([9, 9, 11, 11, 9, 11], dtype=int8)
    ], [
        array([26, 26, 23, 23, 26, 23], dtype=int8),
        array([16, 13, 13, 16, 16, 13], dtype=int8)
    ]),
    ([
        array([9, 10, 10, 9, 9, 10], dtype=int8),
        array([9, 10, 10, 9, 9, 10], dtype=int8)
    ], [
        array([26, 26, 23, 23, 26, 23], dtype=int8),
        array([9, 12, 16, 16, 15, 15], dtype=int8)
    ]), ([array([15, 2, 15], dtype=int8)], [array([28, 20, 12], dtype=int8)]),
    ([array([17, 2], dtype=int8),
      array([2, 17], dtype=int8)],
     [array([24, 24], dtype=int8),
      array([16, 16], dtype=int8)]),
    ([array([2, 15, 2], dtype=int8)], [array([28, 20, 12], dtype=int8)]),
    ([
        array([3, 3, 6, 11, 15, 15, 8, 8], dtype=int8),
        array([8, 8, 10, 10, 8, 10], dtype=int8)
    ], [
        array([29, 32, 35, 34, 31, 26, 19, 15], dtype=int8),
        array([9, 7, 7, 9, 9, 7], dtype=int8)
    ]),
    ([
        array([
            14, 5, 1, 1, 5, 14, 18, 18, 16, 14, 13, 13, 11, 8, 6, 6, 8, 11, 13
        ],
              dtype=int8)
    ], [
        array([
            12, 12, 16, 27, 31, 31, 27, 19, 17, 17, 19, 23, 26, 26, 23, 19, 17,
            17, 19
        ],
              dtype=int8)
    ]),
    ([array([1, 7, 11, 17], dtype=int8),
      array([3, 15], dtype=int8)],
     [array([8, 35, 35, 8], dtype=int8),
      array([18, 18], dtype=int8)]),
    ([
        array([1, 14, 18, 18, 14, 1], dtype=int8),
        array([14, 18, 18, 14, 1, 1], dtype=int8)
    ], [
        array([35, 35, 31, 26, 22, 22], dtype=int8),
        array([22, 18, 12, 8, 8, 35], dtype=int8)
    ]),
    ([array([18, 13, 6, 1, 1, 6, 13, 18],
            dtype=int8)], [array([13, 8, 8, 13, 30, 35, 35, 30], dtype=int8)]),
    ([array([1, 13, 18, 18, 13, 1, 1],
            dtype=int8)], [array([35, 35, 30, 13, 8, 8, 35], dtype=int8)]),
    ([
        array([1, 1, 18], dtype=int8),
        array([1, 12], dtype=int8),
        array([1, 18], dtype=int8)
    ], [
        array([35, 8, 8], dtype=int8),
        array([22, 22], dtype=int8),
        array([35, 35], dtype=int8)
    ]),
    ([
        array([1, 1], dtype=int8),
        array([1, 12], dtype=int8),
        array([1, 18], dtype=int8)
    ], [
        array([35, 8], dtype=int8),
        array([22, 22], dtype=int8),
        array([35, 35], dtype=int8)
    ]),
    ([
        array([11, 18, 18], dtype=int8),
        array([18, 13, 6, 1, 1, 6, 13, 18], dtype=int8)
    ], [
        array([18, 18, 8], dtype=int8),
        array([13, 8, 8, 13, 30, 35, 35, 30], dtype=int8)
    ]),
    ([
        array([1, 1], dtype=int8),
        array([1, 18], dtype=int8),
        array([18, 18], dtype=int8)
    ], [
        array([35, 8], dtype=int8),
        array([21, 21], dtype=int8),
        array([8, 35], dtype=int8)
    ]),
    ([
        array([4, 14], dtype=int8),
        array([9, 9], dtype=int8),
        array([5, 14], dtype=int8)
    ], [
        array([35, 35], dtype=int8),
        array([35, 8], dtype=int8),
        array([8, 8], dtype=int8)
    ]),
    ([array([1, 6, 12, 17, 17],
            dtype=int8)], [array([13, 8, 8, 13, 35], dtype=int8)]),
    ([
        array([1, 1], dtype=int8),
        array([18, 6], dtype=int8),
        array([1, 18], dtype=int8)
    ], [
        array([35, 8], dtype=int8),
        array([8, 23], dtype=int8),
        array([18, 35], dtype=int8)
    ]), ([array([1, 1, 18], dtype=int8)], [array([35, 8, 8], dtype=int8)]),
    ([array([1, 1, 9, 17, 17],
            dtype=int8)], [array([8, 35, 21, 35, 8], dtype=int8)]),
    ([array([1, 1, 18, 18], dtype=int8)], [array([8, 35, 8, 35], dtype=int8)]),
    ([
        array([1, 6, 13, 18, 18, 13, 6, 1, 1], dtype=int8),
        array([13, 18], dtype=int8)
    ], [
        array([30, 35, 35, 30, 13, 8, 8, 13, 30], dtype=int8),
        array([30, 35], dtype=int8)
    ]),
    ([array([1, 1, 14, 18, 18, 14, 1],
            dtype=int8)], [array([8, 35, 35, 31, 24, 20, 20], dtype=int8)]),
    ([
        array([1, 1, 6, 13, 18, 18, 13, 6, 1], dtype=int8),
        array([8, 18], dtype=int8)
    ], [
        array([30, 13, 8, 8, 13, 30, 35, 35, 30], dtype=int8),
        array([24, 4], dtype=int8)
    ]),
    ([
        array([1, 1, 14, 18, 18, 14, 1], dtype=int8),
        array([14, 18], dtype=int8)
    ], [
        array([8, 35, 35, 31, 25, 22, 22], dtype=int8),
        array([22, 8], dtype=int8)
    ]),
    ([array([1, 5, 14, 18, 18, 14, 5, 1, 1, 5, 14, 18], dtype=int8)],
     [array([12, 8, 8, 12, 17, 21, 22, 26, 31, 35, 35, 31], dtype=int8)]),
    ([array([10, 10], dtype=int8),
      array([1, 19], dtype=int8)],
     [array([8, 35], dtype=int8),
      array([35, 35], dtype=int8)]),
    ([array([1, 1, 6, 13, 18, 18],
            dtype=int8)], [array([35, 13, 8, 8, 13, 35], dtype=int8)]),
    ([array([1, 9, 17], dtype=int8)], [array([35, 8, 35], dtype=int8)]),
    ([array([1, 5, 10, 15, 19],
            dtype=int8)], [array([35, 8, 21, 8, 35], dtype=int8)]),
    ([array([1, 18], dtype=int8),
      array([1, 18], dtype=int8)],
     [array([35, 8], dtype=int8),
      array([8, 35], dtype=int8)]),
    ([array([1, 9, 9], dtype=int8),
      array([9, 17], dtype=int8)],
     [array([35, 23, 8], dtype=int8),
      array([23, 35], dtype=int8)]),
    ([array([1, 18, 1, 18], dtype=int8)], [array([35, 35, 8, 8], dtype=int8)]),
    ([array([12, 7, 7, 12], dtype=int8)], [array([37, 37, 7, 7], dtype=int8)]),
    ([array([1, 18], dtype=int8)], [array([35, 8], dtype=int8)]),
    ([array([6, 11, 11, 6], dtype=int8)], [array([37, 37, 7, 7], dtype=int8)]),
    ([array([4, 9, 14], dtype=int8)], [array([32, 35, 32], dtype=int8)]),
    ([array([0, 19], dtype=int8)], [array([3, 3], dtype=int8)]),
    ([array([8, 10], dtype=int8)], [array([35, 29], dtype=int8)]),
    ([
        array([4, 11, 14, 14, 10, 5, 1, 1, 4, 11, 14], dtype=int8),
        array([14, 18], dtype=int8)
    ], [
        array([23, 23, 20, 11, 7, 7, 11, 14, 17, 17, 15], dtype=int8),
        array([11, 7], dtype=int8)
    ]),
    ([
        array([1, 1], dtype=int8),
        array([1, 5, 12, 16, 16, 12, 5, 1], dtype=int8)
    ], [
        array([35, 8], dtype=int8),
        array([12, 8, 8, 12, 19, 23, 23, 19], dtype=int8)
    ]),
    ([array([15, 12, 5, 1, 1, 5, 12, 15],
            dtype=int8)], [array([21, 23, 23, 19, 12, 8, 8, 10], dtype=int8)]),
    ([
        array([16, 12, 5, 1, 1, 5, 12, 16], dtype=int8),
        array([16, 16], dtype=int8)
    ], [
        array([19, 23, 23, 19, 12, 8, 8, 12], dtype=int8),
        array([8, 35], dtype=int8)
    ]),
    ([array([1, 16, 16, 12, 5, 1, 1, 5, 12, 16], dtype=int8)],
     [array([16, 16, 19, 23, 23, 19, 12, 8, 8, 11], dtype=int8)]),
    ([array([3, 14], dtype=int8),
      array([7, 7, 10, 14, 16], dtype=int8)],
     [array([23, 23], dtype=int8),
      array([8, 30, 33, 33, 31], dtype=int8)]),
    ([
        array([1, 5, 12, 16, 16], dtype=int8),
        array([16, 12, 5, 1, 1, 5, 12, 16], dtype=int8)
    ], [
        array([3, 0, 0, 4, 23], dtype=int8),
        array([19, 23, 23, 19, 12, 8, 8, 12], dtype=int8)
    ]),
    ([array([1, 1], dtype=int8),
      array([1, 5, 12, 16, 16], dtype=int8)],
     [array([35, 8], dtype=int8),
      array([19, 23, 23, 19, 8], dtype=int8)]),
    ([array([8, 8, 10, 10, 8, 10], dtype=int8),
      array([8, 9, 9], dtype=int8)], [
          array([29, 27, 27, 29, 29, 27], dtype=int8),
          array([21, 21, 8], dtype=int8)
      ]),
    ([
        array([8, 8, 10, 10, 8, 10], dtype=int8),
        array([8, 9, 9, 7, 4, 2], dtype=int8)
    ], [
        array([29, 27, 27, 29, 29, 27], dtype=int8),
        array([21, 21, 2, 0, 0, 2], dtype=int8)
    ]),
    ([
        array([1, 1], dtype=int8),
        array([1, 13], dtype=int8),
        array([5, 16], dtype=int8)
    ], [
        array([35, 8], dtype=int8),
        array([20, 26], dtype=int8),
        array([22, 8], dtype=int8)
    ]),
    ([array([7, 9, 9, 11], dtype=int8)], [array([35, 33, 10, 8], dtype=int8)]),
    ([
        array([1, 1], dtype=int8),
        array([9, 9], dtype=int8),
        array([1, 4, 7, 9, 11, 14, 17, 17], dtype=int8)
    ], [
        array([23, 8], dtype=int8),
        array([8, 20], dtype=int8),
        array([20, 23, 23, 20, 23, 23, 20, 8], dtype=int8)
    ]),
    ([array([1, 1], dtype=int8),
      array([1, 5, 12, 16, 16], dtype=int8)],
     [array([23, 8], dtype=int8),
      array([19, 23, 23, 19, 8], dtype=int8)]),
    ([array([1, 1, 5, 12, 16, 16, 12, 5, 1], dtype=int8)],
     [array([19, 12, 8, 8, 12, 19, 23, 23, 19], dtype=int8)]),
    ([
        array([1, 1], dtype=int8),
        array([1, 5, 12, 16, 16, 12, 5, 1], dtype=int8)
    ], [
        array([23, 0], dtype=int8),
        array([19, 23, 23, 19, 12, 8, 8, 12], dtype=int8)
    ]),
    ([
        array([16, 16], dtype=int8),
        array([16, 12, 5, 1, 1, 5, 12, 16], dtype=int8)
    ], [
        array([23, 0], dtype=int8),
        array([12, 8, 8, 12, 19, 23, 23, 19], dtype=int8)
    ]),
    ([array([1, 1], dtype=int8),
      array([1, 5, 12, 16], dtype=int8)],
     [array([23, 8], dtype=int8),
      array([19, 23, 23, 20], dtype=int8)]),
    ([array([1, 5, 12, 16, 16, 12, 5, 1, 1, 5, 12, 15], dtype=int8)],
     [array([10, 8, 8, 10, 14, 16, 16, 18, 21, 23, 23, 21], dtype=int8)]),
    ([array([4, 14], dtype=int8),
      array([15, 13, 10, 8, 8], dtype=int8)],
     [array([23, 23], dtype=int8),
      array([10, 8, 8, 10, 33], dtype=int8)]),
    ([array([1, 1, 5, 12, 16], dtype=int8),
      array([16, 16], dtype=int8)],
     [array([23, 12, 8, 8, 12], dtype=int8),
      array([8, 23], dtype=int8)]),
    ([array([2, 9, 16], dtype=int8)], [array([23, 8, 23], dtype=int8)]),
    ([array([1, 5, 9, 13, 17],
            dtype=int8)], [array([23, 8, 21, 8, 23], dtype=int8)]),
    ([array([2, 16], dtype=int8),
      array([2, 16], dtype=int8)],
     [array([23, 8], dtype=int8),
      array([8, 23], dtype=int8)]),
    ([array([1, 9], dtype=int8),
      array([5, 17], dtype=int8)],
     [array([23, 8], dtype=int8),
      array([0, 23], dtype=int8)]),
    ([array([2, 16, 2, 16], dtype=int8)], [array([23, 23, 8, 8], dtype=int8)]),
    ([array([12, 10, 8, 8, 7, 5, 7, 8, 8, 10, 12], dtype=int8)],
     [array([37, 37, 34, 25, 23, 22, 21, 19, 9, 7, 7], dtype=int8)]),
    ([array([9, 9], dtype=int8),
      array([9, 9], dtype=int8)],
     [array([35, 25], dtype=int8),
      array([18, 8], dtype=int8)]),
    ([array([7, 9, 11, 11, 12, 14, 12, 11, 11, 9, 7], dtype=int8)],
     [array([37, 37, 34, 25, 23, 22, 21, 19, 9, 7, 7], dtype=int8)]),
    ([array([1, 4, 7, 12, 15, 18],
            dtype=int8)], [array([19, 22, 22, 17, 17, 20], dtype=int8)])
]
