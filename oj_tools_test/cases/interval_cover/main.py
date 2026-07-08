import sys


def is_covered(n, left, right, intervals):
    intervals.sort()
    next_needed = left

    for start, end in intervals:
        if end < next_needed:
            continue

        # 如果当前区间起点已经超过下一个需要覆盖的位置，中间就存在空缺。
        if start > next_needed:
            return False

        next_needed = max(next_needed, end + 1)
        if next_needed > right:
            return True

    return next_needed > right


def main():
    data = list(map(int, sys.stdin.read().split()))
    if not data:
        return

    n, left, right = data[:3]
    intervals = []
    index = 3

    for _ in range(n):
        start, end = data[index], data[index + 1]
        intervals.append((start, end))
        index += 2

    print("YES" if is_covered(n, left, right, intervals) else "NO")


if __name__ == "__main__":
    main()
